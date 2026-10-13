---
name: trans-pdf
description: 当用户提供 PDF 地址，并要求把 PDF 翻译成中文时使用此技能
---

你将收到一个 PDF 文件的地址，例如：

/home/lin/papers/some-paper.pdf

## 第 1 步：创建 XeLaTeX 工程目录

将该 PDF 转换为一个多文件的 XeLaTeX 工程，输出到 `./docs/{pdf_name}-CN` 中。工程结构如下：

- `main.tex` — 入口文件
- `preamble.tex` — 导言区（字体、宏包等设置）
- 每章一个 `.tex` 文件
- `figures/` — 图片资源目录

字体要求（两个 Skill 统一使用同一套字体，与 `trans-arxiv-paper` 共用，位于 `.claude/skills/fonts/`）：
- 西文 / 正文 / 等宽：`Cascadia Mono`（字体文件位于 `fonts/CascadiaMono/`，含 Light / Regular / SemiBold / Bold 等字重；无独立斜体文件，编译时用 FakeSlant 生成倾斜）
- 中文 / 无衬线：`HarmonyOS Sans SC`（字体文件位于 `fonts/HarmonyOSSans/`）
- 编译前需把字体复制进工程：`cp -r {SKILL_DIR}/../fonts ./{pdf_name}-CN/`

## 第 2 步：提取图像（区分来源，校正方向）

按图片来源分别处理：

- **位图**：用 `pdfimages` 提取原始图像流。
- **矢量图**：用 PyMuPDF 按"图标题区域"渲染。

方向校正：用页面变换矩阵判定旋转/镜像，与显示矩形比对验证后再保存。

每张图的渲染边界规则：
- 以 `Figure X.Y:` 标题为下界（须带冒号、位于行首，排除正文中的引用）
- 上一标题为上界
- 横向取整页文本宽度
- 渲染为单张完整图（含全部子图）

## 第 3 步：处理图像引用与算法

- 每个 `\includegraphics` 必须显式指定 `width`（≤0.85\textwidth），禁止无尺寸选项或超宽。
- 算法/伪代码使用 `algorithm` 环境而非 `figure`，不得占用图编号。

## 第 4 步：处理表格

含示意图的复杂表格（如拓扑/分类表）整块渲染为图像替换，勿改写为纯文字。

## 第 5 步：翻译为简体中文

将正文译为简体中文，要求如下：

- 术语全书统一（专业术语首次出现时括注英文）。
- 公式逐条用 LaTeX 排版并加 `\label`，不得省略或改写数学内容。

## 第 6 步：编译 PDF

使用 `xelatex` 编译两遍，输出最终 PDF。

未安装时通过 `conda install tectonic` 或对应发行版方式获取 xelatex 工具链。

## 第 7 步：交付前自检并修复

确认 0 编译错误后再输出。重点检查并修复以下问题：

- 多子图重复
- 图内容缺失/截断
- 算法冒占图号
- 缺尺寸/超宽图
- 未定义引用
