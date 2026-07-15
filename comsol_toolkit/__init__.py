"""
COMSOL Simulation Toolkit

Cross-platform Python toolkit for automated COMSOL Multiphysics workflows.
"""

__version__ = "0.1.0"
__author__ = "WHU_Clover"

from .comsol_helpers import (
    init_comsol_runtime,
    configure_temp_dir,
    ensure_jpype,
    start_comsol_client,
    jint,
    jdouble_2d,
    java_matrix_to_rows,
    tags,
    remove_if_exists,
    new_eval_global,
    create_eigen_study,
    eval_eigenfrequencies,
    parse_interp_data,
)
from .config import COMSOLConfig, load_config, auto_detect_comsol_root

__all__ = [
    # Config
    "COMSOLConfig",
    "load_config",
    "auto_detect_comsol_root",
    # Helpers
    "init_comsol_runtime",
    "configure_temp_dir",
    "ensure_jpype",
    "start_comsol_client",
    "jint",
    "jdouble_2d",
    "java_matrix_to_rows",
    "tags",
    "remove_if_exists",
    "new_eval_global",
    "create_eigen_study",
    "eval_eigenfrequencies",
    "parse_interp_data",
]
