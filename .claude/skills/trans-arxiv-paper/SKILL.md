---
name: trans-arxiv-paper
description: 将 arXiv 论文翻译为简体中文 PDF。用户提供 arXiv URL/ID 或论文标题、说「翻译论文」「我想读中文版」等时使用。流程：下载 TeX 源码 → 重写为中文 XeLaTeX 工程 → 本地 tectonic 编译。支持多篇。
---

# arXiv 论文中文翻译（重写式 · 本地编译）

**目标：** 将指定论文的 LaTeX 源码译为简体中文，并用**本地 tectonic**（xetex 引擎）编译得到 PDF。

**流程：** 严格按「第一步」至「第四步」顺序执行，不得擅自省略、合并或调换。

**交互：** 仅当论文 ID 无法确定、或检索结果有多个需用户择一时才提问；其余情况一律无中断执行到产出 PDF。

**翻译：** 全部由当前对话模型完成，**严禁**使用外部翻译工具或下载已有译本。

**字体：** 西文/正文/等宽用 `Cascadia Mono`，中文/无衬线用 `HarmonyOS Sans SC`（两款字体与 `trans-pdf` 统一共用同一套，位于 `.claude/skills/fonts/`，随工程复制到 `fonts/`）。

---

## 第一步：确定论文 ID

- arXiv URL / ID → 直接提取 ID（如 `https://arxiv.org/abs/1706.03762` → `1706.03762`）。
- 仅给出论文标题 → 搜索 arXiv 找到 ID；找不到时给候选让用户确认。

---

## 第二步：获取源码并确定翻译范围

```bash
python3 {SKILL_DIR}/scripts/download.py "{PAPER_ID}"
```

`download.py` 一步完成：按 ID 取标题 → 清洗成 `{名}`（去空格/标点，如 `AttentionIsAllYouNeed`）→ 下载解压到 `/tmp/papers/{名}` → 定位主 `.tex`。

脚本向 stdout 输出三行：
```
WORK_DIR='/tmp/papers/{名}'      # 源码目录绝对路径
MAIN_TEX='{主文件}'              # 如 ms.tex / main.tex
NAME='{名}'                      # 论文名，用于输出目录
```

**无源码（仅 PDF）**：脚本会报错退出。此时告知用户该论文无 TeX 源码，改用 `trans-pdf` 技能处理。

---

## 第三步：翻译（重写式）

在 `./docs/{NAME}-CN/` 新建工程，**不要原地改源码**：

### 3.1 复制资源
从 `WORK_DIR` 复制到 `./docs/{NAME}-CN/`：
- 图片目录（`Figures/`、`figures/`、`vis/` 等）；
- **参考文献原样复用**：若源码有 `.bbl`，复制它并保留 `\bibliography{...}`；若仅 `\bibliography{xxx}` + `xxx.bib` 而无 `.bbl`，复制 `.bib` 并保留 `\bibliography{xxx}`（tectonic 会自动跑 bibtex）；若有手写的 `\begin{thebibliography}...\end{thebibliography}`，整块复制——**任何情况都不要手敲参考文献**；
- 论文自带的自定义样式（`*.sty` / `*.cls` / `*.bst`，如 `nips_2017.sty`）；
- 复制自带字体：`cp -r {SKILL_DIR}/../fonts ./docs/{NAME}-CN/`（字体与 `trans-pdf` 共用，位于 `.claude/skills/fonts/`）。

### 3.2 新建 `main.tex`，套用 preamble 模板
直接复制下方模板（已在 `docs/1706.03762-CN` 验证可编译）。仅按需调整 `\documentclass`、自定义命令、宏包：

