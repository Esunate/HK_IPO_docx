# Windows + WSL 部署指南

本文档说明如何在 Windows 系统上部署本项目，并使用 WSL (Windows Subsystem for Linux) 进行开发。

---

## 前置要求

- Windows 10 版本 2004 及以上（内部版本 19041 及以上）或 Windows 11
- 管理员权限
- 至少 20GB 可用磁盘空间
- 8GB 以上内存（推荐 16GB）

---

## Phase 1: Windows 环境准备

### 1.1 启用 WSL

以管理员身份打开 PowerShell，运行：

```powershell
# 启用 WSL
wsl --install

# 重启电脑后，设置 WSL 默认版本为 2
wsl --set-default-version 2
```

### 1.2 安装 Ubuntu (WSL)

```powershell
# 查看可用的 Linux 发行版
wsl --list --online

# 安装 Ubuntu 22.04
wsl --install -d Ubuntu-22.04

# 设置 Ubuntu 为默认发行版
wsl --set-default Ubuntu-22.04
```

### 1.3 配置 WSL 资源

创建/编辑 `C:\Users\<你的用户名>\.wslconfig`：

```ini
[wsl2]
memory=16GB
processors=8
swap=4GB
localhostForwarding=true
```

然后重启 WSL：

```powershell
wsl --shutdown
```

---

## Phase 2: WSL 环境配置

### 2.1 更新系统

打开 WSL Ubuntu 终端，运行：

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2 安装基础依赖

```bash
sudo apt install -y \
    git \
    curl \
    wget \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    llvm \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    unzip
```

### 2.3 安装 Python 3.11

```bash
# 添加 deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# 安装 Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# 设置 Python 3.11 为默认版本
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# 验证安装
python --version
```

### 2.4 安装 uv (Python 包管理器)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# 添加 uv 到 PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 验证安装
uv --version
```

---

## Phase 3: 项目迁移

### 3.1 在 Windows 上准备项目文件

将项目文件夹复制到 Windows 的合适位置，例如：

```
C:\Projects\HK_IPO_docx\
```

### 3.2 在 WSL 中访问 Windows 文件

WSL 会自动挂载 Windows 磁盘，路径为 `/mnt/`：

```bash
# 进入项目目录
cd /mnt/c/Projects/HK_IPO_docx

# 或者将项目复制到 WSL 内部（推荐，性能更好）
cp -r /mnt/c/Projects/HK_IPO_docx ~/HK_IPO_docx
cd ~/HK_IPO_docx
```

### 3.3 创建 Python 虚拟环境

```bash
# 使用 uv 创建虚拟环境
uv venv

# 激活虚拟环境
source .venv/bin/activate
```

---

## Phase 4: MinerU 安装

### 4.1 安装 MinerU

```bash
# 确保在虚拟环境中
source .venv/bin/activate

# 安装 MinerU (带所有依赖)
uv pip install -U "mineru[all]"
```

### 4.2 下载模型文件

```bash
# 下载 MinerU 所需的模型
python -c "from mineru.cli.models_download import main; main([])"
```

模型文件将下载到 `~/.cache/mineru/` 目录。

### 4.3 验证安装

```bash
# 测试 MinerU 是否正常工作
mineru --help
```

---

## Phase 5: Codex CLI 安装

### 5.1 安装 Node.js

```bash
# 安装 nvm (Node 版本管理器)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 重新加载配置
source ~/.bashrc

# 安装 Node.js 20
nvm install 20
nvm use 20

# 验证安装
node --version
npm --version
```

### 5.2 安装 Codex CLI

```bash
# 安装 Codex CLI
npm install -g @openai/codex

# 验证安装
codex --version
```

### 5.3 配置 OpenAI API Key

```bash
# 设置环境变量
export OPENAI_API_KEY="your-api-key-here"

# 添加到 ~/.bashrc 使其永久生效
echo 'export OPENAI_API_KEY="your-api-key-here"' >> ~/.bashrc
```

---

## Phase 6: 项目配置

### 6.1 安装项目依赖

```bash
# 在项目根目录下
cd ~/HK_IPO_docx

