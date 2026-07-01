# Cross-Platform Setup Guide

## Installation

### 1. Install COMSOL Multiphysics

Download and install COMSOL from the official website with a valid license.

**Supported versions**: COMSOL 6.0+

### 2. Verify COMSOL Installation

The toolkit will auto-detect COMSOL from standard paths:

| Platform | Default Installation Path |
|----------|--------------------------|
| Windows  | `C:\Program Files\COMSOL\COMSOL62\Multiphysics` |
| Linux    | `/usr/local/comsol62/multiphysics` or `/opt/comsol62/multiphysics` |
| macOS    | `/Applications/COMSOL62/Multiphysics.app` |

**Manual override**: Set `COMSOL_ROOT` environment variable:

```bash
# Windows (PowerShell)
$env:COMSOL_ROOT = "C:\Custom\Path\To\COMSOL\Multiphysics"

# Linux/macOS
export COMSOL_ROOT="/custom/path/to/comsol/multiphysics"
```

### 3. Install Python Package

```bash
pip install comsol-simulation-toolkit
```

### 4. Test Installation

```python
from comsol_toolkit import COMSOLInterface

# This will auto-detect COMSOL and print the installation path
comsol = COMSOLInterface()
print(f"COMSOL found at: {comsol.config.comsol_root}")
```

## Environment Variables

Create a `.env` file in your project root or set system environment variables:

```bash
# Required (auto-detected if not set)
COMSOL_ROOT=/usr/local/comsol62/multiphysics

# Optional
COMSOL_TEMP_DIR=/scratch/comsol_tmp          # Default: system temp
SIMULATION_PROJECT_DIR=/path/to/project      # Default: current directory
SIMULATION_RESULTS_DIR=/path/to/results      # Default: ./results
COMSOL_MAX_WORKERS=4                         # Default: CPU count
```

## Platform-Specific Notes

### Windows

**Path Separators**: Use forward slashes `/` or raw strings `r"C:\path"` in Python.

**Antivirus**: Some antivirus software may slow down COMSOL Java startup. Add exclusions for:
- COMSOL installation directory
- `COMSOL_TEMP_DIR`

**Firewall**: COMSOL server may require firewall exceptions.

### Linux

**Java Runtime**: COMSOL ships with its own JRE. No system Java required.

**File Permissions**: Ensure `COMSOL_TEMP_DIR` is writable:
```bash
mkdir -p /scratch/comsol_tmp
chmod 777 /scratch/comsol_tmp  # Or use appropriate user/group
```

**Headless Mode**: For HPC clusters without X11:
```bash
export COMSOL_GRAPHICS=off  # Before starting Python
```

### macOS

**Apple Silicon (M1/M2/M3)**: COMSOL runs via Rosetta 2. Install Rosetta if not already present:
```bash
softwareupdate --install-rosetta
```

**Gatekeeper**: First launch may require security approval:
```bash
sudo xattr -rd com.apple.quarantine /Applications/COMSOL62
```

## Troubleshooting

### "COMSOL installation not found"

1. Check installation:
   ```bash
   # Windows
   dir "C:\Program Files\COMSOL"

   # Linux/macOS
   ls /usr/local/comsol* /opt/comsol* /Applications/COMSOL*
   ```

2. Set `COMSOL_ROOT` explicitly:
   ```python
   from comsol_toolkit import COMSOLInterface
   comsol = COMSOLInterface(comsol_root="/custom/path")
   ```

### "JPype JVMNotFoundException"

COMSOL's JRE not found. Set `JAVA_HOME` to COMSOL's JRE:

```bash
# Windows
$env:JAVA_HOME = "C:\Program Files\COMSOL\COMSOL62\Multiphysics\java\win64\jre"

# Linux
export JAVA_HOME=/usr/local/comsol62/multiphysics/java/glnxa64/jre

# macOS
export JAVA_HOME=/Applications/COMSOL62/Multiphysics.app/java/maci64/jre
```

### "License checkout failed"

1. Check license server:
   ```bash
   # COMSOL license utility
   comsol -showlic
   ```

2. Verify network license file (for floating licenses):
   ```bash
   # Linux/macOS: check ~/.comsol/v62/license.dat
   # Windows: check %USERPROFILE%\.comsol\v62\license.dat
   ```

### Slow startup (Windows)

Windows Defender Real-time Protection scans COMSOL Java files on startup. Add exclusions:
1. Open Windows Security → Virus & threat protection → Manage settings
2. Add exclusions for:
   - `C:\Program Files\COMSOL`
   - `%TEMP%\comsol_toolkit` (or your `COMSOL_TEMP_DIR`)

## Testing Cross-Platform

Run the test suite on your platform:

```bash
# With COMSOL installed
pytest tests/ -v

# Mock mode (no COMSOL required)
pytest tests/ --mock-comsol -v
```

## Performance Tips

### Parallel Execution

For parametric sweeps, increase `max_workers` based on license availability:

```python
from comsol_toolkit import ParametricSweep

sweep = ParametricSweep(...)
results = sweep.run(
    parallel=4,  # Number of concurrent COMSOL instances
    output_dir="results/"
)
```

**License limits**: Check your license terms. Most floating licenses allow 1-4 concurrent instances.

### Temp Directory

Use a fast local disk for `COMSOL_TEMP_DIR`:
- **Windows**: Local SSD (e.g., `D:\comsol_tmp`)
- **Linux**: `/tmp` (RAM disk) or `/scratch` (fast SSD)
- **HPC clusters**: Node-local storage (not NFS)

### Memory Settings

For large models, increase COMSOL Java heap:

```python
from comsol_toolkit import COMSOLInterface

comsol = COMSOLInterface(
    jvm_args=["-Xmx16G"]  # 16 GB heap
)
```

## Next Steps

- [API Reference](api.md)
- [Plugin Development](plugins.md)
- [Examples](../examples/)
