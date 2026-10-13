#!/usr/bin/env python3
"""
LaTeX 源码中"未翻译英文片段"的启发式扫描器。

Usage:
    python inspect_tex.py scan <work_dir> <main_tex> <scope>

scope:
    - body: 扫描 \\begin{document} 到 \\end{document}；遇到 \\appendix 停止。
    - full: 扫描整个文件。

判定：剥离注释、数学环境、LaTeX 命令、\\cite/\\ref/\\label/图片路径等之后，
若一行仍含 6 个以上字母的英文长串且不含中文，则视为疑似未译。

Output:
    SUSPECT_COUNT=<n>
    SUSPECT=<file>:<lineno>:<snippet>
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Iterable


INPUT_RE = re.compile(r"\\(input|include|subfile)\{([^}]+)\}")
BEGIN_DOC_RE = re.compile(r"\\begin\{document\}")
END_DOC_RE = re.compile(r"\\end\{document\}")
APPENDIX_RE = re.compile(r"\\appendix\b")
BEGIN_BIB_RE = re.compile(
    r"\\begin\{thebibliography\}|\\bibliographystyle\{|\\bibliography\{"
)
BEGIN_TABULAR_RE = re.compile(r"\\begin\{tabular\}")
END_TABULAR_RE = re.compile(r"\\end\{tabular\}")

# 去掉注释（非转义的 %）
COMMENT_RE = re.compile(r"(?<!\\)%.*$")

# 大致移除不应被翻译的常见 LaTeX 构造
STRIP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\\(input|include|subfile)\{[^}]*\}"),
    re.compile(r"\\includegraphics(\[[^\]]*\])?\{[^}]*\}"),
    re.compile(r"\\texttt\{[^}]*\}"),
    re.compile(r"\\textit\{[^}]*\}"),
    re.compile(r"\\cite\w*\{[^}]*\}"),
    re.compile(r"\\ref\{[^}]*\}"),
    re.compile(r"\\label\{[^}]*\}"),
    re.compile(r"\\url\{[^}]*\}"),
    re.compile(r"\\href\{[^}]*\}\{[^}]*\}"),
    re.compile(r"\\(begin|end)\{[^}]*\}"),
    re.compile(r"\$[^$]*\$"),
    re.compile(r"\\\([^)]*\\\)"),
    re.compile(r"\\\[[^\]]*\\\]"),
    re.compile(r"\\[A-Za-z@]+\*?"),  # 命令名
    re.compile(r"[{}\\[\\]]"),
]

ALPHA_RUN_RE = re.compile(r"[A-Za-z]{6,}")
CJK_RE = re.compile(r"[一-鿿]")
TABULAR_SPEC_RE = re.compile(r"^[lcrpmb\|@*!0-9.\s]+$")


@dataclass(frozen=True)
class Suspect:
    path: str
    lineno: int
    snippet: str


def _norm_tex_path(work_dir: str, raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    candidates = [raw]
    if not raw.lower().endswith(".tex"):
        candidates.append(raw + ".tex")
    for c in candidates:
        p = os.path.normpath(os.path.join(work_dir, c))
        if os.path.exists(p) and os.path.isfile(p):
            return p
    return None


def _walk_includes(work_dir: str, main_tex: str) -> list[str]:
    work_dir = os.path.abspath(work_dir)
    main_abs = main_tex if os.path.isabs(main_tex) else os.path.join(work_dir, main_tex)
    main_abs = os.path.abspath(main_abs)
    if not main_abs.startswith(work_dir + os.sep) and main_abs != work_dir:
        raise SystemExit(f"main_tex must be within work_dir: {main_abs}")

    queue = [main_abs]
    seen: set[str] = set()
    ordered: list[str] = []

    while queue:
        cur = os.path.abspath(queue.pop(0))
        if cur in seen or not os.path.exists(cur):
            continue
        seen.add(cur)
        ordered.append(cur)
        try:
            with open(cur, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        for m in INPUT_RE.finditer(text):
            inc = _norm_tex_path(os.path.dirname(cur), m.group(2))
            if inc and inc.startswith(work_dir + os.sep):
                queue.append(inc)
    return ordered


def _iter_relevant_lines(lines: list[str], scope: str) -> Iterable[tuple[int, str]]:
    if scope == "full":
        for i, line in enumerate(lines, start=1):
            yield i, line
        return

    # body scope
    in_doc = False
    in_tabular = False
    for i, line in enumerate(lines, start=1):
        if not in_doc and BEGIN_DOC_RE.search(line):
            in_doc = True
        if not in_doc:
            continue
        if APPENDIX_RE.search(line):
            break
        if BEGIN_BIB_RE.search(line):
            break
        if END_DOC_RE.search(line):
            break
        if BEGIN_TABULAR_RE.search(line):
            in_tabular = True
        if in_tabular:
            if END_TABULAR_RE.search(line):
                in_tabular = False
            continue
        yield i, line


def _strip_for_detection(s: str) -> str:
    s = COMMENT_RE.sub("", s)
    for pat in STRIP_PATTERNS:
        s = pat.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _is_suspect_line(s: str) -> bool:
    if not s:
        return False
    if TABULAR_SPEC_RE.match(s):
        return False
    # 含中文字符即视为已译（残留的英文多为缩写/专有名词）
    if CJK_RE.search(s):
        return False
    alpha = sum(1 for ch in s if ch.isalpha())
    if alpha < 12:
        return False
    if ALPHA_RUN_RE.search(s):
        return True
    return alpha / max(len(s), 1) > 0.35


def scan(work_dir: str, main_tex: str, scope: str) -> list[Suspect]:
    suspects: list[Suspect] = []
    for path in _walk_includes(work_dir, main_tex):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            continue
        for lineno, raw in _iter_relevant_lines(lines, scope):
            stripped = _strip_for_detection(raw)
            if _is_suspect_line(stripped):
                suspects.append(
                    Suspect(path=path, lineno=lineno, snippet=stripped[:160])
                )
    return suspects


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan_p = sub.add_parser("scan")
    scan_p.add_argument("work_dir")
    scan_p.add_argument("main_tex")
    scan_p.add_argument("scope", choices=["body", "full"])

    args = parser.parse_args(argv)
    if args.cmd == "scan":
        sus = scan(args.work_dir, args.main_tex, args.scope)
        print(f"SUSPECT_COUNT={len(sus)}")
        for s in sus[:5000]:
            rel = os.path.relpath(s.path, os.path.abspath(args.work_dir))
            print(f"SUSPECT={rel}:{s.lineno}:{s.snippet}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
