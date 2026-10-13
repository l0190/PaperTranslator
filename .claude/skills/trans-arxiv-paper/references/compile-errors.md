# 编译错误速查（tectonic + xeCJK）

本 skill 使用**本地 tectonic**（xetex 引擎）+ **xeCJK** 编译。tectonic 会自动按需从 CTAN 抓取缺失的宏包，因此"缺包"问题比传统 TeX Live 少；但 CJK 字体与原论文 preamble 的冲突仍常见。下面按报错关键词速查。

---

## 1. `xeCJK ... does not have a key called 'fontset'`

```
Package xeCJK Error: Sorry, but xeCJK/options does not have a key called `fontset'.
```

**原因**：旧写法 `\usepackage[fontset=none]{xeCJK}` 在新版 xeCJK 中已不支持。

**修复**：去掉选项，直接 `\usepackage{xeCJK}`，然后用 `\setCJKmainfont{...}` 手动指定字体（本 skill 正是这样做）。

---

## 2. `Font shape '.../b/n' undefined`（中文无粗体）

```
LaTeX Font Warning: Font shape `TU/HarmonyOS_Sans_SC(0)/b/n' undefined
```

**原因**：自带的中文字体（HarmonyOS Sans SC）没有独立的粗体字形文件。

**修复**：在 `\setCJKmainfont` / `\setCJKsansfont` 里加 `AutoFakeBold`，让 fontspec 合成加粗：

```latex
\setCJKmainfont{HarmonyOS_Sans_SC}[
  Path = fonts/HarmonyOSSans/ , Extension = .ttf , UprightFont = * ,
  AutoFakeBold = 2.5 ]
```

（本 skill 的 preamble 模板已包含，通常无需手改。）

---

## 3. `inputenc` / `fontenc` 冲突

**原因**：原论文 preamble 里有 `\usepackage[utf8]{inputenc}` 或 `\usepackage[T1]{fontenc}`，与 XeLaTeX 的 Unicode 编译栈冲突。

**修复**：**注释掉**这两行。XeLaTeX 原生支持 UTF-8，不需要它们。

---

## 4. 自带 `.sty` 找不到（`File 'xxx.sty' not found`）

**原因**：arXiv 论文常用会议/期刊模板（如 `nips_2017.sty`、`neurips_2024.sty`），它们不在 CTAN 上，作者随源码打包。

**修复**：从源码目录把对应 `.sty` / `.cls` / `.bst` 复制进 `./docs/{名}-CN/` 工程根目录。本 skill 默认应复制源码所需的自定义样式文件。

---

## 5. 字体路径错 / `fontspec error: font not found`

**原因**：`\setmainfont{X}` 找不到字体文件。

**修复**：用 `Path=` / `Extension=` / `UprightFont=` 显式指定，字体随工程分发（`fonts/` 目录已复制）：

```latex
\setmainfont{CascadiaMonoRegular}[
  Path = fonts/CascadiaMono/ , Extension = .ttf , UprightFont = * ,
  BoldFont = CascadiaMonoBold ,
  ItalicFont = CascadiaMonoRegular , ItalicFeatures = { FakeSlant = 0.2 } ]
```

---

## 6. 引用显示 `??` / `[?]`

**原因**：交叉引用或文献引用未解析。

**修复**：
- tectonic 会**自动多遍编译**解析引用，正常无需手动重跑。
- 若仍为 `??`：通常是别处编译出错导致中断（见第 8 条）。先修首个 `!` 错误。
- 文献引用：确认 `.bbl`（或 `\begin{thebibliography}` 块）已带入工程；本 skill 要求**复用原论文的参考文献，不要手敲**。

---

## 7. `Overfull \hbox` / `Underfull \hbox`

**性质**：警告，非错误。表格略宽于版心几 pt 属正常，不影响产出。

**修复**（仅在严重溢出时）：
- 加 `\sloppy`，或
- preamble 加 `\setlength{\emergencystretch}{3em}`，
- 或缩小表格内的 `\scalebox` / 列宽。

---

## 8. 宏包缺失（`File 'xxx.sty' not found`，且非自定义样式）

**原因**：tectonic 默认从 CTAN 自动抓包。若报缺包，通常是**网络问题**或该包名不存在。

**修复**：
- 检查网络连通性（tectonic 需联网首次抓包）。
- 确认包名拼写；极冷门包可尝试注释或换等价包。

---

## 9. 读取错误日志

编译失败时，定位以 `!` 开头的行——那是致命错误：

```
! LaTeX Error: ...
! Undefined control sequence ...
! Missing $ inserted ...
! Argument of \xxx has an extra }.
```

**优先修第一个错误**——后续错误多半是连锁反应。tectonic 输出里搜 `error:` 即可。
