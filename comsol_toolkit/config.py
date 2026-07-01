"""Configuration management for COMSOL Simulation Toolkit.

Handles environment detection, path resolution, and config loading from:
1. Environment variables
2. .env file
3. Default fallbacks
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env if available
except ImportError:
    pass


@dataclass
class COMSOLConfig:
    """COMSOL Simulation Toolkit configuration.

    Attributes:
        comsol_root: Path to COMSOL installation (auto-detected if None)
        temp_dir: Temporary directory for COMSOL (defaults to system temp)
        project_dir: Project root directory (optional)
        results_dir: Output directory for results (optional)
        max_workers: Maximum parallel workers for sweeps (default: CPU count)
    """

    comsol_root: Optional[Path] = None
    temp_dir: Optional[Path] = None
    project_dir: Optional[Path] = None
    results_dir: Optional[Path] = None
    max_workers: int = field(default_factory=lambda: os.cpu_count() or 4)

    def __post_init__(self):
        """Resolve paths and validate configuration."""
        # Auto-detect COMSOL if not provided
        if self.comsol_root is None:
            try:
                self.comsol_root = auto_detect_comsol_root()
            except RuntimeError:
                # Allow config creation without COMSOL, validate() will catch it
                self.comsol_root = None
        else:
            self.comsol_root = Path(self.comsol_root).resolve()

        # Set temp dir (default to system temp)
        if self.temp_dir is None:
            import tempfile
            self.temp_dir = Path(tempfile.gettempdir()) / "comsol_toolkit"
        else:
            self.temp_dir = Path(self.temp_dir).resolve()

        # Resolve optional paths
        if self.project_dir:
            self.project_dir = Path(self.project_dir).resolve()
        if self.results_dir:
            self.results_dir = Path(self.results_dir).resolve()

        # Create temp dir if needed
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        """Validate that COMSOL installation exists."""
        if not self.comsol_root or not self.comsol_root.exists():
            raise RuntimeError(
                f"COMSOL installation not found at: {self.comsol_root}\n"
                f"Set COMSOL_ROOT environment variable or pass comsol_root to config."
            )


def auto_detect_comsol_root() -> Path:
    """Auto-detect COMSOL installation path.

    Search order:
    1. COMSOL_ROOT environment variable
    2. Standard installation paths for current OS

    Returns:
        Path to COMSOL Multiphysics directory

    Raises:
        RuntimeError: If COMSOL installation not found
    """
    # Check environment variable
    env_root = os.environ.get("COMSOL_ROOT")
    if env_root:
        path = Path(env_root).resolve()
        if path.exists():
            return path

    # Platform-specific search paths
    search_paths = []

    if sys.platform == "win32":
        # Windows
        program_files = [
            Path(os.environ.get("ProgramFiles", "C:/Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
        ]
        for pf in program_files:
            comsol_dir = pf / "COMSOL"
            if comsol_dir.exists():
                # Find latest version (COMSOL62, COMSOL61, etc.)
                versions = sorted(
                    [d for d in comsol_dir.iterdir() if d.is_dir() and d.name.startswith("COMSOL")],
                    reverse=True
                )
                for ver in versions:
                    mp_path = ver / "Multiphysics"
                    if mp_path.exists():
                        return mp_path.resolve()

    elif sys.platform.startswith("linux"):
        # Linux
        search_paths = [
            Path("/usr/local"),
            Path("/opt"),
        ]
        for base in search_paths:
            if not base.exists():
                continue
            # Find comsol* directories
            comsol_dirs = sorted(
                [d for d in base.iterdir() if d.is_dir() and d.name.startswith("comsol")],
                reverse=True
            )
            for comsol_dir in comsol_dirs:
                mp_path = comsol_dir / "multiphysics"
                if mp_path.exists():
                    return mp_path.resolve()

    elif sys.platform == "darwin":
        # macOS
        app_dir = Path("/Applications")
        if app_dir.exists():
            comsol_apps = sorted(
                [d for d in app_dir.iterdir() if d.is_dir() and d.name.startswith("COMSOL")],
                reverse=True
            )
            for app in comsol_apps:
                mp_path = app / "Multiphysics.app"
                if mp_path.exists():
                    return mp_path.resolve()

    raise RuntimeError(
        "COMSOL installation not found. Please set COMSOL_ROOT environment variable.\n"
        f"Searched paths: {search_paths}"
    )


def load_config(
    comsol_root: Optional[str | Path] = None,
    temp_dir: Optional[str | Path] = None,
    project_dir: Optional[str | Path] = None,
    results_dir: Optional[str | Path] = None,
    max_workers: Optional[int] = None,
) -> COMSOLConfig:
    """Load configuration from environment and arguments.

    Priority order (highest to lowest):
    1. Function arguments
    2. Environment variables (from .env or system)
    3. Auto-detected defaults

    Environment variables:
        COMSOL_ROOT: COMSOL installation directory
        COMSOL_TEMP_DIR: Temporary directory
        SIMULATION_PROJECT_DIR: Project directory
        SIMULATION_RESULTS_DIR: Results directory
        COMSOL_MAX_WORKERS: Max parallel workers

    Args:
        comsol_root: Override COMSOL installation path
        temp_dir: Override temp directory
        project_dir: Override project directory
        results_dir: Override results directory
        max_workers: Override max workers

    Returns:
        Validated COMSOLConfig instance
    """
    config = COMSOLConfig(
        comsol_root=Path(comsol_root) if comsol_root else None,
        temp_dir=Path(temp_dir) if temp_dir else (
            Path(os.environ["COMSOL_TEMP_DIR"]) if "COMSOL_TEMP_DIR" in os.environ else None
        ),
        project_dir=Path(project_dir) if project_dir else (
            Path(os.environ["SIMULATION_PROJECT_DIR"]) if "SIMULATION_PROJECT_DIR" in os.environ else None
        ),
        results_dir=Path(results_dir) if results_dir else (
            Path(os.environ["SIMULATION_RESULTS_DIR"]) if "SIMULATION_RESULTS_DIR" in os.environ else None
        ),
        max_workers=max_workers or int(os.environ.get("COMSOL_MAX_WORKERS", "0")) or os.cpu_count() or 4,
    )

    config.validate()
    return config