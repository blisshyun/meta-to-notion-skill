#!/usr/bin/env python3
"""
fetch_insights.py — Meta Graph API로 광고 단위 인사이트 + 광고 소재 메타 수집

출력 JSON 스키마:
{
  "account_id": "act_...",
  "date_preset": "last_7d",
  "fetched_at": "ISO timestamp",
  "ads": [
    {
      "ad_id": "...",
      "ad_name": "...",
      "creative": { "id":"...", "name":"...", "thumbnail_url":"...",
                    "image_url":"...", "video_id":"...",
                    "body":"...", "title":"..." },
      "metrics": {
        "impressions": int, "clicks": int, "spend": float,
        "ctr": float, "cpc": float, "cpm": float,
        "purchases": int, "purchase_value": float,
        "roas": float | null
      }
    },
    ...
  ]
}
"""

from __future__ import annotations
import argparse
import json
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "meta-to-notion" / "config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"config 없음: {CONFIG_PATH} — auth.py로 먼저 저장하세요")
    return json.loads(CONFIG_PATH.read_text())


def graph_get(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        sys.exit(f"Graph API HTTP {e.code}\n{body}")


def graph_get_optional(url: str, token: str) -> dict | None:
    """필수가 아닌 호출용 — 에러 시 sys.exit 대신 None 반환."""
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception:
        return None


def paginate(initial_url: str, token: str) -> list[dict]:
    """data[] 를 모두 모아 반환. paging.next 따라가며."""
    out: list[dict] = []
    url = initial_url
    while url:
        page = graph_get(url, token)
        out.extend(page.get("data", []))
        url = page.get("paging", {}).get("next")
    return out


def fetch_ads(account_id: str, api_version: str, token: str) -> dict[str, dict]:
    """ad_id → {name, creative{...}} 사전 반환."""
    fields = (
        "id,name,status,effective_status,"
        "creative{id,name,thumbnail_url,image_url,video_id,body,title,object_story_spec}"
    )
    url = (
        f"https://graph.facebook.com/{api_version}/{account_id}/ads"
        f"?fields={urllib.parse.quote(fields)}&limit=200"
    )
    out: dict[str, dict] = {}
    for ad in paginate(url, token):
        out[ad["id"]] = {
            "name": ad.get("name", ""),
            "status": ad.get("status"),
            "effective_status": ad.get("effective_status"),
            "creative": ad.get("creative") or {},
        }
    return out


def fetch_insights(account_id: str, api_version: str, token: str,
                   date_preset: str) -> list[dict]:
    fields = (
        "ad_id,ad_name,impressions,clicks,spend,ctr,cpc,cpm,"
        "actions,action_values"
    )
    url = (
        f"https://graph.facebook.com/{api_version}/{account_id}/insights"
        f"?level=ad&date_preset={date_preset}"
        f"&fields={urllib.parse.quote(fields)}&limit=200"
    )
    return paginate(url, token)


def find_action(actions: list[dict] | None, action_type: str) -> float:
    if not actions:
        return 0.0
    for a in actions:
        if a.get("action_type") == action_type:
            try:
                return float(a.get("value", 0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def fetch_video_thumb_uri(video_id: str, api_version: str, token: str) -> str | None:
    """비디오에서 가장 큰 썸네일 URI 반환 (없으면 None)."""
    fields = "thumbnails{uri,width,height}"
    url = (
        f"https://graph.facebook.com/{api_version}/{video_id}"
        f"?fields={urllib.parse.quote(fields)}"
    )
    data = graph_get_optional(url, token)
    if not data:
        return None
    thumbs = (data.get("thumbnails") or {}).get("data") or []
    if not thumbs:
        return None
    sorted_thumbs = sorted(thumbs, key=lambda t: t.get("width") or 0, reverse=True)
    return sorted_thumbs[0].get("uri")


def fetch_video_source(video_id: str, api_version: str, token: str) -> str | None:
    """비디오 ID에서 실제 mp4 source URL 반환 (없으면 None).

    Meta가 발급하는 signed URL이라 만료 시간이 있음 — 노션에 빠르게 업로드한 직후엔 정상 재생.
    """
    fields = "source,permalink_url"
    url = (
        f"https://graph.facebook.com/{api_version}/{video_id}"
        f"?fields={urllib.parse.quote(fields)}"
    )
    data = graph_get_optional(url, token)
    if not data:
        return None
    return data.get("source")


def pick_hd_url(creative: dict, video_thumb_uri: str | None = None) -> str | None:
    """창의의 여러 후보 중 가장 좋은 이미지 URL 선택.

    참고: Meta_API_Toolkit/meta-ads-backend/api/images.js의 우선순위 패턴.
    1) 비디오 썸네일(가장 큰 것)
    2) object_story_spec 내부 (link_data.picture / photo_data.url / video_data.image_url)
    3) creative.image_url
    4) creative.thumbnail_url
    """
    candidates = []
    if video_thumb_uri:
        candidates.append(video_thumb_uri)
    spec = creative.get("object_story_spec") or {}
    candidates.append((spec.get("link_data") or {}).get("picture"))
    candidates.append((spec.get("photo_data") or {}).get("url"))
    candidates.append((spec.get("video_data") or {}).get("image_url"))
    candidates.append(creative.get("image_url"))
    candidates.append(creative.get("thumbnail_url"))
    return next((c for c in candidates if c), None)


def enrich_top_creatives(merged: list[dict], api_version: str, token: str,
                         top_n: int) -> int:
    """ROAS 상위 N개(부족하면 CTR로 보충)의 creative.hd_image_url 채워넣기.
    반환: HD URL을 채운 광고 수.
    """
    if top_n <= 0 or not merged:
        return 0

    has_roas = [a for a in merged if a["metrics"].get("roas") is not None]
    by_roas = sorted(has_roas, key=lambda a: a["metrics"]["roas"], reverse=True)
    selected = by_roas[:top_n]
    if len(selected) < top_n:
        rest = [a for a in merged if a not in selected]
        rest_sorted = sorted(rest, key=lambda a: a["metrics"].get("ctr") or 0, reverse=True)
        selected.extend(rest_sorted[: top_n - len(selected)])

    filled = 0
    for ad in selected:
        creative = ad.get("creative") or {}
        video_id = creative.get("video_id")
        video_thumb = None
        if video_id:
            video_thumb = fetch_video_thumb_uri(video_id, api_version, token)
            video_src = fetch_video_source(video_id, api_version, token)
            if video_src:
                creative["hd_video_url"] = video_src
        hd = pick_hd_url(creative, video_thumb)
        if hd:
            creative["hd_image_url"] = hd
        if hd or creative.get("hd_video_url"):
            ad["creative"] = creative
            filled += 1
    return filled


def merge(insights: list[dict], ads_meta: dict[str, dict]) -> list[dict]:
    out = []
    for row in insights:
        ad_id = row.get("ad_id")
        meta = ads_meta.get(ad_id, {})
        impressions = int(row.get("impressions") or 0)
        clicks = int(row.get("clicks") or 0)
        spend = float(row.get("spend") or 0)
        ctr = float(row.get("ctr") or 0)
        cpc = float(row.get("cpc") or 0)
        cpm = float(row.get("cpm") or 0)
        purchases = find_action(row.get("actions"), "purchase") or \
                    find_action(row.get("actions"), "omni_purchase")
        purchase_value = find_action(row.get("action_values"), "purchase") or \
                         find_action(row.get("action_values"), "omni_purchase")
        roas = (purchase_value / spend) if spend > 0 else None
        cpa = (spend / purchases) if purchases > 0 else None
        out.append({
            "ad_id": ad_id,
            "ad_name": row.get("ad_name") or meta.get("name", ""),
            "creative": meta.get("creative", {}),
            "status": meta.get("effective_status"),
            "metrics": {
                "impressions": impressions,
                "clicks": clicks,
                "spend": round(spend, 2),
                "ctr": round(ctr, 4),
                "cpc": round(cpc, 2),
                "cpm": round(cpm, 2),
                "purchases": int(purchases),
                "purchase_value": round(purchase_value, 2),
                "roas": round(roas, 3) if roas is not None else None,
                "cpa": round(cpa, 2) if cpa is not None else None,
            },
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-id", help="act_xxx (없으면 config에서 로드)")
    ap.add_argument("--days", type=int, default=7, help="최근 N일 (1, 7, 14, 28, 30)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--top-creatives", type=int, default=3,
                    help="ROAS 상위 N개 소재의 고화질 URL 추가 수집 (0=비활성)")
    args = ap.parse_args()

    cfg = load_config()
    token = cfg.get("meta_token") or sys.exit("Meta 토큰 없음 — auth.py --save-meta-token")
    api_version = cfg.get("meta_api_version", "v23.0")
    account_id = args.account_id or cfg.get("ad_account_id") or sys.exit("광고 계정 ID 없음")
    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"

    preset_map = {1: "yesterday", 7: "last_7d", 14: "last_14d",
                  28: "last_28d", 30: "last_30d"}
    date_preset = preset_map.get(args.days, "last_7d")

    print(f"→ ads 메타 수집…", file=sys.stderr)
    ads_meta = fetch_ads(account_id, api_version, token)
    print(f"  {len(ads_meta)}개 ad 수집됨", file=sys.stderr)

    print(f"→ insights 수집… (date_preset={date_preset})", file=sys.stderr)
    rows = fetch_insights(account_id, api_version, token, date_preset)
    print(f"  {len(rows)}개 insight row", file=sys.stderr)

    merged = merge(rows, ads_meta)

    if args.top_creatives > 0 and merged:
        print(f"→ ROAS 상위 {args.top_creatives}개 소재의 고화질 이미지 URL 수집…",
              file=sys.stderr)
        filled = enrich_top_creatives(merged, api_version, token, args.top_creatives)
        print(f"  HD URL 확보: {filled}개", file=sys.stderr)

    payload = {
        "account_id": account_id,
        "date_preset": date_preset,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ads": merged,
    }
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"✓ 저장: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
