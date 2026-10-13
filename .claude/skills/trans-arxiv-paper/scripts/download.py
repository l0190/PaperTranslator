#!/usr/bin/env python3
"""
下载 arXiv e-print、解压、定位主 .tex、获取论文标题并清洗成目录名。

Usage:
    python3 download.py <paper_id> [work_dir]

流程：
    1. 按 ID 经 arXiv API（失败回退 abs 页）取论文标题；
    2. 将标题清洗为 {arxiv_论文名}（仅保留字母数字，去空格/标点，限长）；
    3. 默认 work_dir = /tmp/papers/{arxiv_论文名}（可由第二参数覆盖）；
    4. 下载 https://arxiv.org/e-print/{id}，tar/gzip 解压回退；
    5. 在解压结果中定位主 .tex（含 \\documentclass，多候选取 \\input 数最多）。

stdout 三行（shell 友好的 KEY='VALUE' 形式）：
    WORK_DIR='<源码目录绝对路径>'
    MAIN_TEX='<主文件相对路径>'
    NAME='<arxiv_论文名>'

仅依赖 Python 标准库。
"""
from __future__ import annotations

import gzip
import html
import os
import re
import shutil
import sys
import tarfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


# --------------------------------------------------------------------------- #
# 下载与解压
# --------------------------------------------------------------------------- #
def _extract_tar(tf: tarfile.TarFile, work_dir: str) -> None:
    """使用更安全的 data 过滤模式解压（Python 3.12+ 支持）。"""
    if sys.version_info >= (3, 12):
        tf.extractall(work_dir, filter="data")
    else:
        tf.extractall(work_dir)


def download_and_extract(paper_id: str, work_dir: str) -> list[str]:
    os.makedirs(work_dir, exist_ok=True)
    source_path = os.path.join(work_dir, "source.bin")

    url = f"https://arxiv.org/e-print/{paper_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(source_path, "wb") as f:
                shutil.copyfileobj(resp, f)
    except Exception as e:  # noqa: BLE001
        print(f"Error: 下载失败 {url}\n{e}", file=sys.stderr)
        sys.exit(1)

    extracted = False
    try:
        if tarfile.is_tarfile(source_path):
            with tarfile.open(source_path) as tf:
                _extract_tar(tf, work_dir)
            extracted = True
    except Exception:  # noqa: BLE001
        pass
    if not extracted:
        # 单文件 gzip 压缩的 .tex
        try:
            with gzip.open(source_path, "rb") as gz, open(
                os.path.join(work_dir, "paper.tex"), "wb"
            ) as out:
                shutil.copyfileobj(gz, out)
            extracted = True
        except Exception:  # noqa: BLE001
            pass
    if not extracted:
        # 兜底：当作裸 .tex
        shutil.copy(source_path, os.path.join(work_dir, "paper.tex"))
    os.remove(source_path)

    tex_files: list[str] = []
    for root, _, files in os.walk(work_dir):
        for f in files:
            if f.endswith(".tex"):
                tex_files.append(os.path.relpath(os.path.join(root, f), work_dir))
    if not tex_files:
        print(
            "Error: 未找到任何 .tex 文件——该论文可能仅提供 PDF。"
            "请改用 trans-pdf 技能处理。",
            file=sys.stderr,
        )
        sys.exit(1)
    return tex_files


# --------------------------------------------------------------------------- #
# 定位主 .tex
# --------------------------------------------------------------------------- #
_RE_DOCCLASS = re.compile(r"\\documentclass")
_RE_INPUT = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")


def find_main_tex(work_dir: str, tex_files: list[str]) -> str:
    candidates: list[tuple[str, str]] = []
    for tf in tex_files:
        try:
            content = open(
                os.path.join(work_dir, tf), "r", encoding="utf-8", errors="replace"
            ).read()
        except OSError:
            continue
        if _RE_DOCCLASS.search(content):
            candidates.append((tf, content))
    if not candidates:
        print("Error: 没有任何 .tex 文件包含 \\documentclass。", file=sys.stderr)
        sys.exit(1)
    if len(candidates) == 1:
        return candidates[0][0]
    # 多个候选：取 \input/\include 数最多的那个
    return max(candidates, key=lambda c: len(_RE_INPUT.findall(c[1])))[0]


# --------------------------------------------------------------------------- #
# 获取标题
# --------------------------------------------------------------------------- #
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_RE_CITATION_TITLE = re.compile(
    r'<meta\s+name=["\']citation_title["\']\s+content=["\'](.*?)["\']',
    re.IGNORECASE,
)
_RE_HTML_TITLE = re.compile(
    r"<title>\s*(?:\[[^\]]+\]\s*)?(.*?)\s*</title>", re.IGNORECASE | re.DOTALL
)


def fetch_arxiv_title_from_api(paper_id: str) -> str | None:
    query = urllib.parse.urlencode({"id_list": paper_id})
    url = f"https://arxiv.org/api/query?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "trans-arxiv-paper/1.0 "
            "(+https://arxiv.org/help/api/user-manual)"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except Exception:  # noqa: BLE001
        return None
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    entry = root.find("atom:entry", _ATOM_NS)
    if entry is None:
        return None
    title_el = entry.find("atom:title", _ATOM_NS)
    if title_el is None:
        return None
    title = " ".join(title_el.itertext()).strip()
    return re.sub(r"\s+", " ", title) or None


def fetch_arxiv_title_from_abs_page(paper_id: str) -> str | None:
    url = f"https://arxiv.org/abs/{paper_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            page = resp.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    for pattern in (_RE_CITATION_TITLE, _RE_HTML_TITLE):
        m = pattern.search(page)
        if not m:
            continue
        title = html.unescape(m.group(1)).strip()
        title = re.sub(r"\s+", " ", title)
        if title:
            return title
    return None


def fetch_arxiv_title(paper_id: str) -> str | None:
    return fetch_arxiv_title_from_api(paper_id) or fetch_arxiv_title_from_abs_page(
        paper_id
    )


# --------------------------------------------------------------------------- #
# 标题 -> 目录名 {arxiv_论文名}
# --------------------------------------------------------------------------- #
def name_from_title(title: str | None, fallback: str, max_len: int = 80) -> str:
    """
    将论文标题清洗为安全的目录名：仅保留字母与数字（去空格/标点）。
    例如 "Attention Is All You Need" -> "AttentionIsAllYouNeed"。
    标题为空或清洗后为空时回退到 fallback（通常是 paper_id）。
    """
    if not title or not str(title).strip():
        return fallback
    s = re.sub(r"[^A-Za-z0-9]", "", str(title))
    if not s:
        return fallback
    return s[:max_len]


# --------------------------------------------------------------------------- #
def _sh_var(name: str, value: str) -> str:
    esc = str(value).replace("'", "'\\''")
    return f"{name}='{esc}'"


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 2):
        print("Usage: python download.py <paper_id> [work_dir]", file=sys.stderr)
        return 2
    paper_id = argv[0]
    work_dir = argv[1] if len(argv) == 2 else None

    # 1) 先取标题、清洗成目录名（决定默认 work_dir）
    title = fetch_arxiv_title(paper_id)
    name = name_from_title(title, fallback=paper_id)
    if work_dir is None:
        work_dir = f"/tmp/papers/{name}"

    # 2) 下载 + 解压 + 定位主文件
    tex_files = download_and_extract(paper_id, work_dir)
    main_tex = find_main_tex(work_dir, tex_files).replace("\\", "/")

    print(_sh_var("WORK_DIR", os.path.abspath(work_dir)))
    print(_sh_var("MAIN_TEX", main_tex))
    print(_sh_var("NAME", name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
