"""COMSOL helper functions: jpype conversion, study creation, result extraction.

Low-level wrappers for COMSOL Java API to avoid duplicating boilerplate.
All functions require mph and jpype to be available in the calling environment.

Usage:
    import mph
    if config is None:
        from .config import load_config
        config = load_config()
    from mph import session
    from .comsol_helpers import (
        ensure_jpype, start_comsol_client, jint, jdouble_2d,
        tags, remove_if_exists, latest_tag,
        create_eigen_study, eval_eigenfrequencies,
        parse_interp_data,
    )
    session.client = None
    client = start_comsol_client()
    model = client.load("path/to/model.mph")
    j = model.java
    create_eigen_study(j, "eig1", "5.0[GHz]", 24, "lr")
    j.study("eig1").run()
    data_tag = latest_tag(tags(j.result().dataset()), ["dset1"])
    eigs = eval_eigenfrequencies(j, data_tag, 24)
"""

from __future__ import annotations
from typing import Any
from pathlib import Path
import numpy as np


def ensure_jpype():
    """Import jpype if not already loaded. Raises ImportError if unavailable."""
    try:
        import jpype
    except ImportError as exc:
        raise ImportError("jpype1 required for COMSOL Java bridge") from exc


def _resolve_config(config=None):
    """Return the given config, loading the default config when None."""
    if config is None:
        from .config import load_config
        config = load_config()
    return config


def configure_temp_dir(config) -> Any:
    """Create the configured temp dir and point COMSOL's tempfiles.folder at it.

    Returns the com.comsol.model.util.ModelUtil Java class.
    """
    config.temp_dir.mkdir(parents=True, exist_ok=True)
    from com.comsol.model.util import ModelUtil
    ModelUtil.setPreference("tempfiles.folder", str(config.temp_dir))
    return ModelUtil


def init_comsol_runtime(config=None):
    """Initialize COMSOL runtime and return ModelUtil.

    This is a low-level initialization that returns the Java ModelUtil class.
    For higher-level usage, prefer start_comsol_client() which returns mph.Client.

    Returns:
        com.comsol.model.util.ModelUtil Java class

    Raises:
        ImportError: If mph or jpype not available
        RuntimeError: If COMSOL initialization fails
    """
    import mph
    config = _resolve_config(config)

    # Start mph client to initialize COMSOL runtime
    mph.start()

    # Configure temp directory
    try:
        return configure_temp_dir(config)
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize COMSOL runtime: {exc}") from exc


def start_comsol_client(config=None):
    """Start mph COMSOL client with configurable temp directory.

    Returns mph.Client. Caller should session.client=None before calling.
    """
    import mph
    config = _resolve_config(config)
    client = mph.start()
    try:
        configure_temp_dir(config)
    except Exception:
        pass
    return client


def jint(values: list[int]) -> Any:
    """Convert Python int list to Java int[] for COMSOL selection.set()."""
    import jpype
    arr = jpype.JArray(jpype.JInt)(len(values))
    for idx, value in enumerate(values):
        arr[idx] = int(value)
    return arr


def jdouble_2d(rows: list[list[float]]) -> Any:
    """Convert Python 2D list to Java double[][] for COMSOL Interp coord."""
    import jpype
    return jpype.JArray(jpype.JDouble, 2)(rows)


def java_matrix_to_rows(obj: Any) -> list[list[float]]:
    """Convert COMSOL Java matrix to Python 2D list of floats."""
    return [[float(value) for value in list(row)] for row in list(obj)]


def tags(collection: Any) -> list[str]:
    """Extract string tags from a COMSOL collection (study, dataset, feature)."""
    try:
        return [str(item) for item in list(collection.tags())]
    except Exception:
        return []


def remove_if_exists(collection: Any, tag: str) -> None:
    """Remove a tag from a COMSOL collection if it exists, silently ignore if not."""
    try:
        if tag in tags(collection):
            collection.remove(tag)
    except Exception:
        pass


def latest_tag(after: list[str], before: list[str]) -> str:
    """Return the first tag in `after` that is not in `before`.

    Used to find the dataset tag created by a study.run().
    Raises ValueError if no new tag found.
    """
    new_tags = [t for t in after if t not in before]
    if not new_tags:
        raise ValueError(f"no new tag found: after={after}, before={before}")
    return new_tags[0]