```latex
% !TEX program = xelatex
\documentclass[11pt]{article}
\usepackage{fontspec}
\usepackage{xeCJK}                       % 注意：不要加 [fontset=...]

% 西文 / 正文 / 等宽：Cascadia Mono（无独立斜体文件，用 FakeSlant 生成倾斜）
\setmainfont{CascadiaMonoRegular}[
  Path = fonts/CascadiaMono/ , Extension = .ttf , UprightFont = * ,
  BoldFont = CascadiaMonoBold ,
  ItalicFont = CascadiaMonoRegular , ItalicFeatures = { FakeSlant = 0.2 } ,
  BoldItalicFont = CascadiaMonoBold , BoldItalicFeatures = { FakeSlant = 0.2 } ]
\setmonofont{CascadiaMonoRegular}[ Path = fonts/CascadiaMono/ , Extension = .ttf , UprightFont = * , BoldFont = CascadiaMonoBold ]
% 无衬线：HarmonyOS Sans SC（与中文一致）
\setsansfont{HarmonyOS_Sans_SC}[ Path = fonts/HarmonyOSSans/ , Extension = .ttf , UprightFont = * , BoldFont = HarmonyOS_Sans_SC_Bold ]

% 中文：HarmonyOS Sans SC（AutoFakeBold 补粗体）
\setCJKmainfont{HarmonyOS_Sans_SC}[ Path = fonts/HarmonyOSSans/ , Extension = .ttf , UprightFont = * , AutoFakeBold = 2.5 ]
\setCJKsansfont{HarmonyOS_Sans_SC}[ Path = fonts/HarmonyOSSans/ , Extension = .ttf , UprightFont = * , AutoFakeBold = 2.5 ]
\setCJKmonofont{HarmonyOS_Sans_SC}[ Path = fonts/HarmonyOSSans/ , Extension = .ttf , UprightFont = * ]

\usepackage{amsmath, amssymb, amsfonts}
\usepackage[a4paper, margin=1in]{geometry}
\usepackage{booktabs, multirow, graphicx, xcolor, hyperref, url, natbib}
\linespread{1.15}
% 注意：原论文若有 \usepackage[utf8]{inputenc} / [T1]{fontenc}，一律注释掉。
```

### 3.3 翻译规则

- **范围**：默认翻译全文
- **必须翻译**：正文叙述、摘要、图表标题（`\caption{}`）、列表项、脚注描述、代码块注释。
- **保留不翻**：数学环境、LaTeX 命令、`\cite{}`/`\ref{}`/`\label{}`、图片路径、URL、代码本体、`.bib`/参考文献条目、人名、机构名、模型名、数据集名。
- **专有名词**：Transformer、Softmax、Token、BLEU、attention 等通用学术术语保留英文，不要硬译。
- **标题**：`\title{}` 译为自然中文题名（**不**保留英文原题或中英并列）。

### 3.3.1 并行翻译（默认开启 subagent 加速）

**默认用并行 subagent 翻译，不要再顺序单线程做。** 重写式工程天然适合并行——各章节是独立 `.tex` 文件，可分派给多个 subagent 同时翻译：

1. 主 Agent 先读 `MAIN_TEX`，列出待译章节文件清单（`\input`/`\include` 引用的各文件，外加 `MAIN_TEX` 内的摘要/标题）。
2. **一条消息里**并行启动多个 subagent，每个负责 1～2 个章节文件：把原文片段 + 上方「3.3 翻译规则」+ preamble 模板一并交给它，让它直接产出译好的 `.tex` 段落到 `./docs/{NAME}-CN/`。所有 subagent 共用同一份规则，保证术语一致。
3. 主 Agent 负责收口：组装 `main.tex`（套 preamble 模板 + `\input{}` 各译好章节）、复用参考文献（3.1）、复制资源与字体。
4. 单篇论文编译是单条 `tectonic` 命令，无需也不能并行；**多篇论文**时各篇独立，可整篇并行（下载/翻译/编译分别 fan-out）。

子代理数量按章节规模定（一般 3～6 个即可），过多反而增加组装开销。

### 3.4 自检（编译前必做的本地检查）

翻译后必须运行（纯本地脚本，不联网、非网关）：

```bash
python3 {SKILL_DIR}/scripts/inspect_tex.py scan "./docs/{NAME}-CN" "main.tex" body
```

（用户要全文翻译时把 `body` 换成 `full`。）

脚本输出 `SUSPECT_COUNT=<n>` 及若干 `SUSPECT=<文件>:<行号>:<片段>`：
- 只要 `SUSPECT_COUNT` 非 0，就必须逐条回到对应位置翻译；
- 只有 `SUSPECT_COUNT=0`，或剩余项明确属于「保留不翻」范围（专有名词、人名等）时，才可进入第四步。

---

## 第四步：编译（本地 tectonic）

```bash
cd ./docs/{NAME}-CN && tectonic main.tex
```

tectonic 自动多遍编译解析引用，并按需从 CTAN 自动抓取缺失宏包。

- **失败**：读输出中以 `!` / `error:` 开头的首个错误，参考 `{SKILL_DIR}/references/compile-errors.md` 修复源码后重编译（最多重试 2 次）。
- **成功**：输出 `main.pdf`。向用户报告 PDF 路径。

---

## 多篇论文
**默认并行**：多篇论文各自独立，可整篇并行 fan-out（下载 / 翻译 / 编译分别并行）。单篇内的章节翻译也默认并行（见 3.3.1）。

## 参考文件
- `references/compile-errors.md`：tectonic + xeCJK 编译常见错误及修复方法。
