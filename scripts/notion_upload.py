#!/usr/bin/env python3
"""
notion_upload.py — markdown 보고서를 노션 페이지의 자식 페이지로 업로드

지원 markdown:
- # H1 → heading_1
- ## H2 → heading_2
- ### H3 → heading_3
- "- " 불릿 리스트 → bulleted_list_item
- "| ... |" 표 → table block (헤더 + 데이터 행)
- 빈 줄 → 무시
- 그 외 → paragraph

URL → 페이지 ID 변환:
- "https://www.notion.so/Title-32hexchars" 또는 "https://www.notion.so/workspace/Title-32hexchars"
- 마지막 32자(하이픈 제거) → 페이지 ID
"""

from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "meta-to-notion" / "config.json"
NOTION_VERSION = "2022-06-28"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"config 없음: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text())


def extract_page_id(url_or_id: str) -> str:
    s = url_or_id.strip()
    # 이미 32자 hex (하이픈 무관)면 그대로
    hex_only = re.sub(r"[^0-9a-fA-F]", "", s)
    if len(hex_only) == 32:
        return format_page_id(hex_only)
    # URL 끝부분에서 32자 hex 시퀀스 추출
    m = re.search(r"([0-9a-fA-F]{32})", s.replace("-", ""))
    if not m:
        sys.exit(f"노션 페이지 ID 추출 실패: {url_or_id}")
    return format_page_id(m.group(1))


def format_page_id(hex32: str) -> str:
    """32자 hex → 8-4-4-4-12 형식."""
    return f"{hex32[:8]}-{hex32[8:12]}-{hex32[12:16]}-{hex32[16:20]}-{hex32[20:]}"


def notion_request(method: str, path: str, token: str, body: dict | None = None) -> dict:
    url = f"https://api.notion.com/v1{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        sys.exit(f"Notion API HTTP {e.code} on {method} {path}\n{body_txt}")


# ── markdown → notion blocks ────────────────────────────────────────────

def rich(text: str) -> list[dict]:
    """간단한 inline 처리 — **bold**, *italic*, `code` 정도만."""
    if not text:
        return []
    pattern = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")
    parts = pattern.split(text)
    out = []
    for p in parts:
        if not p:
            continue
        anns = {"bold": False, "italic": False, "code": False}
        content = p
        if p.startswith("**") and p.endswith("**") and len(p) >= 4:
            anns["bold"] = True
            content = p[2:-2]
        elif p.startswith("`") and p.endswith("`") and len(p) >= 2:
            anns["code"] = True
            content = p[1:-1]
        elif p.startswith("*") and p.endswith("*") and len(p) >= 2:
            anns["italic"] = True
            content = p[1:-1]
        out.append({
            "type": "text",
            "text": {"content": content},
            "annotations": anns,
        })
    return out or [{"type": "text", "text": {"content": text}}]


def parse_table(lines: list[str], i: int) -> tuple[dict, int]:
    """Returns (table_block, next_index)."""
    rows = []
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        rows.append(lines[i])
        i += 1
    # 분리자 행 ( | --- | --- | ) 제거
    clean = [r for r in rows if not re.match(r"^\s*\|[\s|:\-]+\|\s*$", r)]
    parsed = []
    for r in clean:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        parsed.append(cells)
    if not parsed:
        return None, i
    width = max(len(r) for r in parsed)
    table_rows = []
    for idx, cells in enumerate(parsed):
        # 부족한 셀 채우기
        cells = cells + [""] * (width - len(cells))
        table_rows.append({
            "type": "table_row",
            "table_row": {"cells": [rich(c) for c in cells]},
        })
    block = {
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows,
        },
    }
    return block, i


IMG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
VIDEO_RE = re.compile(r"^!video\[([^\]]*)\]\(([^)]+)\)\s*$")


def _media_block(kind: str, alt: str, url: str) -> dict:
    """kind = 'image' | 'video' — 외부 URL 임베드 블록 생성."""
    block = {
        "type": kind,
        kind: {
            "type": "external",
            "external": {"url": url},
        },
    }
    if alt:
        block[kind]["caption"] = [{"type": "text", "text": {"content": alt}}]
    return block


def md_to_blocks(md: str) -> list[dict]:
    lines = md.splitlines()
    blocks: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # 비디오는 이미지보다 먼저 매칭 (둘 다 ! 로 시작하므로 순서 중요)
        m_video = VIDEO_RE.match(stripped)
        if m_video:
            blocks.append(_media_block("video", m_video.group(1), m_video.group(2)))
            i += 1
            continue
        m_img = IMG_RE.match(stripped)
        if m_img:
            blocks.append(_media_block("image", m_img.group(1), m_img.group(2)))
            i += 1
            continue
        if stripped.startswith("# "):
            blocks.append({"type": "heading_1",
                           "heading_1": {"rich_text": rich(stripped[2:])}})
            i += 1
        elif stripped.startswith("## "):
            blocks.append({"type": "heading_2",
                           "heading_2": {"rich_text": rich(stripped[3:])}})
            i += 1
        elif stripped.startswith("### "):
            blocks.append({"type": "heading_3",
                           "heading_3": {"rich_text": rich(stripped[4:])}})
            i += 1
        elif stripped.startswith("|") and stripped.endswith("|"):
            block, i = parse_table(lines, i)
            if block:
                blocks.append(block)
        elif stripped.startswith("- "):
            blocks.append({"type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": rich(stripped[2:])}})
            i += 1
        else:
            blocks.append({"type": "paragraph",
                           "paragraph": {"rich_text": rich(stripped)}})
            i += 1
    return blocks


def chunk(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-url", help="부모 노션 페이지 URL 또는 ID (생략 시 config의 default_notion_page 사용)")
    ap.add_argument("--report", required=True, help="markdown 파일 경로")
    ap.add_argument("--title", required=True, help="새로 만들 자식 페이지 제목")
    args = ap.parse_args()

    cfg = load_config()
    token = cfg.get("notion_token")
    if not token:
        sys.exit("Notion 토큰 없음 — auth.py --save-notion-token TOKEN 으로 저장하세요")

    page_url = args.page_url or cfg.get("default_notion_page")
    if not page_url:
        sys.exit("페이지 URL 없음 — --page-url 인자 또는 auth.py --save-notion-page 로 default 지정 필요")
    parent_id = extract_page_id(page_url)
    md = Path(args.report).read_text(encoding="utf-8")
    blocks = md_to_blocks(md)

    # 1. 자식 페이지 생성 (children에는 첫 100개만 한번에 보낼 수 있음)
    first_chunk = blocks[:100]
    rest = blocks[100:]
    print(f"→ 자식 페이지 생성… (블록 총 {len(blocks)}개)", file=sys.stderr)
    page = notion_request("POST", "/pages", token, {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": [{"type": "text", "text": {"content": args.title}}],
        },
        "children": first_chunk,
    })
    new_page_id = page["id"]
    print(f"  page_id = {new_page_id}", file=sys.stderr)

    # 2. 100개 초과분은 PATCH /blocks/{id}/children로 추가
    for batch in chunk(rest, 100):
        notion_request("PATCH", f"/blocks/{new_page_id}/children", token,
                       {"children": batch})

    page_url = page.get("url", f"https://www.notion.so/{new_page_id.replace('-', '')}")
    print(f"✓ 노션 업로드 완료")
    print(page_url)


if __name__ == "__main__":
    main()