def new_eval_global(jmodel: Any, eval_tag: str, data_tag: str, exprs: list[str]) -> Any:
    """Create a fresh EvalGlobal numerical node bound to a dataset and expressions.

    Any pre-existing node with `eval_tag` is removed first. The returned node is
    the caller's responsibility to evaluate (getReal/computeResult) and clean up.
    """
    numerical = jmodel.result().numerical()
    remove_if_exists(numerical, eval_tag)
    node = numerical.create(eval_tag, "EvalGlobal")
    node.set("data", data_tag)
    node.set("expr", exprs)
    return node


def create_eigen_study(
    jmodel: Any,
    study_tag: str,
    shift: str,
    neigs: int,
    eigwhich: str = "lr",
) -> None:
    """Create an Eigenfrequency study with shift and neigs.

    Args:
        jmodel: Java model object (model.java from mph)
        study_tag: Unique tag for the study
        shift: Frequency shift as COMSOL expression (e.g. "5.0[GHz]")
        neigs: Number of eigenvalues to compute
        eigwhich: COMSOL solver eigenvalue target ("lr", "sm", etc.)

    The study is created but not run. Caller must j.study(study_tag).run().
    """
    remove_if_exists(jmodel.study(), study_tag)
    std = jmodel.study().create(study_tag)
    std.create("eig", "Eigenfrequency")
    eig_node = std.feature("eig")
    eig_node.set("shift", shift)
    eig_node.set("neigs", str(neigs))
    eig_node.set("eigwhich", eigwhich)
    eig_node.set("shiftactive", True)
    eig_node.set("useadvanced", True)


def eval_eigenfrequencies(jmodel: Any, data_tag: str, neigs: int) -> list[dict[str, float | int]]:
    """Extract eigenfrequencies from an eigen dataset.

    Returns list of dicts: [{"mode_idx": 1, "f_ghz": 4.962}, ...]
    mode_idx is 1-based.
    """
    eval_tag = "eval_eigenfreq_tmp"
    num = new_eval_global(jmodel, eval_tag, data_tag, ["freq"])
    try:
        raw = java_matrix_to_rows(num.getReal())
        freqs = raw[0] if raw else []
        return [{"mode_idx": i + 1, "f_ghz": float(f) / 1e9} for i, f in enumerate(freqs[:neigs])]
    finally:
        remove_if_exists(jmodel.result().numerical(), eval_tag)


def parse_interp_data(raw: Any, nexpr: int, npts: int) -> np.ndarray:
    """Parse COMSOL Interp.getData() into numpy array[expr, solnum, vertex].

    Per COMSOL API, Interp.getData() returns data[expr][solnum][vertex]. This
    function converts the nested Java lists into a 3D numpy array.

    Args:
        raw: Result of num.getData() on an Interp node
        nexpr: Expected number of expressions
        npts: Expected number of vertices (coordinate points)

    Returns:
        arr: shape (nexpr, nsol, npts), where nsol is the number of solutions
        in the dataset (e.g. eigenmodes).

    Raises:
        RuntimeError: If the structure does not match expected dimensions.
    """
    expr_blocks = list(raw)
    if len(expr_blocks) != nexpr:
        raise RuntimeError(f"unexpected Interp expr count {len(expr_blocks)}, expected {nexpr}")
    per_expr = []
    nsol = None
    for expr_block in expr_blocks:
        sol_blocks = list(expr_block)
        if nsol is None:
            nsol = len(sol_blocks)
        sols = []
        for sol_block in sol_blocks:
            vals = [float(v) for v in list(sol_block)]
            if len(vals) != npts:
                raise RuntimeError(f"unexpected vertex count {len(vals)}, expected {npts}")
            sols.append(vals)
        per_expr.append(sols)
    arr = np.asarray(per_expr, dtype=float)
    if arr.shape != (nexpr, nsol, npts):
        raise RuntimeError(f"unexpected Interp.getData shape {arr.shape}, expected {(nexpr, nsol, npts)}")
    return arr
