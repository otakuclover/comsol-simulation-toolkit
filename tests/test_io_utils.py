"""Unit tests for comsol_toolkit.io_utils (pure numpy/pandas, no COMSOL)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from comsol_toolkit.io_utils import dedup_modes, load_case_modes

CASE = "caseA"
TAG = "neigs24"


def _write_modal_csv(modal_dir, case, shift, rows, tag=TAG):
    """Write a modal_matrix_integrals CSV with the given rows (list of dicts)."""
    path = modal_dir / f"event_centered_{case}_shift_{shift:03d}_{tag}_modal_matrix_integrals.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _write_eig_csv(modal_dir, case, shift, freqs_by_sol, tag=TAG):
    """Write an eigenfrequencies CSV: {solnum: freq_ghz}."""
    path = modal_dir / f"event_centered_{case}_shift_{shift:03d}_{tag}_eigenfrequencies.csv"
    pd.DataFrame(
        {"eig_solnum": list(freqs_by_sol.keys()), "eig_freq_ghz": list(freqs_by_sol.values())}
    ).to_csv(path, index=False)
    return path


def _diag_rows(sol, *, eta_eng, eta_raw, k_storage, m):
    """Build the four diagonal expr_key rows for a single solution number."""
    return [
        {"left_solnum": sol, "right_solnum": sol, "expr_key": "eta_i_eng", "value_real": eta_eng},
        {"left_solnum": sol, "right_solnum": sol, "expr_key": "eta_i_raw", "value_real": eta_raw},
        {
            "left_solnum": sol,
            "right_solnum": sol,
            "expr_key": "K_storage_ij",
            "value_real": k_storage,
        },
        {"left_solnum": sol, "right_solnum": sol, "expr_key": "M_ij", "value_real": m},
    ]


class TestLoadCaseModes:
    def test_single_shift_single_mode(self, tmp_path):
        rows = _diag_rows(1, eta_eng=2.0, eta_raw=1.5, k_storage=4.0, m=3.0)
        _write_modal_csv(tmp_path, CASE, 0, rows)
        _write_eig_csv(tmp_path, CASE, 0, {1: 5.0})

        df = load_case_modes(tmp_path, CASE, [0])

        assert len(df) == 1
        r = df.iloc[0]
        assert r["shift"] == 0
        assert r["solnum"] == 1
        assert r["f_eig_ghz"] == 5.0
        assert r["eta_i_eng"] == 2.0
        assert r["eta_i_raw"] == 1.5
        assert r["K_ii"] == 4.0
        assert r["M_ii"] == 3.0
        # coupling = eta_eng^2 / K
        assert r["coupling"] == pytest.approx(4.0 / 4.0)
        # eta2_w2 = eta_eng^2 / omega^2
        omega = 2 * np.pi * 5.0 * 1e9
        assert r["eta2_w2"] == pytest.approx(4.0 / omega**2)
        assert r["abs_eta"] == 2.0
        assert r["abs_eta_raw"] == 1.5

    def test_returns_expected_columns(self, tmp_path):
        _write_modal_csv(
            tmp_path, CASE, 0, _diag_rows(1, eta_eng=1.0, eta_raw=1.0, k_storage=1.0, m=1.0)
        )
        _write_eig_csv(tmp_path, CASE, 0, {1: 5.0})
        df = load_case_modes(tmp_path, CASE, [0])
        expected = {
            "shift",
            "solnum",
            "f_eig_ghz",
            "eta_i_eng",
            "eta_i_raw",
            "K_ii",
            "M_ii",
            "coupling",
            "eta2_w2",
            "abs_eta",
            "abs_eta_raw",
        }
        assert set(df.columns) == expected

    def test_missing_files_skipped(self, tmp_path):
        # No CSVs written -> empty DataFrame, no crash.
        df = load_case_modes(tmp_path, CASE, [0, 1, 2])
        assert df.empty

    def test_partial_files_skipped(self, tmp_path):
        # Only modal CSV present for shift 0 (eig missing) -> skipped.
        _write_modal_csv(
            tmp_path, CASE, 0, _diag_rows(1, eta_eng=1.0, eta_raw=1.0, k_storage=1.0, m=1.0)
        )
        df = load_case_modes(tmp_path, CASE, [0])
        assert df.empty

    def test_zero_stiffness_dropped(self, tmp_path):
        _write_modal_csv(
            tmp_path, CASE, 0, _diag_rows(1, eta_eng=2.0, eta_raw=1.0, k_storage=0.0, m=1.0)
        )
        _write_eig_csv(tmp_path, CASE, 0, {1: 5.0})
        df = load_case_modes(tmp_path, CASE, [0])
        assert df.empty

    def test_nonfinite_stiffness_dropped(self, tmp_path):
        _write_modal_csv(
            tmp_path, CASE, 0, _diag_rows(1, eta_eng=2.0, eta_raw=1.0, k_storage=np.nan, m=1.0)
        )
        _write_eig_csv(tmp_path, CASE, 0, {1: 5.0})
        df = load_case_modes(tmp_path, CASE, [0])
        assert df.empty

    def test_mode_without_frequency_skipped(self, tmp_path):
        # eta_eng exists for sol 2, but eig CSV only lists sol 1.
        _write_modal_csv(
            tmp_path, CASE, 0, _diag_rows(2, eta_eng=2.0, eta_raw=1.0, k_storage=4.0, m=1.0)
        )
        _write_eig_csv(tmp_path, CASE, 0, {1: 5.0})
        df = load_case_modes(tmp_path, CASE, [0])
        assert df.empty

    def test_offdiagonal_ignored(self, tmp_path):
        rows = _diag_rows(1, eta_eng=2.0, eta_raw=1.0, k_storage=4.0, m=1.0)
        # off-diagonal eta_i_eng row should be ignored.
        rows.append(
            {"left_solnum": 1, "right_solnum": 2, "expr_key": "eta_i_eng", "value_real": 99.0}
        )
        _write_modal_csv(tmp_path, CASE, 0, rows)
        _write_eig_csv(tmp_path, CASE, 0, {1: 5.0})
        df = load_case_modes(tmp_path, CASE, [0])
        assert len(df) == 1
        assert df.iloc[0]["eta_i_eng"] == 2.0

    def test_k_ij_fallback_when_no_storage(self, tmp_path):
        # No K_storage_ij present -> fall back to K_ij.
        rows = [
            {"left_solnum": 1, "right_solnum": 1, "expr_key": "eta_i_eng", "value_real": 2.0},
            {"left_solnum": 1, "right_solnum": 1, "expr_key": "eta_i_raw", "value_real": 1.0},
            {"left_solnum": 1, "right_solnum": 1, "expr_key": "K_ij", "value_real": 8.0},
            {"left_solnum": 1, "right_solnum": 1, "expr_key": "M_ij", "value_real": 1.0},
        ]
        _write_modal_csv(tmp_path, CASE, 0, rows)
        _write_eig_csv(tmp_path, CASE, 0, {1: 5.0})
        df = load_case_modes(tmp_path, CASE, [0])
        assert len(df) == 1
        assert df.iloc[0]["K_ii"] == 8.0

    def test_multiple_shifts_and_modes(self, tmp_path):
        _write_modal_csv(
            tmp_path,
            CASE,
            0,
            _diag_rows(1, eta_eng=2.0, eta_raw=1.0, k_storage=4.0, m=1.0)
            + _diag_rows(2, eta_eng=3.0, eta_raw=1.0, k_storage=9.0, m=1.0),
        )
        _write_eig_csv(tmp_path, CASE, 0, {1: 5.0, 2: 6.0})
        _write_modal_csv(
            tmp_path, CASE, 1, _diag_rows(1, eta_eng=1.0, eta_raw=1.0, k_storage=1.0, m=1.0)
        )
        _write_eig_csv(tmp_path, CASE, 1, {1: 7.0})

        df = load_case_modes(tmp_path, CASE, [0, 1])
        assert len(df) == 3
        assert set(df["shift"]) == {0, 1}

    def test_missing_m_is_nan(self, tmp_path):
        rows = [
            {"left_solnum": 1, "right_solnum": 1, "expr_key": "eta_i_eng", "value_real": 2.0},
            {"left_solnum": 1, "right_solnum": 1, "expr_key": "eta_i_raw", "value_real": 1.0},
            {"left_solnum": 1, "right_solnum": 1, "expr_key": "K_storage_ij", "value_real": 4.0},
        ]
        _write_modal_csv(tmp_path, CASE, 0, rows)
        _write_eig_csv(tmp_path, CASE, 0, {1: 5.0})
        df = load_case_modes(tmp_path, CASE, [0])
        assert len(df) == 1
        assert np.isnan(df.iloc[0]["M_ii"])


class TestDedupModes:
    def _base_df(self, freqs, coupling):
        return pd.DataFrame(
            {
                "f_eig_ghz": freqs,
                "coupling": coupling,
                "solnum": range(1, len(freqs) + 1),
            }
        )

    def test_empty_returns_empty(self):
        df = pd.DataFrame()
        assert dedup_modes(df).empty

    def test_close_modes_collapsed_keeps_max_coupling(self):
        # 5.000 and 5.002 GHz are 2 MHz apart (< 5 MHz default) -> one cluster.
        df = self._base_df([5.000, 5.002], [1.0, 5.0])
        out = dedup_modes(df)
        assert len(out) == 1
        assert out.iloc[0]["coupling"] == 5.0

    def test_far_modes_kept_separate(self):
        # 100 MHz apart -> two clusters.
        df = self._base_df([5.0, 5.1], [1.0, 2.0])
        out = dedup_modes(df)
        assert len(out) == 2

    def test_cluster_column_removed(self):
        df = self._base_df([5.0, 5.1], [1.0, 2.0])
        out = dedup_modes(df)
        assert "cluster" not in out.columns

    def test_custom_dedup_threshold(self):
        # 5.0 and 5.05 are 50 MHz apart; with dedup_mhz=100 they collapse.
        df = self._base_df([5.00, 5.05], [1.0, 2.0])
        out = dedup_modes(df, dedup_mhz=100.0)
        assert len(out) == 1
        assert out.iloc[0]["coupling"] == 2.0

    def test_rank_by_alternate_column(self):
        df = pd.DataFrame(
            {
                "f_eig_ghz": [5.000, 5.001],
                "coupling": [9.0, 1.0],
                "quality": [1.0, 9.0],
            }
        )
        out = dedup_modes(df, rank_by="quality")
        assert len(out) == 1
        assert out.iloc[0]["quality"] == 9.0
