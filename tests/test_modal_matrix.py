"""Unit tests for comsol_toolkit.modal_matrix (pure spec generation, no COMSOL)."""

from __future__ import annotations

import json

import pytest

from comsol_toolkit import modal_matrix as mm


class TestWithsolExpr:
    def test_default_template(self):
        out = mm.withsol_expr("sol1", "u", 3)
        assert out == "withsol('sol1',(u),setind(solnum,3))"

    def test_solnum_coerced_to_int(self):
        out = mm.withsol_expr("sol1", "u", 3.9)
        assert "setind(solnum,3)" in out

    def test_custom_selector_template(self):
        tmpl = "SEL[{solver_tag}|{expr}|{solnum}]"
        out = mm.withsol_expr("sol1", "u", 2, selector_template=tmpl)
        assert out == "SEL[sol1|u|2]"


class TestRightModeFields:
    def test_all_keys_present(self):
        fields = mm.right_mode_fields("eig", 1)
        expected = {
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
        }
        assert set(fields.keys()) == expected

    def test_values_wrap_expr(self):
        fields = mm.right_mode_fields("eig", 2)
        assert fields["u"] == "withsol('eig',(u),setind(solnum,2))"


class TestEtaExpr:
    def test_has_three_drive_terms(self):
        out = mm.eta_expr(mm.VOIGT_RAW)
        # one summand per drive field (Ex, Ey, Ez)
        assert out.count("es.E") == 3

    def test_uses_supplied_voigt(self):
        out = mm.eta_expr(mm.VOIGT_ENG)
        assert "2*solid.eYZ" in out

    def test_drive_wrap_applied(self):
        out = mm.eta_expr(mm.VOIGT_RAW, drive_wrap="withsol('d',({expr}),setind(solnum,1))")
        assert "withsol('d',(es.Ex)" in out


class TestMatrixPairExpressions:
    def test_all_matrix_keys(self):
        exprs = mm.matrix_pair_expressions("eig", 1)
        assert set(exprs.keys()) == {
            "M_ij",
            "K_ij",
            "K_storage_ij",
            "K_loss_proxy_ij",
            "eta_i_raw",
            "eta_i_eng",
        }

    def test_storage_and_loss_wrap_kij(self):
        exprs = mm.matrix_pair_expressions("eig", 1)
        assert exprs["K_storage_ij"] == f"real({exprs['K_ij']})"
        assert exprs["K_loss_proxy_ij"] == f"imag({exprs['K_ij']})"

    def test_m_ij_contains_density(self):
        exprs = mm.matrix_pair_expressions("eig", 1)
        assert "solid.rho" in exprs["M_ij"]


class TestBuildExportSpec:
    def test_mode_pairs_count(self):
        spec = mm.build_export_spec(neigs=3, shift="5[GHz]", drive_field_source="static-es")
        assert len(spec["mode_pairs"]) == 9  # 3 x 3
        assert spec["mode_pairs"][0] == {"left_solnum": 1, "right_solnum": 1}
        assert spec["mode_pairs"][-1] == {"left_solnum": 3, "right_solnum": 3}

    def test_scalar_fields(self):
        spec = mm.build_export_spec(neigs=4, shift="17[GHz]", drive_field_source="forced-frequency")
        assert spec["neigs"] == 4
        assert spec["shift"] == "17[GHz]"
        assert spec["drive_field_source"] == "forced-frequency"

    def test_matrices_and_domains_consistent(self):
        spec = mm.build_export_spec(neigs=2, shift="5[GHz]", drive_field_source="static-es")
        assert set(spec["matrices"]) == set(spec["integration_domains"].keys())

    def test_neigs_string_coerced(self):
        spec = mm.build_export_spec(neigs="2", shift="5[GHz]", drive_field_source="static-es")
        assert spec["neigs"] == 2
        assert len(spec["mode_pairs"]) == 4

    def test_json_serializable(self):
        spec = mm.build_export_spec(neigs=2, shift="5[GHz]", drive_field_source="static-es")
        # Should not raise.
        json.dumps(spec)


class TestRenderMarkdown:
    @pytest.fixture()
    def spec(self):
        return mm.build_export_spec(neigs=2, shift="5[GHz]", drive_field_source="static-es")

    def test_has_title_and_sections(self, spec):
        md = mm.render_markdown(spec)
        assert md.startswith("# Piezoelectric Modal Matrix Export Specification")
        assert "## Matrices" in md
        assert "## Expression Template" in md
        assert "## Acceptance Checks" in md

    def test_lists_all_matrices(self, spec):
        md = mm.render_markdown(spec)
        for name in spec["matrices"]:
            assert f"`{name}`" in md

    def test_trailing_newline(self, spec):
        assert mm.render_markdown(spec).endswith("\n")


class TestMain:
    def test_main_writes_outputs(self, tmp_path, monkeypatch):
        outdir = tmp_path / "out"
        monkeypatch.setattr(
            "sys.argv",
            ["prog", "--neigs", "2", "--shift", "5[GHz]", "--outdir", str(outdir)],
        )
        rc = mm.main()
        assert rc == 0

        json_path = outdir / "modal_matrix_export_spec.json"
        md_path = outdir / "modal_matrix_export_spec.md"
        assert json_path.exists()
        assert md_path.exists()

        spec = json.loads(json_path.read_text())
        assert spec["neigs"] == 2
        assert len(spec["mode_pairs"]) == 4
