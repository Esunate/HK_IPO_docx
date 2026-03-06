# HK IPO Prospectus Sentence Indexer

一个面向招股书/行业报告 PDF、Word 文档的句子索引工具。

这个工程的目标是：
- 调用 `MinerU` 解析 `pdf` / `doc` / `docx`
- 把解析结果整理成结构化 `Block`
- 按段落切句，并做基础 QA 检查
- 导出为可复核的 `CSV`、`DOCX`、`JSON`

当前工程已经针对 `MinerU content_list.json` 做了若干兼容，尤其是：
- `type="text"` 文本块
- `type="list"` 且 `sub_type="text"` 的列表文本块
- `list_text` / `list_body` / `list_items` / `items` / `children` 等常见文本字段

## 目录结构

- `prospectus_sentence_indexer/cli.py`：命令行入口
- `prospectus_sentence_indexer/mineru.py`：MinerU 调用与 `content_list.json` 解析
- `prospectus_sentence_indexer/segment.py`：英文句子切分
- `prospectus_sentence_indexer/qa.py`：句子级 QA 标记
- `prospectus_sentence_indexer/export.py`：导出 `CSV` / `DOCX` / `summary.json`
- `prospectus_sentence_indexer/models.py`：核心数据结构
- `tests/`：单元测试与集成测试
- `docx/`：样例输入文件
- `output/`：运行输出目录

## 处理流程

整体流程如下：

1. 输入 `pdf` / `doc` / `docx`
2. `doc` / `docx` 先通过 `soffice` 转成 `pdf`
3. 调用 `MinerU` 生成 `markdown` 与 `*_content_list.json`
4. 从 `content_list.json` 提取块级内容：
   - 标题 `heading`
   - 段落 `paragraph`
   - 图片 `image`
   - 表格 / 公式
5. 对段落做句子切分
6. 运行 QA 检查
7. 导出结果文件

## 输出文件

每次运行默认会在输出目录生成：

- `sentences.csv`：主结果，便于检索与二次处理
- `sentences.docx`：便于人工复核
- `qa_report.csv`：QA 问题列表
- `summary.json`：统计摘要
- `mineru_artifacts.json`：记录 MinerU 中间产物路径

`sentences.csv` 主要字段包括：
- `sentence_id`
- `block_id`
- `part`
- `block_type`
- `heading_level`
- `heading_path`
- `text`
- `image_path`
- `qa_flags`

说明：
- 标题行会单独保留，但 `sentence_id` 为空
- 图片会被当作一条句子记录
- 段落会被切成多句

## 环境说明

仓库里目前有两个虚拟环境：

- `.venv`：CPU 环境
- `.venv_torch`：带 `torch` / CUDA 的环境，适合跑 GPU 版 `MinerU`

如果要处理真实 PDF，优先使用 `.venv_torch`。

代理说明：
- 工具默认继承当前 shell 的代理环境变量，例如 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`
- 在这台机器上，`MinerU` 的模型加载/后处理可能依赖现有代理
- 不要在运行前手动清空这些代理变量，否则可能出现“GPU 预测已完成，但后续长时间无输出、看起来像卡在落盘阶段”的现象

## 依赖

核心依赖见 `requirements.txt`：
- `mineru`
- `python-docx`
- `pysbd`
- `lxml`
- `pandas`
- `pytest`
- `PyMuPDF`

如果输入是 Word 文档，还需要本机可用：
- `soffice`

### 本地模型配置

为了减少运行时联网，可以把 `MinerU` 切到本地模型模式。

当前机器已经配置好：`/home/ethan/mineru.json`

配置内容对应的本地模型目录为：
- `vlm`：`/home/ethan/.cache/huggingface/hub/models--opendatalab--MinerU2.5-2509-1.2B/snapshots/879e58bdd9566632b27a8a81f0e2961873311f67`
- `pipeline`：`/home/ethan/.cache/huggingface/hub/models--opendatalab--PDF-Extract-Kit-1.0/snapshots/1d9a3cd772329d0f83d84638a789296863f940f9`

启用方式：

```bash
export MINERU_MODEL_SOURCE=local
```

说明：
- 这会让 `MinerU` 优先使用 `~/mineru.json` 中配置的本地模型目录
- 可以显著减少运行时访问模型仓库的概率
- 建议与现有代理环境一起使用，以避免其他潜在联网步骤卡住

## 快速开始

### 1. 使用已有虚拟环境

CPU：

```bash
.venv/bin/python -m prospectus_sentence_indexer <input.pdf> --output-dir output/run_cpu
```

GPU：

```bash
.venv_torch/bin/python -m prospectus_sentence_indexer <input.pdf> \
  --output-dir output/run_gpu \
  --mineru-command .venv_torch/bin/mineru \
  --mineru-method auto \
  --mineru-lang en
