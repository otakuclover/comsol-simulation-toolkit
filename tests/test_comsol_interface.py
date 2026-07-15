"""Unit tests for comsol_toolkit.comsol_interface.

The interface module is EXPERIMENTAL and contains placeholder implementations,
so these tests exercise the control flow / data shaping using mocked COMSOL
model objects rather than a real COMSOL runtime.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from comsol_toolkit import comsol_interface as ci


@pytest.fixture(autouse=True)
def _reset_handle():
    """Ensure the module-level COMSOL singleton is reset around each test."""
    ci._COMSOL_HANDLE = None
    yield
    ci._COMSOL_HANDLE = None


class TestGetComsolHandle:
    def test_initializes_once(self):
        sentinel = object()
        with patch.object(ci, "init_comsol_runtime", return_value=sentinel) as init:
            assert ci.get_comsol_handle() is sentinel
            assert ci.get_comsol_handle() is sentinel
            init.assert_called_once()

    def test_reuses_existing_handle(self):
        ci._COMSOL_HANDLE = "already-here"
        with patch.object(ci, "init_comsol_runtime") as init:
            assert ci.get_comsol_handle() == "already-here"
            init.assert_not_called()


class TestLoadOrCreateModel:
    def test_creates_from_scratch_when_no_path(self):
        model_util = MagicMock()
        with patch.object(ci, "get_comsol_handle", return_value=model_util):
            ci.load_or_create_model(None)
        model_util.create.assert_called_once_with("Model")
        model_util.load.assert_not_called()

    def test_loads_template_when_path_exists(self, tmp_path):
        mph = tmp_path / "template.mph"
        mph.write_text("dummy")
        model_util = MagicMock()
        with patch.object(ci, "get_comsol_handle", return_value=model_util):
            ci.load_or_create_model(mph)
        model_util.load.assert_called_once()
        assert str(mph) in model_util.load.call_args.args

    def test_creates_when_path_missing(self, tmp_path):
        mph = tmp_path / "does_not_exist.mph"
        model_util = MagicMock()
        with patch.object(ci, "get_comsol_handle", return_value=model_util):
            ci.load_or_create_model(mph)
        model_util.create.assert_called_once_with("Model")


class TestBuildXbarGeometry:
    def _params(self):
        return {
            "duty": 0.5,
            "pitch_um": 2.0,
            "t_ln_um": 0.4,
            "rotation_deg": 30.0,
            "t_al_nm": 100.0,
        }

    def test_returns_expected_structure(self):
        model = MagicMock()
        out = ci.build_xbar_geometry(model, self._params())
        assert out["geom_tag"] == "geom1"
        assert set(out["domain_ids"]) == {"piezo", "electrode", "all"}

    def test_sets_all_parameters(self):
        model = MagicMock()
        ci.build_xbar_geometry(model, self._params())
        param = model.java.param.return_value
        set_keys = {call.args[0] for call in param.set.call_args_list}
        assert set_keys == {"duty", "pitch", "t_ln", "rotation", "t_al"}

    def test_rebuilds_geometry(self):
        model = MagicMock()
        ci.build_xbar_geometry(model, self._params())
        model.java.component.return_value.geom.return_value.run.assert_called_once()


class TestRunEigenfrequencyStudy:
    def _model_with_freqs(self, freqs_hz):
        model = MagicMock()
        model.java.result.return_value.numerical.return_value.create.return_value.computeResult.return_value = [
            [list(freqs_hz)]
        ]
        return model

    def test_success_extracts_frequencies(self):
        model = self._model_with_freqs([5e9, 6e9, 7e9])
        out = ci.run_eigenfrequency_study(model, neigs=3, shift_ghz=5.0)
        assert out["failed"] is False
        assert out["neigs_requested"] == 3
        assert out["neigs_converged"] == 3
        assert out["eigenfreqs_hz"] == [5e9, 6e9, 7e9]
        assert out["study_tag"] == "eig1"
        assert out["elapsed_sec"] >= 0

    def test_study_configuration(self):
        model = self._model_with_freqs([5e9])
        ci.run_eigenfrequency_study(model, neigs=8, shift_ghz=17.5)
        step = model.java.study.return_value.create.return_value.feature.return_value
        sets = {call.args[0]: call.args[1] for call in step.set.call_args_list}
        assert sets["neigs"] == "8"
        assert sets["shift"] == "17.5[GHz]"
        assert sets["eigwhich"] == "lr"

    def test_failure_branch(self):
        model = MagicMock()
        model.java.study.return_value.create.return_value.run.side_effect = RuntimeError("boom")
        out = ci.run_eigenfrequency_study(model, neigs=4)
        assert out["failed"] is True
        assert out["neigs_converged"] == 0
        assert out["eigenfreqs_hz"] == []
        assert "boom" in out["error"]
        assert out["data_tag"] is None


class TestExtractModalMatrix:
    def test_returns_one_record_per_mode(self):
        model = MagicMock()
        model.java.result.return_value.numerical.return_value.create.return_value.computeResult.return_value = [
            [[5e9, 6e9]]
        ]
        modes = ci.extract_modal_matrix(model, "dset1", {"piezo": [1]})
        assert [m["mode_idx"] for m in modes] == [1, 2]
        assert [m["freq_hz"] for m in modes] == [5e9, 6e9]
        for m in modes:
            assert set(m) == {"mode_idx", "freq_hz", "eta_c", "K_nm", "M_kg"}

    def test_empty_when_no_frequencies(self):
        model = MagicMock()
        model.java.result.return_value.numerical.return_value.create.return_value.computeResult.return_value = (
            []
        )
        assert ci.extract_modal_matrix(model, "dset1", {}) == []


class TestPlaceholders:
    def test_static_capacitance_placeholder(self):
        assert ci.compute_static_capacitance(MagicMock()) == 12.34

    def test_displacement_stats_keys_and_ranges(self):
        stats = ci.compute_displacement_stats_light(MagicMock(), "dset1", 3, {}, {})
        assert set(stats) == {
            "edge_energy_frac",
            "vertical_confinement",
            "lateral_uniformity",
            "sampled_method",
        }
        assert stats["sampled_method"] == "volume_integral"
        assert 0.0 <= stats["edge_energy_frac"] <= 1.0
        assert 0.0 <= stats["vertical_confinement"] <= 1.0
        assert 0.0 <= stats["lateral_uniformity"] <= 1.0

    def test_displacement_stats_deterministic_per_mode(self):
        a = ci.compute_displacement_stats_light(MagicMock(), "d", 5, {}, {})
        b = ci.compute_displacement_stats_light(MagicMock(), "d", 5, {}, {})
        assert a == b


class TestRunComsolCase:
    def test_success_assembles_result(self):
        eigen = {
            "failed": False,
            "data_tag": "dset_eig1",
            "study_tag": "eig1",
            "neigs_requested": 2,
            "neigs_converged": 2,
            "elapsed_sec": 1.5,
        }
        modes = [{"mode_idx": 1, "freq_hz": 5e9}, {"mode_idx": 2, "freq_hz": 6e9}]
        with (
            patch.object(ci, "load_or_create_model", return_value=MagicMock()),
            patch.object(ci, "build_xbar_geometry", return_value={"domain_ids": {"all": [1]}}),
            patch.object(ci, "run_eigenfrequency_study", return_value=eigen),
            patch.object(ci, "extract_modal_matrix", return_value=[dict(m) for m in modes]),
            patch.object(ci, "compute_static_capacitance", return_value=9.9),
            patch.object(ci, "compute_displacement_stats_light", return_value={"x": 1}),
        ):
            out = ci.run_comsol_case({"duty": 0.5}, neigs=2)

        assert out["solver_meta"]["failed"] is False
        assert out["solver_meta"]["neigs_converged"] == 2
        assert out["C0_pf"] == 9.9
        assert len(out["modes"]) == 2
        assert all("displacement_stats" in m for m in out["modes"])

    def test_failure_short_circuits(self):
        eigen = {"failed": True, "error": "solver crash", "elapsed_sec": 0.2}
        with (
            patch.object(ci, "load_or_create_model", return_value=MagicMock()),
            patch.object(ci, "build_xbar_geometry", return_value={"domain_ids": {}}),
            patch.object(ci, "run_eigenfrequency_study", return_value=eigen),
            patch.object(ci, "extract_modal_matrix") as extract,
        ):
            out = ci.run_comsol_case({"duty": 0.5})

        assert out["solver_meta"]["failed"] is True
        assert out["solver_meta"]["error"] == "solver crash"
        assert out["C0_pf"] is None
        assert out["modes"] == []
        extract.assert_not_called()
