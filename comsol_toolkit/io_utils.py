#!/usr/bin/env python3
"""RAFT modal-matrix IO helpers (pure numpy/pandas, no COMSOL).

Shared loader for RAFT eigenfrequency + modal-matrix CSV exports, used by the
blind-test, baseline-attack, and kt-proxy validation scripts. Centralizes the
parsing of the raw COMSOL modal_matrix_integrals.csv format so the per-mode
quantities (eta_i_eng, K_storage_ii, eta^2/K coupling) are computed identically
everywhere.

Raw modal_matrix CSV schema (from export_raft_modal_matrix_comsol.py):
    domain_label, domain_ids, data_tag, left_solnum, selection_note, expr,
    expr_key, value_real, value_imag, value_abs, right_solnum, integral_kind
Diagonal quantities are rows where left_solnum == right_solnum.
Eigenfrequency CSV schema: eig_solnum, eig_freq_ghz
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


def load_case_modes(modal_dir, case: str, shifts, neigs_tag: str = "neigs24") -> pd.DataFrame:
    """Build a per-mode table across all shifts of one geometry case.

    Returns columns: shift, solnum, f_eig_ghz, eta_i_eng, eta_i_raw, K_ii,
    M_ii, coupling (=eta_eng^2/K), eta2_w2 (=eta_eng^2/omega^2), abs_eta,
    abs_eta_raw. Rows with zero/non-finite K are dropped.

    modal_dir: directory containing event_centered_<case>_shift_NNN_<tag>_*.csv
    shifts: iterable of integer shift indices
    """
    modal_dir = Path(modal_dir)
    rows = []
    for s in shifts:
        mat_p = modal_dir / f"event_centered_{case}_shift_{s:03d}_{neigs_tag}_modal_matrix_integrals.csv"
        eig_p = modal_dir / f"event_centered_{case}_shift_{s:03d}_{neigs_tag}_eigenfrequencies.csv"
        if not mat_p.exists() or not eig_p.exists():
            continue
        mat = pd.read_csv(mat_p)
        eig = pd.read_csv(eig_p)
        freq_by_sol = dict(zip(eig["eig_solnum"], eig["eig_freq_ghz"]))

        diag = mat["left_solnum"] == mat["right_solnum"]
        eta_eng = mat[(mat["expr_key"] == "eta_i_eng") & diag]
        eta_raw = mat[(mat["expr_key"] == "eta_i_raw") & diag]
        eta_raw_by_sol = dict(zip(eta_raw["left_solnum"], eta_raw["value_real"]))
        # diagonal modal stiffness: prefer K_storage_ij, fall back to K_ij
        kexpr = "K_storage_ij" if (mat["expr_key"] == "K_storage_ij").any() else "K_ij"
        K_by_sol = dict(zip(mat[(mat["expr_key"] == kexpr) & diag]["left_solnum"],
                            mat[(mat["expr_key"] == kexpr) & diag]["value_real"]))
        M_by_sol = dict(zip(mat[(mat["expr_key"] == "M_ij") & diag]["left_solnum"],
                            mat[(mat["expr_key"] == "M_ij") & diag]["value_real"]))

        for _, r in eta_eng.iterrows():
            sol = r["left_solnum"]
            if sol not in freq_by_sol or sol not in K_by_sol:
                continue
            eta_v = r["value_real"]
            K_v = K_by_sol[sol]
            if K_v == 0 or not np.isfinite(K_v):
                continue
            f = freq_by_sol[sol]
            omega = 2 * np.pi * f * 1e9
            rows.append({
                "shift": s,
                "solnum": sol,
                "f_eig_ghz": f,
                "eta_i_eng": eta_v,
                "eta_i_raw": eta_raw_by_sol.get(sol, np.nan),
                "K_ii": K_v,
                "M_ii": M_by_sol.get(sol, np.nan),
                "coupling": eta_v**2 / K_v,
                "eta2_w2": eta_v**2 / omega**2,
                "abs_eta": abs(eta_v),
                "abs_eta_raw": abs(eta_raw_by_sol.get(sol, 0.0)),
            })
    return pd.DataFrame(rows)


def dedup_modes(df: pd.DataFrame, dedup_mhz: float = 5.0,
                rank_by: str = "coupling") -> pd.DataFrame:
    """Collapse the same physical mode seen across multiple shifts.

    Event-centered RAFT samples the same eigenmode from several shift windows,
    producing near-identical (freq, coupling) rows. Cluster by frequency
    proximity (< dedup_mhz) and keep the max-`rank_by` representative per
    cluster. Without this, top-1 and top-2 can be the same physical mode from
    different shifts, giving a fake margin of 0.
    """
    if df.empty:
        return df
    d = df.sort_values("f_eig_ghz").reset_index(drop=True)
    cid = -1
    last_f = None
    clusters = []
    for f in d["f_eig_ghz"]:
        if last_f is None or (f - last_f) * 1000.0 > dedup_mhz:
            cid += 1
        clusters.append(cid)
        last_f = f
    d["cluster"] = clusters
    rep = d.sort_values(rank_by, ascending=False).groupby("cluster", as_index=False).first()
    return rep.drop(columns=["cluster"])
