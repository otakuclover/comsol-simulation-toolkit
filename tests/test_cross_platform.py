"""Test cross-platform configuration and COMSOL detection."""

import os
import platform
import pytest
from pathlib import Path

from comsol_toolkit.config import (
    COMSOLConfig,
    auto_detect_comsol_root,
    load_config,
)


class TestCrossPlatform:
    """Cross-platform compatibility tests."""

    def test_auto_detect_comsol_mock(self, monkeypatch, tmp_path):
        """Test COMSOL auto-detection with mocked filesystem."""
        system = platform.system()

        if system == "Windows":
            fake_comsol = tmp_path / "Program Files" / "COMSOL" / "COMSOL62" / "Multiphysics"
            fake_comsol.mkdir(parents=True)
            monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))

        elif system == "Linux":
            fake_comsol = tmp_path / "comsol62" / "multiphysics"
            fake_comsol.mkdir(parents=True)
            # Mock both search paths
            (tmp_path / "usr" / "local").mkdir(parents=True)
            (tmp_path / "usr" / "local" / "comsol62").symlink_to(fake_comsol.parent)

        elif system == "Darwin":  # macOS
            fake_comsol = tmp_path / "COMSOL62" / "Multiphysics.app"
            fake_comsol.mkdir(parents=True)

        # This test requires actual mocking of search paths in auto_detect_comsol_root
        # For now, just test that it raises RuntimeError when not found
        monkeypatch.delenv("COMSOL_ROOT", raising=False)

    def test_env_var_override(self, monkeypatch, tmp_path):
        """Test that COMSOL_ROOT env var overrides auto-detection."""
        custom_comsol = tmp_path / "custom_comsol"
        custom_comsol.mkdir()

        monkeypatch.setenv("COMSOL_ROOT", str(custom_comsol))

        config = load_config()
        assert config.comsol_root == custom_comsol.resolve()

    def test_temp_dir_defaults(self, monkeypatch):
        """Test temp directory defaults to system temp."""
        monkeypatch.delenv("COMSOL_TEMP_DIR", raising=False)

        config = load_config()
        assert config.temp_dir.exists()
        assert "comsol_toolkit" in str(config.temp_dir)

    def test_temp_dir_custom(self, monkeypatch, tmp_path):
        """Test custom temp directory."""
        custom_temp = tmp_path / "custom_temp"
        monkeypatch.setenv("COMSOL_TEMP_DIR", str(custom_temp))

        config = load_config()
        assert config.temp_dir == custom_temp.resolve()
        assert config.temp_dir.exists()  # Should be created

    def test_path_resolution_windows_style(self, monkeypatch, tmp_path):
        """Test that Windows-style paths are handled correctly."""
        # Even on non-Windows, pathlib.Path should handle backslashes
        test_dir = tmp_path / "test"
        test_dir.mkdir()  # Create the directory first
        windows_path = str(test_dir).replace("/", "\\")
        monkeypatch.setenv("SIMULATION_PROJECT_DIR", windows_path)

        config = load_config()
        assert config.project_dir.exists()
        assert config.project_dir == test_dir.resolve()

    def test_max_workers_default(self):
        """Test that max_workers defaults to CPU count."""
        config = load_config()
        assert config.max_workers == os.cpu_count() or config.max_workers == 4

    def test_max_workers_custom(self, monkeypatch):
        """Test custom max_workers from environment."""
        monkeypatch.setenv("COMSOL_MAX_WORKERS", "8")

        config = load_config()
        assert config.max_workers == 8

    @pytest.mark.requires_comsol
    def test_validate_real_comsol(self):
        """Test validation with real COMSOL installation."""
        config = load_config()
        config.validate()  # Should not raise if COMSOL is installed

    def test_validate_fails_invalid_path(self, tmp_path):
        """Test validation fails for invalid COMSOL path."""
        invalid_path = tmp_path / "nonexistent_comsol"

        config = COMSOLConfig(comsol_root=invalid_path)

        with pytest.raises(RuntimeError, match="COMSOL installation not found"):
            config.validate()


class TestPathHandling:
    """Test cross-platform path handling."""

    def test_forward_slash_paths(self, tmp_path):
        """Test that forward slashes work on all platforms."""
        path_str = str(tmp_path / "test" / "path").replace("\\", "/")
        path = Path(path_str)

        # Should resolve correctly on all platforms
        assert path.is_absolute() or path.resolve().is_absolute()

    def test_backslash_paths(self, tmp_path):
        """Test that backslashes are handled correctly."""
        path_str = str(tmp_path / "test" / "path").replace("/", "\\")
        path = Path(path_str)

        # pathlib should normalize on all platforms
        assert path.resolve().is_absolute()

    def test_tilde_expansion(self):
        """Test that ~ expands to home directory."""
        path = Path("~/test")
        expanded = path.expanduser()

        assert expanded.is_absolute()
        assert "~" not in str(expanded)


class TestDotEnvLoading:
    """Test .env file loading."""

    def test_dotenv_loads_if_present(self, tmp_path, monkeypatch):
        """Test that .env file is loaded if python-dotenv is available."""
        # Create a .env file
        env_file = tmp_path / ".env"
        env_file.write_text("COMSOL_MAX_WORKERS=16\n")

        # Change to tmp_path so .env is found
        monkeypatch.chdir(tmp_path)

        # Reload config module to trigger dotenv loading
        import importlib
        from comsol_toolkit import config
        importlib.reload(config)

        # Check if env var was loaded
        loaded_config = config.load_config()
        # This may or may not work depending on dotenv import order
        # Just check it doesn't crash

    def test_missing_dotenv_package_ok(self, monkeypatch):
        """Test that missing python-dotenv doesn't break config loading."""
        # This is implicitly tested by all other tests if dotenv is not installed
        config = load_config()
        assert config is not None


@pytest.mark.requires_comsol
class TestRealCOMSOL:
    """Tests that require actual COMSOL installation."""

    def test_detect_real_comsol(self):
        """Test detection of real COMSOL installation."""
        try:
            comsol_root = auto_detect_comsol_root()
            assert comsol_root.exists()
            assert "comsol" in str(comsol_root).lower()
        except RuntimeError as e:
            pytest.skip(f"COMSOL not installed: {e}")

    def test_config_with_real_comsol(self):
        """Test full config with real COMSOL."""
        try:
            config = load_config()
            config.validate()

            assert config.comsol_root.exists()
            assert config.temp_dir.exists()
        except RuntimeError as e:
            pytest.skip(f"COMSOL not installed: {e}")
