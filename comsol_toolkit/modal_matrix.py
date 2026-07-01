"""
用途：生成 RAFT-FEM 物理 subspace 矩阵导出规格。时间：2026-06-11
不修改：不打开 COMSOL，不读取目标导纳，不拟合 LSQ residue。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


DEFAULT_OUTDIR = Path.cwd() / "modal_matrix_output"
VOIGT_RAW = ["solid.eX", "solid.eY", "solid.eZ", "solid.eYZ", "solid.eXZ", "solid.eXY"]
VOIGT_ENG = ["solid.eX", "solid.eY", "solid.eZ", "2*solid.eYZ", "2*solid.eXZ", "2*solid.eXY"]
DRIVE_FIELDS = ["es.Ex", "es.Ey", "es.Ez"]


def withsol_expr(solver_tag: str, expr: str, solnum: int, selector_template: str | None = None) -> str:
    if selector_template:
        return selector_template.format(solver_tag=solver_tag, expr=expr, solnum=int(solnum))
    return f"withsol('{solver_tag}',({expr}),setind(solnum,{int(solnum)}))"


def right_mode_fields(eigen_solver_tag: str, right_solnum: int, selector_template: str | None = None) -> dict[str, str]:
    keys = [
        "u",
        "v",
        "w",
        "solid.eX",
        "solid.eY",
        "solid.eZ",
        "solid.eYZ",
        "solid.eXZ",
        "solid.eXY",
        "solid.sx",
        "solid.sy",
        "solid.sz",
        "solid.syz",
        "solid.sxz",
        "solid.sxy",
    ]
    return {key: withsol_expr(eigen_solver_tag, key, right_solnum, selector_template=selector_template) for key in keys}


def eta_expr(voigt: list[str], drive_wrap: str = "{expr}") -> str:
    rows = []
    for i, field in enumerate(DRIVE_FIELDS, start=1):
        drive = drive_wrap.format(expr=field)
        terms = [f"solid.eES{i}{j}*({strain})" for j, strain in enumerate(voigt, start=1)]
        rows.append(f"({drive})*(" + "+".join(terms) + ")")
    return "+".join(rows)


def matrix_pair_expressions(
    eigen_solver_tag: str,
    right_solnum: int,
    drive_wrap: str = "{expr}",
    right_selector_template: str | None = None,
) -> dict[str, str]:
    right = right_mode_fields(eigen_solver_tag, right_solnum, selector_template=right_selector_template)
    m_ij = (
        "solid.rho*("
        f"conj(u)*({right['u']})+conj(v)*({right['v']})+conj(w)*({right['w']})"
        ")"
    )
    k_ij = (
        f"conj(solid.eX)*({right['solid.sx']})+"
        f"conj(solid.eY)*({right['solid.sy']})+"
        f"conj(solid.eZ)*({right['solid.sz']})+"
        f"2*(conj(solid.eYZ)*({right['solid.syz']})+"
        f"conj(solid.eXZ)*({right['solid.sxz']})+"
        f"conj(solid.eXY)*({right['solid.sxy']}))"
    )
    return {
        "M_ij": m_ij,
        "K_ij": k_ij,
        "K_storage_ij": f"real({k_ij})",
        "K_loss_proxy_ij": f"imag({k_ij})",
        "eta_i_raw": eta_expr(VOIGT_RAW, drive_wrap=drive_wrap),
        "eta_i_eng": eta_expr(VOIGT_ENG, drive_wrap=drive_wrap),
    }


def build_export_spec(
    *,
    neigs: int,
    shift: str,
    drive_field_source: str,
    eigen_solver_tag_placeholder: str = "EIGEN_SOLVER_TAG",
    drive_solver_tag_placeholder: str = "DRIVE_SOLVER_TAG",
) -> dict[str, object]:
    drive_wrap = f"withsol('{drive_solver_tag_placeholder}',({{expr}}),setind(solnum,1))"
    mode_pairs = []
    for left in range(1, int(neigs) + 1):
        for right in range(1, int(neigs) + 1):
            mode_pairs.append({"left_solnum": left, "right_solnum": right})
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "purpose": "physical_subspace_matrix_export",
        "classification": "fixed_geometry_study_extension",
        "shift": shift,
        "neigs": int(neigs),
        "drive_field_source": drive_field_source,
        "forbidden_inputs": ["target_admittance_curve", "complex_lsq_residue", "cluster_alpha"],
        "matrices": ["M_ij", "K_ij", "K_storage_ij", "K_loss_proxy_ij", "eta_i_raw", "eta_i_eng"],
        "dynamic_model": "Y_mot(omega)=j*omega*eta_out^T*(K-omega^2*M+j*omega*B)^-1*eta_in",
        "mode_pairs": mode_pairs,
        "integration_domains": {
            "M_ij": "solid_all",
            "K_ij": "solid_all",
            "K_storage_ij": "solid_all",
            "K_loss_proxy_ij": "solid_all",
            "eta_i_raw": "full_piezo",
            "eta_i_eng": "full_piezo",
        },
        "expression_template_for_right_solnum_1": matrix_pair_expressions(
            eigen_solver_tag=eigen_solver_tag_placeholder,
            right_solnum=1,
            drive_wrap=drive_wrap,
        ),
        "normalization_policy": "export raw cross matrices first; do not normalize by target admittance or LSQ residue",
        "acceptance_checks": [
            "M must be approximately Hermitian after export",
            "diagonal K/M should recover omega_n^2 within numerical tolerance",
            "eta vector must reproduce existing scalar modal_theta rows on the diagonal/current left mode",
            "no target admittance curve may be read during export",
        ],
    }


def render_markdown(spec: dict[str, object]) -> str:
    lines = [
        "# RAFT-FEM Physical Modal Matrix Export Spec",
        "",
        f"Purpose: `{spec['purpose']}`.",
        "",
        f"Classification: `{spec['classification']}`.",
        "",
        f"Dynamic model: `{spec['dynamic_model']}`.",
        "",
        "Forbidden inputs: " + ", ".join(f"`{item}`" for item in spec["forbidden_inputs"]),  # type: ignore[index]
        "",
        "## Matrices",
        "",
    ]
    for name in spec["matrices"]:  # type: ignore[index]
        lines.append(f"- `{name}` over `{spec['integration_domains'][name]}`")  # type: ignore[index]
    lines.extend(["", "## Expression Template", ""])
    for key, expr in spec["expression_template_for_right_solnum_1"].items():  # type: ignore[index]
        lines.append(f"- `{key}`: `{expr}`")
    lines.extend(["", "## Acceptance Checks", ""])
    for check in spec["acceptance_checks"]:  # type: ignore[index]
        lines.append(f"- {check}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a dry-run RAFT-FEM physical modal matrix export specification.")
    parser.add_argument("--neigs", type=int, default=32)
    parser.add_argument("--shift", default="17.45[GHz]")
    parser.add_argument("--drive-field-source", choices=["static-es", "forced-frequency"], default="static-es")
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    args = parser.parse_args()

    spec = build_export_spec(neigs=args.neigs, shift=args.shift, drive_field_source=args.drive_field_source)
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "modal_matrix_export_spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    (args.outdir / "modal_matrix_export_spec.md").write_text(render_markdown(spec), encoding="utf-8")
    print(args.outdir / "modal_matrix_export_spec.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