# 激活虚拟环境
source .venv/bin/activate

# 安装开发依赖
uv pip install pytest pytest-cov

# 安装其他需要的包
uv pip install lxml pysbd python-docx
```

### 6.2 创建项目配置文件

创建 `.env` 文件：

```bash
cat > .env << EOF
# OpenAI API Key
OPENAI_API_KEY=your-api-key-here

# 项目配置
PROJECT_ROOT=/home/$(whoami)/HK_IPO_docx
OUTPUT_DIR=/home/$(whoami)/HK_IPO_docx/output
EOF
```

---

## Phase 7: 测试验证

### 7.1 测试 MinerU

```bash
# 创建一个测试 PDF 目录
mkdir -p ~/HK_IPO_docx/test_pdfs

# 复制一个测试 PDF
cp ~/HK_IPO_docx/docx/*.pdf ~/HK_IPO_docx/test_pdfs/ 2>/dev/null || echo "请手动复制测试 PDF"

# 运行测试转换
mineru -p ~/HK_IPO_docx/test_pdfs/test.pdf -o ~/HK_IPO_docx/test_output -l en -b pipeline
```

### 7.2 测试 Codex CLI

```bash
# 进入项目目录
cd ~/HK_IPO_docx

# 启动 Codex
codex

# 或者在项目目录下直接运行
codex "请帮我查看项目结构"
```

### 7.3 运行项目测试

```bash
# 运行 pytest 测试
cd ~/HK_IPO_docx
source .venv/bin/activate
pytest tests/ -v
```

---

## Phase 8: 开发工作流

### 8.1 日常开发流程

```bash
# 1. 打开 WSL 终端
# 2. 进入项目目录
cd ~/HK_IPO_docx

# 3. 激活虚拟环境
source .venv/bin/activate

# 4. 启动 Codex 进行开发
codex

# 或者直接在 VS Code 中使用 WSL 远程开发
```

### 8.2 VS Code + WSL 开发（推荐）

1. 在 Windows 上安装 VS Code
2. 安装 "WSL" 扩展
3. 在 VS Code 中按 `Ctrl+Shift+P`，输入 "WSL: Connect to WSL"
4. 选择你的 Ubuntu 发行版
5. 在 VS Code 中打开项目文件夹

---

## 常见问题解决

### Q1: WSL 安装失败

```powershell
# 手动启用 WSL 功能
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# 重启后安装 WSL 内核更新包
# 下载地址：https://aka.ms/wsl2kernel
```

### Q2: MinerU 模型下载失败

```bash
# 手动下载模型
mkdir -p ~/.cache/mineru
# 从 GitHub 或其他源手动下载模型文件到该目录
```

### Q3: 内存不足

```ini
# 编辑 .wslconfig 文件，减少内存分配
[wsl2]
memory=8GB
processors=4
swap=2GB
```

### Q4: 文件权限问题

```bash
# 修复文件权限
sudo chown -R $USER:$USER ~/HK_IPO_docx
chmod -R 755 ~/HK_IPO_docx
```

---

## 性能优化建议

1. **使用 WSL 内部存储**：将项目复制到 WSL 内部 (`~/HK_IPO_docx`) 比访问 Windows 文件系统 (`/mnt/c/`) 性能更好
2. **配置足够的内存**：MinerU 处理大 PDF 需要较多内存，建议分配 8GB 以上
3. **使用 SSD**：确保 WSL 安装在 SSD 上以提高 I/O 性能
4. **定期清理缓存**：`wsl --shutdown` 后重启可以清理内存缓存

---

## 下一步

完成部署后，你可以：

1. 使用 MinerU 转换 PDF 文件
2. 使用 Codex CLI 进行 AI 辅助开发
3. 运行项目测试验证功能
4. 开始开发招股书句子拆分工具

参考项目文档：
- [项目规格说明书](.trae/documents/prospectus_sentence_indexer_spec.md)
- [任务清单](.trae/documents/prospectus_sentence_indexer_tasks.md)
- [验收检查清单](.trae/documents/prospectus_sentence_indexer_checklist.md)