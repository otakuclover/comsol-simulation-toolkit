#!/usr/bin/env python3
"""⚠️ EXPERIMENTAL: High-level COMSOL interface (UNDER DEVELOPMENT).

WARNING: This module is currently EXPERIMENTAL and contains placeholder implementations.
Do NOT use in production. Functions like extract_modal_matrix() and compute_static_capacitance()
currently return MOCK/RANDOM values for testing purposes only.

For stable functionality, use comsol_helpers.py directly.

Future plans:
1. Model building from geometry parameters
2. Eigenfrequency study + modal matrix extraction
3. Lightweight displacement statistics (volume integrals)
4. Static capacitance calculation

This module is based on logic from RAFT-FEM research workflows but not yet production-ready.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from .comsol_helpers import (
    init_comsol_runtime,
    tags,
    remove_if_exists,
    jint,
    java_matrix_to_rows,
)


# ============================================================================
# COMSOL Runtime Management
# ============================================================================

_COMSOL_HANDLE = None


def get_comsol_handle():
    """Get or initialize COMSOL ModelUtil handle (singleton)."""
    global _COMSOL_HANDLE
    if _COMSOL_HANDLE is None:
        print("Initializing COMSOL runtime...")
        _COMSOL_HANDLE = init_comsol_runtime()
    return _COMSOL_HANDLE


def load_or_create_model(mph_path: Path | None = None) -> Any:
    """Load existing .mph or create new model.

    Args:
        mph_path: Path to template .mph, or None to create from scratch

    Returns:
        COMSOL model object
    """
    ModelUtil = get_comsol_handle()

    if mph_path and mph_path.exists():
        print(f"Loading template: {mph_path}")
        model_tag = ModelUtil.uniquetag("Model")
        model = ModelUtil.load(model_tag, str(mph_path))
    else:
        print("Creating new model from scratch")
        model_tag = ModelUtil.create("Model")
        model = ModelUtil.model(model_tag)

    return model


# ============================================================================
# Model Building (TODO: implement geometry builder)
# ============================================================================

def build_xbar_geometry(
    model: Any,
    params: dict[str, float],
) -> dict[str, Any]:
    """Build XBAR geometry from parameters.

    TODO: Implement full geometry builder
    For now, assumes template .mph with parameterized geometry

    Args:
        model: COMSOL model
        params: {duty, pitch_um, t_ln_um, rotation_deg, t_al_nm, ...}

    Returns:
        {
            "geom_tag": str,
            "domain_ids": {
                "piezo": [int],
                "electrode": [int],
                "all": [int],
            }
        }
    """
    # TODO: Implement geometry builder
    # For now, assume template has these parameters defined
    param_node = model.java.param()

    # Set parameters
    param_node.set("duty", str(params["duty"]))
    param_node.set("pitch", f"{params['pitch_um']}[um]")
    param_node.set("t_ln", f"{params['t_ln_um']}[um]")
    param_node.set("rotation", f"{params['rotation_deg']}[deg]")
    param_node.set("t_al", f"{params['t_al_nm']}[nm]")

    # Rebuild geometry
    geom_tag = "geom1"  # assume template uses this
    model.java.component("comp1").geom(geom_tag).run()

    # TODO: Auto-detect domain IDs
    # For now, return placeholder
    return {
        "geom_tag": geom_tag,
        "domain_ids": {
            "piezo": [1],  # placeholder
            "electrode": [2, 3],  # placeholder
            "all": [1, 2, 3],  # placeholder
        },
    }


# ============================================================================
# Eigenfrequency Study
# ============================================================================

def run_eigenfrequency_study(
    model: Any,
    neigs: int = 20,
    shift_ghz: float = 5.0,
    study_tag: str = "std_raft_eigen",
) -> dict[str, Any]:
    """Run eigenfrequency study.

    Args:
        model: COMSOL model
        neigs: number of eigenvalues to find
        shift_ghz: frequency shift (search around this frequency)
        study_tag: study node tag

    Returns:
        {
            "study_tag": str,
            "data_tag": str,
            "neigs_requested": int,
            "neigs_converged": int,
            "eigenfreqs_hz": list[float],
            "elapsed_sec": float,
            "failed": bool,
        }
    """
    j = model.java
    study_node = j.study()

    # Remove existing study if present
    remove_if_exists(study_node, study_tag)

    # Create eigenfrequency study
    study = study_node.create(study_tag, "Eigenfrequency")
    step = study.feature("eig")

    # Configure eigenvalue search
    step.set("neigs", str(neigs))
    step.set("shift", f"{shift_ghz}[GHz]")
    step.set("eigwhich", "lr")  # eigenvalues of largest real part

    # Run study
    print(f"  Running eigenfrequency study (neigs={neigs}, shift={shift_ghz} GHz)...")
    t0 = time.time()
    try:
        study.run()
        elapsed = time.time() - t0
        failed = False
    except Exception as exc:
        print(f"  Study failed: {exc}")
        elapsed = time.time() - t0
        failed = True
        return {
            "study_tag": study_tag,
            "data_tag": None,
            "neigs_requested": neigs,
            "neigs_converged": 0,
            "eigenfreqs_hz": [],
            "elapsed_sec": elapsed,
            "failed": True,
            "error": str(exc),
        }

    # Get solution info
    sol = j.sol(study_tag)
    data_tag = f"dset_{study_tag}"

    # Extract eigenfrequencies
    res = j.result()
    eval_tag = f"eval_{study_tag}_freq"
    remove_if_exists(res.numerical(), eval_tag)
    eval_node = res.numerical().create(eval_tag, "EvalGlobal")
    eval_node.set("data", data_tag)
    eval_node.set("expr", ["freq"])

    # Get all eigenvalues
    result = eval_node.computeResult()
    freqs_hz = java_matrix_to_rows(result[0])[0] if result else []
    neigs_converged = len(freqs_hz)

    print(f"  Converged {neigs_converged}/{neigs} eigenvalues in {elapsed:.1f} sec")

    return {
        "study_tag": study_tag,
        "data_tag": data_tag,
        "neigs_requested": neigs,
        "neigs_converged": neigs_converged,
        "eigenfreqs_hz": [float(f) for f in freqs_hz],
        "elapsed_sec": elapsed,
        "failed": False,
    }


# ============================================================================
# Modal Matrix Extraction
# ============================================================================

def extract_modal_matrix(
    model: Any,
    data_tag: str,
    domain_ids: dict[str, list[int]],
) -> list[dict[str, Any]]:
    """Extract modal matrix (eta, K, M) for all converged modes.

    Args:
        model: COMSOL model
        data_tag: solution dataset tag
        domain_ids: {"piezo": [1, ...], "electrode": [...]}

    Returns:
        List of mode records:
        [
            {
                "mode_idx": int (1-based),
                "freq_hz": float,
                "eta_c": float,  # modal coupling [C]
                "K_nm": float,   # modal stiffness [N/m]
                "M_kg": float,   # modal mass [kg]
            },
            ...
        ]
    """
    # TODO: Implement full modal matrix extraction
    # Reuse logic from export_raft_modal_matrix_comsol.py

    # For now, return placeholder
    j = model.java
    res = j.result()

    # Get eigenfrequencies
    eval_tag = "eval_modal_freq"
    remove_if_exists(res.numerical(), eval_tag)
    eval_node = res.numerical().create(eval_tag, "EvalGlobal")
    eval_node.set("data", data_tag)
    eval_node.set("expr", ["freq"])
    result = eval_node.computeResult()
    freqs_hz = java_matrix_to_rows(result[0])[0] if result else []

    # Placeholder: return mock modal data
    # TODO: Compute actual IntVolume integrals for eta, K, M
    modes = []
    for i, f_hz in enumerate(freqs_hz):
        modes.append({
            "mode_idx": i + 1,
            "freq_hz": float(f_hz),
            "eta_c": 1e-9 * (1 + 0.5 * np.random.rand()),  # TODO: real integral
            "K_nm": 1e-3 * (1 + 0.3 * np.random.rand()),   # TODO: real integral
            "M_kg": 1e-9 * (1 + 0.2 * np.random.rand()),   # TODO: real integral
        })

    return modes


# ============================================================================
# Static Capacitance
# ============================================================================

def compute_static_capacitance(
    model: Any,
    voltage: float = 1.0,
) -> float:
    """Compute static capacitance C0 (no mechanical coupling).

    Args:
        model: COMSOL model
        voltage: applied voltage [V]

    Returns:
        Capacitance [pF]
    """
    # TODO: Implement electrostatics study
    # For now, return placeholder
    return 12.34  # pF


# ============================================================================
# Displacement Statistics (B-light)
# ============================================================================

def compute_displacement_stats_light(
    model: Any,
    data_tag: str,
    mode_idx: int,
    domain_ids: dict[str, list[int]],
    geometry_params: dict[str, float],
) -> dict[str, float]:
    """Compute lightweight displacement statistics via volume integrals.

    No dense field export. Uses COMSOL IntVolume to compute:
    - Edge energy fraction (0.125 µm band at electrode edges)
    - Vertical confinement (energy in piezo layer / total)
    - Lateral uniformity (1 - std/mean of energy density along x)

    Args:
        model: COMSOL model
        data_tag: solution dataset
        mode_idx: which eigenmode (1-based)
        domain_ids: domain selections
        geometry_params: {pitch_um, t_ln_um, ...}

    Returns:
        {
            "edge_energy_frac": float [0,1],
            "vertical_confinement": float [0,1],
            "lateral_uniformity": float [0,1],
            "sampled_method": "volume_integral",
        }
    """
    # TODO: Implement IntVolume calculations
    # For now, return mock data
    np.random.seed(mode_idx)
    return {
        "edge_energy_frac": float(0.05 + 0.1 * np.random.rand()),
        "vertical_confinement": float(0.85 + 0.1 * np.random.rand()),
        "lateral_uniformity": float(0.80 + 0.15 * np.random.rand()),
        "sampled_method": "volume_integral",
    }


# ============================================================================
# High-Level Wrapper
# ============================================================================

def run_comsol_case(
    params: dict[str, float],
    template_mph: Path | None = None,
    neigs: int = 20,
    shift_ghz: float = 5.0,
) -> dict[str, Any]:
    """Run complete COMSOL case: geometry + eigen + modal matrix + stats.

    Args:
        params: geometry parameters
        template_mph: template .mph file (or None for scratch)
        neigs: number of eigenvalues
        shift_ghz: frequency shift

    Returns:
        {
            "solver_meta": {...},
            "C0_pf": float,
            "modes": [{idx, freq_hz, eta_c, K_nm, M_kg, displacement_stats}, ...],
        }
    """
    # Load/create model
    model = load_or_create_model(template_mph)

    # Build geometry
    geom_info = build_xbar_geometry(model, params)

    # Run eigenfrequency study
    eigen_result = run_eigenfrequency_study(model, neigs, shift_ghz)

    if eigen_result["failed"]:
        return {
            "solver_meta": {
                "failed": True,
                "error": eigen_result.get("error"),
                "elapsed_sec": eigen_result["elapsed_sec"],
            },
            "C0_pf": None,
            "modes": [],
        }

    # Extract modal matrix
    modes = extract_modal_matrix(model, eigen_result["data_tag"], geom_info["domain_ids"])

    # Compute static capacitance
    C0_pf = compute_static_capacitance(model)

    # Add displacement stats to each mode
    for mode in modes:
        stats = compute_displacement_stats_light(
            model,
            eigen_result["data_tag"],
            mode["mode_idx"],
            geom_info["domain_ids"],
            params,
        )
        mode["displacement_stats"] = stats

    # Cleanup
    # ModelUtil.remove(model.tag())  # TODO: decide cleanup strategy

    return {
        "solver_meta": {
            "mesh_tag": geom_info.get("mesh_tag", "mesh1"),
            "study_tag": eigen_result["study_tag"],
            "neigs_requested": eigen_result["neigs_requested"],
            "neigs_converged": eigen_result["neigs_converged"],
            "elapsed_sec": eigen_result["elapsed_sec"],
            "failed": False,
            "normalization": "max_displacement",  # TODO: configurable
        },
        "C0_pf": C0_pf,
        "modes": modes,
    }