```

说明：
- 默认继承当前终端里的代理配置
- 如果你本机访问模型仓库依赖代理，请直接在已有终端环境里运行，不要额外 `unset` 代理变量

示例：

```bash
.venv_torch/bin/python -m prospectus_sentence_indexer docx/'Project Star-IO.pdf' \
  --output-dir output/project_star_io_gpu \
  --mineru-command .venv_torch/bin/mineru \
  --mineru-method auto \
  --mineru-lang en
```

如果要优先使用本地模型缓存：

```bash
export MINERU_MODEL_SOURCE=local
.venv_torch/bin/python -m prospectus_sentence_indexer docx/'Project Star-IO.pdf' \
  --output-dir output/project_star_io_gpu_local \
  --mineru-command .venv_torch/bin/mineru \
  --mineru-method auto \
  --mineru-lang en
```

### 2. 运行测试

```bash
.venv_torch/bin/pytest -q
```

如果只跑 `MinerU` 解析相关测试：

```bash
.venv_torch/bin/pytest -q tests/test_mineru.py
```

## 命令行参数

入口在 `prospectus_sentence_indexer/cli.py`。

可用参数：
- `input_path`：输入文件路径，支持 `.doc` / `.docx` / `.pdf`
- `--output-dir`：输出目录，默认 `output`
- `--abbrev`：缩写白名单，可重复传入
- `--mineru-command`：MinerU 可执行文件路径，默认 `mineru`
- `--mineru-method`：`auto` / `txt` / `ocr`
- `--mineru-lang`：OCR / 文本语言，默认 `en`

示例：

```bash
.venv_torch/bin/python -m prospectus_sentence_indexer input.pdf \
  --output-dir output/demo \
  --abbrev Inc \
  --abbrev Ltd
```

## 代码设计要点

### 1. Block 模型

工程先把原始解析内容归一成 `Block`：
- `HEADING`
- `PARAGRAPH`
- `IMAGE`
- `TABLE`
- `EQUATION`

这让后续切句、QA、导出都能共用一套数据结构。

### 2. 标题路径

标题会维护 `heading_path`，例如：

```text
INDUSTRY OVERVIEW > Market Drivers > Satellite Internet
```

这样每句文本都能带上下文。

### 3. 句子切分

切句使用 `pysbd`，并做了两层保护：
- 缩写白名单修正
- reconstruct check

如果切分结果无法和原文重构一致，会退回整段作为单句，并打上 `RECONSTRUCT_FAIL` / `FALLBACK_SEGMENT`。

### 4. QA 标记

当前会检查：
- `TOO_SHORT`
- `TOO_LONG`
- `LOWERCASE_START`
- `NO_END_PUNCT`
- `MANY_SEMICOLONS`
- `ABBR_EDGE`
- `FALLBACK_SEGMENT`
- `RECONSTRUCT_FAIL`

## MinerU 兼容说明

`MinerU` 的 `content_list.json` 在不同版本/不同页面类型下，字段形态并不完全一致。

当前工程已兼容的文本型列表场景包括：

```json
{
  "type": "list",
  "sub_type": "text"
}
```

并会优先从以下字段提取文本：
- `text`
- `list_text`
- `list_body`
- `list_items`
- `items`
- `children`

其中 `list_items` 是当前真实样例 `Project Star-IO.pdf` 中实际出现的字段。

## 已验证样例

当前仓库内已验证过的样例包括：
- `docx/Project Star-IO.pdf`
- `docx/Star – Industry Overview – 0304.doc`

基于 `Project Star-IO.pdf` 的重处理结果可参考：
- `output/project_star_io_reprocess_current`

## 常见问题

### 1. `MinerU` 跑不起来

优先检查：
- 是否使用了正确虚拟环境
- `mineru` 是否可执行
- 模型是否已下载
- 网络代理是否影响 `huggingface` 下载
- GPU 环境是否能被 `torch.cuda.is_available()` 识别

补充：
- 如果日志里 `Predict` 已经跑完，但迟迟没有生成 `content_list.json` / `md` / `summary`，先不要只怀疑“落盘卡死”
- 这个工程的实际排查结果是：某些情况下 `MinerU` 会在后处理阶段继续访问外网资源
- 如果当前机器依赖本地代理，清空代理变量后就可能表现为“预测完成后卡住”

### 2. GPU 在系统里可见，但 Python 里不可用

建议检查：
- 是否用了 `.venv_torch`
- 当前 shell 是否带了异常代理或环境变量
- `torch` 与 CUDA 版本是否匹配

### 3. Word 转 PDF 失败

请确认本机安装了 LibreOffice，并且命令可用：

```bash
soffice --headless --version
```

## 后续可扩展方向

- 增加更多 `MinerU` 字段形态兼容
- 对表格文字内容做更细粒度抽取
- 增加英文以外语言的切句策略
- 增加更丰富的 QA 规则
- 支持复用已有 `content_list.json` 的独立重处理命令

## 开发建议

日常开发推荐：

```bash
.venv_torch/bin/pytest -q tests/test_mineru.py
```

如果改动了导出或 CLI，再补跑：

```bash
.venv_torch/bin/pytest -q tests/test_integration.py
```

