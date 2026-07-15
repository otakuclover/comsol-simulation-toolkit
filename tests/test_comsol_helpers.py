"""Unit tests for comsol_toolkit.comsol_helpers.

Focuses on the pure-Python helpers and the Java-bridge wrappers, which are
exercised with fakes/mocks instead of a real COMSOL/JVM runtime.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pytest

from comsol_toolkit import comsol_helpers as ch


class TestEnsureJpype:
    def test_ok_when_importable(self):
        # jpype1 is a declared dependency and installed in the test env.
        assert ch.ensure_jpype() is None

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "jpype", None)
        with pytest.raises(ImportError, match="jpype1 required"):
            ch.ensure_jpype()


def _install_fake_jpype(monkeypatch):
    """Install a minimal fake jpype so jint/jdouble_2d run without a JVM."""
    fake = types.ModuleType("jpype")
    fake.JInt = "JInt"
    fake.JDouble = "JDouble"

    def _jarray(_typ, _dims=1):
        def _factory(arg):
            # 1-D case is called with an int length; 2-D with the row list.
            return [0] * arg if isinstance(arg, int) else [list(r) for r in arg]

        return _factory

    fake.JArray = _jarray
    monkeypatch.setitem(sys.modules, "jpype", fake)


class TestJavaArrayConversions:
    def test_jint(self, monkeypatch):
        _install_fake_jpype(monkeypatch)
        assert ch.jint([1, 2, 3]) == [1, 2, 3]

    def test_jint_coerces_floats(self, monkeypatch):
        _install_fake_jpype(monkeypatch)
        assert ch.jint([1.9, 2.1]) == [1, 2]

    def test_jdouble_2d(self, monkeypatch):
        _install_fake_jpype(monkeypatch)
        assert ch.jdouble_2d([[1.0, 2.0], [3.0, 4.0]]) == [[1.0, 2.0], [3.0, 4.0]]


class TestJavaMatrixToRows:
    def test_nested_conversion(self):
        assert ch.java_matrix_to_rows([[1, 2], [3, 4]]) == [[1.0, 2.0], [3.0, 4.0]]

    def test_values_are_floats(self):
        out = ch.java_matrix_to_rows([[1, 2]])
        assert all(isinstance(v, float) for v in out[0])


class TestTags:
    def test_extracts_string_tags(self):
        coll = MagicMock()
        coll.tags.return_value = ["a", "b"]
        assert ch.tags(coll) == ["a", "b"]

    def test_returns_empty_on_error(self):
        coll = MagicMock()
        coll.tags.side_effect = RuntimeError("no bridge")
        assert ch.tags(coll) == []


class TestRemoveIfExists:
    def test_removes_present_tag(self):
        coll = MagicMock()
        coll.tags.return_value = ["dset1", "dset2"]
        ch.remove_if_exists(coll, "dset1")
        coll.remove.assert_called_once_with("dset1")

    def test_skips_absent_tag(self):
        coll = MagicMock()
        coll.tags.return_value = ["dset2"]
        ch.remove_if_exists(coll, "dset1")
        coll.remove.assert_not_called()

    def test_swallows_errors(self):
        coll = MagicMock()
        coll.tags.side_effect = RuntimeError("boom")
        # Should not raise.
        ch.remove_if_exists(coll, "dset1")


class TestLatestTag:
    def test_returns_new_tag(self):
        assert ch.latest_tag(["a", "b", "c"], ["a", "b"]) == "c"

    def test_returns_first_new_tag(self):
        assert ch.latest_tag(["a", "b", "c"], ["a"]) == "b"

    def test_raises_when_no_new_tag(self):
        with pytest.raises(ValueError, match="no new tag"):
            ch.latest_tag(["a", "b"], ["a", "b"])


class TestCreateEigenStudy:
    def test_configures_study(self):
        jmodel = MagicMock()
        jmodel.study.return_value.tags.side_effect = RuntimeError  # force tags() -> []
        ch.create_eigen_study(jmodel, "eig1", "5.0[GHz]", 24, "lr")

        jmodel.study.return_value.create.assert_called_once_with("eig1")
        std = jmodel.study.return_value.create.return_value
        std.create.assert_called_once_with("eig", "Eigenfrequency")

        eig_node = std.feature.return_value
        sets = {call.args[0]: call.args[1] for call in eig_node.set.call_args_list}
        assert sets["shift"] == "5.0[GHz]"
        assert sets["neigs"] == "24"
        assert sets["eigwhich"] == "lr"
        assert sets["shiftactive"] is True
        assert sets["useadvanced"] is True


class TestEvalEigenfrequencies:
    def _model(self, freqs_hz):
        jmodel = MagicMock()
        num = jmodel.result.return_value.numerical.return_value.create.return_value
        num.getReal.return_value = [list(freqs_hz)]
        return jmodel

    def test_converts_hz_to_ghz(self):
        jmodel = self._model([5e9, 6e9])
        out = ch.eval_eigenfrequencies(jmodel, "dset1", 24)
        assert out == [
            {"mode_idx": 1, "f_ghz": 5.0},
            {"mode_idx": 2, "f_ghz": 6.0},
        ]

    def test_truncates_to_neigs(self):
        jmodel = self._model([5e9, 6e9, 7e9])
        out = ch.eval_eigenfrequencies(jmodel, "dset1", 2)
        assert len(out) == 2

    def test_empty_result(self):
        jmodel = MagicMock()
        num = jmodel.result.return_value.numerical.return_value.create.return_value
        num.getReal.return_value = []
        assert ch.eval_eigenfrequencies(jmodel, "dset1", 4) == []


class TestParseInterpData:
    def test_valid_shape(self):
        # nexpr=2, nsol=2, npts=3
        raw = [
            [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
            [[7.0, 8.0, 9.0], [10.0, 11.0, 12.0]],
        ]
        arr = ch.parse_interp_data(raw, nexpr=2, npts=3)
        assert arr.shape == (2, 2, 3)
        assert arr[1, 0, 2] == 9.0
        assert arr.dtype == np.float64

    def test_wrong_expr_count_raises(self):
        raw = [[[1.0, 2.0]]]
        with pytest.raises(RuntimeError, match="unexpected Interp expr count"):
            ch.parse_interp_data(raw, nexpr=2, npts=2)

    def test_wrong_vertex_count_raises(self):
        raw = [[[1.0, 2.0, 3.0]]]
        with pytest.raises(RuntimeError, match="unexpected vertex count"):
            ch.parse_interp_data(raw, nexpr=1, npts=2)
