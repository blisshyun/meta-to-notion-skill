#!/usr/bin/env python3
"""
auth.py — config 저장·검증

~/.config/meta-to-notion/config.json 형식:
{
  "meta_token": "EAAxxx...",
  "ad_account_id": "act_xxxxxxxxxxxxxxxx",
  "notion_token": "ntn_xxx..." | null,
  "default_notion_page": "https://www.notion.so/...",
  "meta_api_version": "v23.0"
}

사용 예:
  python3 auth.py                                 # 현재 config 상태 출력
  python3 auth.py --save-meta-token EAA...        # Meta 토큰 저장
  python3 auth.py --save-account-id act_123       # 광고 계정 ID 저장
  python3 auth.py --save-notion-token ntn_...     # 노션 통합 토큰 저장
  python3 auth.py --save-notion-page https://...  # 기본 노션 페이지 URL 저장
  python3 auth.py --validate                      # Meta 토큰을 /me로 검증
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "meta-to-notion" / "config.json"
DEFAULT_API_VERSION = "v23.0"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as e:
        sys.exit(f"config.json 파싱 실패: {e}")


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    os.chmod(CONFIG_PATH, 0o600)


def mask(token: str | None) -> str:
    if not token:
        return "(없음)"
    if len(token) <= 12:
        return token[:4] + "…"
    return f"{token[:8]}…{token[-4:]} ({len(token)}자)"


def validate_meta(token: str, api_version: str) -> tuple[bool, str]:
    if not token:
        return False, "토큰 없음"
    url = f"https://graph.facebook.com/{api_version}/me?fields=id,name"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            return True, f"OK — id={data.get('id')} name={data.get('name','?')}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return False, f"HTTP {e.code} — {body[:200]}"
    except Exception as e:
        return False, f"네트워크 에러: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-meta-token", metavar="TOKEN")
    ap.add_argument("--save-notion-token", metavar="TOKEN")
    ap.add_argument("--save-account-id", metavar="ACT_ID")
    ap.add_argument("--save-notion-page", metavar="URL_OR_ID",
                    help="기본 노션 페이지 URL/ID (사용자가 별도 페이지 안 줄 때 fallback)")
    ap.add_argument("--validate", action="store_true",
                    help="메타 토큰을 Graph API /me에 호출해 유효성 확인")
    args = ap.parse_args()

    cfg = load_config()
    cfg.setdefault("meta_api_version", DEFAULT_API_VERSION)

    changed = False
    if args.save_meta_token:
        cfg["meta_token"] = args.save_meta_token
        changed = True
    if args.save_notion_token:
        cfg["notion_token"] = args.save_notion_token
        changed = True
    if args.save_account_id:
        acct = args.save_account_id
        if not acct.startswith("act_"):
            acct = f"act_{acct}"
        cfg["ad_account_id"] = acct
        changed = True
    if args.save_notion_page:
        cfg["default_notion_page"] = args.save_notion_page
        changed = True

    if changed:
        save_config(cfg)
        print(f"✓ config 저장: {CONFIG_PATH}")

    print("── meta-to-notion config ──")
    print(f"  config 경로     : {CONFIG_PATH}")
    print(f"  Meta API 버전   : {cfg.get('meta_api_version')}")
    print(f"  광고 계정 ID    : {cfg.get('ad_account_id') or '(없음)'}")
    print(f"  Meta 토큰       : {mask(cfg.get('meta_token'))}")
    print(f"  Notion 토큰     : {mask(cfg.get('notion_token'))}")
    print(f"  기본 노션 페이지: {cfg.get('default_notion_page') or '(없음)'}")

    if args.validate:
        print()
        ok, msg = validate_meta(cfg.get("meta_token", ""), cfg["meta_api_version"])
        prefix = "✓" if ok else "✗"
        print(f"  {prefix} Meta 토큰 검증: {msg}")
        if not ok:
            sys.exit(2)

    if not cfg.get("meta_token"):
        print("\n⚠ Meta 토큰이 없습니다. --save-meta-token TOKEN 으로 저장하세요.")
    if not cfg.get("notion_token"):
        print("\n⚠ Notion 토큰이 없습니다. 첫 노션 업로드 전에 --save-notion-token TOKEN 으로 저장하세요.")


if __name__ == "__main__":
    main()
