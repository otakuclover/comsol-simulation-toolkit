# COMSOL Simulation Toolkit

[English](#english) | [中文](#中文)

---

## English

Cross-platform Python toolkit for automated COMSOL Multiphysics workflows: eigenfrequency studies, modal analysis, and parametric sweeps.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![COMSOL 6.x](https://img.shields.io/badge/COMSOL-6.x-green.svg)](https://www.comsol.com/)

### Features

✅ **Cross-Platform**: Auto-detect COMSOL on Windows/Linux/macOS  
✅ **Environment-Based Config**: `.env` file support with sensible defaults  
✅ **Low-Level COMSOL Helpers**: JPype wrappers for eigenfrequency studies, modal matrices, field extraction  
✅ **Graceful Degradation**: Clear error messages when COMSOL not found  

⚠️ **Note**: High-level interfaces (`COMSOLInterface`, `ParametricSweep`) are under development. Use `comsol_helpers` directly for production work.

### Requirements

| Component | Version |
|-----------|---------|
| **COMSOL Multiphysics** | 6.x (5.x may work) |
| **Python** | 3.9+ (NOT Microsoft Store version) |
| **Java Runtime** | Required by MPh/COMSOL |

### Installation

```bash
# Clone repository
git clone https://github.com/WHU_Clover/comsol-simulation-toolkit.git
cd comsol-simulation-toolkit

# Install with pip
pip install -e .

# Or install with optional dependencies
pip install -e ".[dev,hdf5,visualization]"
```

### Quick Start

#### 1. Configuration

Create `.env` file in your project:

```bash
# Optional: COMSOL auto-detects if not set
COMSOL_ROOT=C:/Program Files/COMSOL/COMSOL64/Multiphysics

# Optional: Defaults to system temp
COMSOL_TEMP_DIR=./temp_comsol

# Optional: For project-specific paths
SIMULATION_PROJECT_DIR=./my_project
SIMULATION_RESULTS_DIR=./results
```

Or use environment variables directly.

#### 2. Basic Usage

```python
from comsol_toolkit import load_config, start_comsol_client
from comsol_toolkit import create_eigen_study, eval_eigenfrequencies

# Load configuration
config = load_config()

# Start COMSOL client
from mph import session
session.client = None
client = start_comsol_client(config)

# Load model
model = client.load("path/to/model.mph")
j = model.java

# Create eigenfrequency study
create_eigen_study(
    model_java=j,
    study_tag="eig1",
    search_freq="5.0[GHz]",
    num_modes=24,
    eigwhich="lr"  # Largest real part
)

# Run study
j.study("eig1").run()

# Extract eigenfrequencies
from comsol_toolkit import latest_tag, tags
data_tag = latest_tag(tags(j.result().dataset()), ["dset1"])
eigenfreqs = eval_eigenfrequencies(j, data_tag, num_modes=24)

print(f"Found {len(eigenfreqs)} modes")
for i, freq in enumerate(eigenfreqs, 1):
    print(f"Mode {i}: {freq:.6f} Hz")
```

#### 3. Available Functions

**Configuration**:
- `load_config()` - Load from environment/`.env`
- `auto_detect_comsol_root()` - Find COMSOL installation

**COMSOL Helpers**:
- `init_comsol_runtime()` - Initialize COMSOL Java runtime
- `start_comsol_client()` - Start MPh client
- `create_eigen_study()` - Create eigenfrequency study
- `eval_eigenfrequencies()` - Extract eigenvalues
- `jint()`, `jdouble_2d()` - JPype type conversion
- `tags()`, `remove_if_exists()` - COMSOL model utilities
- `parse_interp_data()` - Parse interpolation data

See [API Reference](#api-reference) for details.

### Cross-Platform Support

#### Windows
```bash
# COMSOL auto-detected from:
# C:/Program Files/COMSOL/COMSOL*/Multiphysics
# C:/Program Files (x86)/COMSOL/COMSOL*/Multiphysics
```

#### Linux
```bash
# COMSOL auto-detected from:
# /usr/local/comsol*/multiphysics
# /opt/comsol*/multiphysics
```

#### macOS
```bash
# COMSOL auto-detected from:
# /Applications/COMSOL*/Multiphysics.app

# Note: Rosetta 2 required for Apple Silicon
```

### Project Structure

```
comsol_toolkit/
├── config.py              # Configuration management
├── comsol_helpers.py      # Low-level COMSOL wrappers
├── comsol_interface.py    # ⚠️ Experimental high-level API
├── modal_matrix.py        # Modal analysis utilities
└── io_utils.py            # I/O utilities

tests/
└── test_cross_platform.py # Cross-platform tests

docs/
└── cross_platform.md      # Detailed setup guide
```

### Development Status

| Component | Status |
|-----------|--------|
| Config system | ✅ Stable |
| COMSOL helpers | ✅ Stable |
| Modal matrix utils | ✅ Stable |
| Cross-platform support | ✅ Tested |
| High-level interface | ⚠️ Experimental (mock outputs) |
| CLI tools | 📋 Planned |
| Documentation | 🚧 In progress |

### API Reference

#### Configuration

```python
from comsol_toolkit import load_config, COMSOLConfig

# Load from environment
config = load_config()

# Or create manually
config = COMSOLConfig(
    comsol_root="/path/to/COMSOL/Multiphysics",
    temp_dir="./temp",
    max_workers=8
)

# Validate
config.validate()  # Raises RuntimeError if COMSOL not found
```

#### COMSOL Client

```python
from comsol_toolkit import start_comsol_client
from mph import session

session.client = None
client = start_comsol_client()

# Load model
model = client.load("model.mph")

# Access Java API
j = model.java
```

#### Eigenfrequency Study

```python
from comsol_toolkit import create_eigen_study, eval_eigenfrequencies

# Create study
create_eigen_study(
    model_java=j,
    study_tag="eig1",
    search_freq="5.0[GHz]",  # Search near 5 GHz
    num_modes=24,            # Number of modes
    eigwhich="lr"            # Largest real (use "sm" for smallest magnitude)
)

# Run
j.study("eig1").run()

# Extract results
eigenfreqs = eval_eigenfrequencies(j, dataset_tag, num_modes=24)
```

### Troubleshooting

**ImportError: mph not found**
```bash
pip install mph
```

**RuntimeError: COMSOL installation not found**
```bash
# Set environment variable
export COMSOL_ROOT=/path/to/COMSOL/Multiphysics

# Or in .env file
COMSOL_ROOT=/path/to/COMSOL/Multiphysics
```

**JPype errors**
```bash
# Ensure Java is installed
java -version

# Reinstall JPype
pip install --force-reinstall JPype1
```

**Tests failing**
```bash
# Run tests without COMSOL
pytest -m "not requires_comsol"

# Run all tests (requires COMSOL)
pytest
```

### Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure `pytest` passes
5. Submit a pull request

### License

MIT License - see [LICENSE](LICENSE) for details.

### Citation

```bibtex
@software{comsol_simulation_toolkit,
  title = {COMSOL Simulation Toolkit},
  author = {WHU\_Clover},
  year = {2026},
  url = {https://github.com/WHU_Clover/comsol-simulation-toolkit}
}
```

### Acknowledgments

- Built on [MPh](https://github.com/MPh-py/MPh) for COMSOL Python interface
- Uses [JPype](https://github.com/jpype-project/jpype) for Java integration
- Inspired by RAFT-FEM research workflows

---

## 中文

跨平台 COMSOL Multiphysics 自动化 Python 工具包：特征频率研究、模态分析和参数扫描。

### 特性

✅ **跨平台**：自动检测 Windows/Linux/macOS 上的 COMSOL 安装  
✅ **环境变量配置**：支持 `.env` 文件，提供合理默认值  
✅ **底层 COMSOL 封装**：JPype 封装的特征频率研究、模态矩阵、场提取功能  
✅ **优雅降级**：COMSOL 未找到时提供清晰错误信息  

⚠️ **注意**：高层接口（`COMSOLInterface`、`ParametricSweep`）正在开发中。生产环境请直接使用 `comsol_helpers`。

### 系统要求

| 组件 | 版本 |
|------|------|
| **COMSOL Multiphysics** | 6.x（5.x 可能可用） |
| **Python** | 3.9+（不要使用 Microsoft Store 版本） |
| **Java 运行时** | MPh/COMSOL 需要 |

### 安装

```bash
# 克隆仓库
git clone https://github.com/WHU_Clover/comsol-simulation-toolkit.git
cd comsol-simulation-toolkit

# 使用 pip 安装
pip install -e .

# 或安装可选依赖
pip install -e ".[dev,hdf5,visualization]"
```

### 快速开始

#### 1. 配置

在项目目录创建 `.env` 文件：

```bash
# 可选：如果不设置会自动检测 COMSOL
COMSOL_ROOT=C:/Program Files/COMSOL/COMSOL64/Multiphysics

# 可选：默认使用系统临时目录
COMSOL_TEMP_DIR=./temp_comsol

# 可选：项目特定路径
SIMULATION_PROJECT_DIR=./my_project
SIMULATION_RESULTS_DIR=./results
```

或直接使用环境变量。

#### 2. 基本使用

```python
from comsol_toolkit import load_config, start_comsol_client
from comsol_toolkit import create_eigen_study, eval_eigenfrequencies

# 加载配置
config = load_config()

# 启动 COMSOL 客户端
from mph import session
session.client = None
client = start_comsol_client(config)

# 加载模型
model = client.load("path/to/model.mph")
j = model.java

# 创建特征频率研究
create_eigen_study(
    model_java=j,
    study_tag="eig1",
    search_freq="5.0[GHz]",
    num_modes=24,
    eigwhich="lr"  # 最大实部
)

# 运行研究
j.study("eig1").run()

# 提取特征频率
from comsol_toolkit import latest_tag, tags
data_tag = latest_tag(tags(j.result().dataset()), ["dset1"])
eigenfreqs = eval_eigenfrequencies(j, data_tag, num_modes=24)

print(f"找到 {len(eigenfreqs)} 个模态")
for i, freq in enumerate(eigenfreqs, 1):
    print(f"模态 {i}: {freq:.6f} Hz")
```

#### 3. 可用函数

**配置**：
- `load_config()` - 从环境变量/`.env` 加载
- `auto_detect_comsol_root()` - 查找 COMSOL 安装

**COMSOL 辅助函数**：
- `init_comsol_runtime()` - 初始化 COMSOL Java 运行时
- `start_comsol_client()` - 启动 MPh 客户端
- `create_eigen_study()` - 创建特征频率研究
- `eval_eigenfrequencies()` - 提取特征值
- `jint()`, `jdouble_2d()` - JPype 类型转换
- `tags()`, `remove_if_exists()` - COMSOL 模型工具
- `parse_interp_data()` - 解析插值数据

详见 [API 参考](#api-reference)。

### 跨平台支持

#### Windows
```bash
# COMSOL 自动检测路径：
# C:/Program Files/COMSOL/COMSOL*/Multiphysics
# C:/Program Files (x86)/COMSOL/COMSOL*/Multiphysics
```

#### Linux
```bash
# COMSOL 自动检测路径：
# /usr/local/comsol*/multiphysics
# /opt/comsol*/multiphysics
```

#### macOS
```bash
# COMSOL 自动检测路径：
# /Applications/COMSOL*/Multiphysics.app

# 注意：Apple Silicon 需要 Rosetta 2
```

### 项目结构

```
comsol_toolkit/
├── config.py              # 配置管理
├── comsol_helpers.py      # 底层 COMSOL 封装
├── comsol_interface.py    # ⚠️ 实验性高层 API
├── modal_matrix.py        # 模态分析工具
└── io_utils.py            # I/O 工具

tests/
└── test_cross_platform.py # 跨平台测试

docs/
└── cross_platform.md      # 详细安装指南
```

### 开发状态

| 组件 | 状态 |
|------|------|
| 配置系统 | ✅ 稳定 |
| COMSOL 辅助函数 | ✅ 稳定 |
| 模态矩阵工具 | ✅ 稳定 |
| 跨平台支持 | ✅ 已测试 |
| 高层接口 | ⚠️ 实验性（模拟输出） |
| CLI 工具 | 📋 计划中 |
| 文档 | 🚧 进行中 |

### 故障排除

**ImportError: mph not found**
```bash
pip install mph
```

**RuntimeError: COMSOL installation not found**
```bash
# 设置环境变量
export COMSOL_ROOT=/path/to/COMSOL/Multiphysics

# 或在 .env 文件中
COMSOL_ROOT=/path/to/COMSOL/Multiphysics
```

**JPype 错误**
```bash
# 确保已安装 Java
java -version

# 重新安装 JPype
pip install --force-reinstall JPype1
```

**测试失败**
```bash
# 运行不需要 COMSOL 的测试
pytest -m "not requires_comsol"

# 运行所有测试（需要 COMSOL）
pytest
```

### 贡献

欢迎贡献！请：
1. Fork 仓库
2. 创建功能分支
3. 为新功能添加测试
4. 确保 `pytest` 通过
5. 提交 pull request

### 许可证

MIT License - 详见 [LICENSE](LICENSE)

### 引用

```bibtex
@software{comsol_simulation_toolkit,
  title = {COMSOL Simulation Toolkit},
  author = {WHU\_Clover},
  year = {2026},
  url = {https://github.com/WHU_Clover/comsol-simulation-toolkit}
}
```

### 致谢

- 基于 [MPh](https://github.com/MPh-py/MPh) 构建 COMSOL Python 接口
- 使用 [JPype](https://github.com/jpype-project/jpype) 进行 Java 集成
- 受 RAFT-FEM 研究工作流启发