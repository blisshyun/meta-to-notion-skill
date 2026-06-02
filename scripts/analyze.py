#!/usr/bin/env python3
"""
analyze.py — fetch_insights.py가 만든 JSON을 받아 markdown 보고서 생성

표 + 한국어 5문장 요약 + 별도 요청사항 반영.
"""

from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def fmt_money(v: float) -> str:
    if v is None:
        return "-"
    return f"₩{v:,.0f}"


def fmt_pct(v: float) -> str:
    if v is None:
        return "-"
    return f"{v*100:.2f}%"


def fmt_num(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return f"{v:,}"


def render_table(ads: list[dict], rank_by: str, top_n: int, ascending: bool = False) -> str:
    """rank_by 기준으로 정렬 후 markdown 표 반환."""
    def key(ad):
        v = ad["metrics"].get(rank_by)
        return (-1 if v is None else v)

    sorted_ads = sorted(ads, key=key, reverse=not ascending)
    sliced = sorted_ads[:top_n]

    header = "| 순위 | 광고명 | 노출 | 클릭 | CTR | 지출 | CPC | 구매 | ROAS |"
    div    = "|---|---|---:|---:|---:|---:|---:|---:|---:|"
    rows = [header, div]
    for i, ad in enumerate(sliced, 1):
        m = ad["metrics"]
        name = (ad.get("ad_name") or "(무제)")[:45]
        rows.append("| " + " | ".join([
            str(i),
            name,
            fmt_num(m.get("impressions")),
            fmt_num(m.get("clicks")),
            fmt_pct(m.get("ctr")),
            fmt_money(m.get("spend")),
            fmt_money(m.get("cpc")),
            fmt_num(m.get("purchases")),
            f"{m['roas']:.2f}" if m.get("roas") is not None else "-",
        ]) + " |")
    return "\n".join(rows)


def korean_summary(ads: list[dict]) -> list[str]:
    if not ads:
        return ["수집된 광고 데이터가 없습니다. 광고 계정 권한 또는 기간 설정을 확인하세요."]

    total_spend = sum(a["metrics"].get("spend") or 0 for a in ads)
    total_imp = sum(a["metrics"].get("impressions") or 0 for a in ads)
    total_clicks = sum(a["metrics"].get("clicks") or 0 for a in ads)
    total_purchase_value = sum(a["metrics"].get("purchase_value") or 0 for a in ads)
    avg_ctr = (total_clicks / total_imp) if total_imp else 0
    overall_roas = (total_purchase_value / total_spend) if total_spend else None

    # CTR 기준 상/하위
    by_ctr = sorted(ads, key=lambda a: a["metrics"].get("ctr") or 0, reverse=True)
    top_ctr = by_ctr[0] if by_ctr else None
    bot_ctr = by_ctr[-1] if by_ctr else None

    # ROAS 상위 (구매 있는 것만)
    has_roas = [a for a in ads if a["metrics"].get("roas") is not None]
    by_roas = sorted(has_roas, key=lambda a: a["metrics"]["roas"], reverse=True)
    top_roas = by_roas[0] if by_roas else None

    lines = []
    lines.append(
        f"총 {len(ads)}개 광고가 집계됐고, 합계 지출은 {fmt_money(total_spend)}, "
        f"노출 {fmt_num(total_imp)}회 · 클릭 {fmt_num(total_clicks)}회로 "
        f"평균 CTR은 {avg_ctr*100:.2f}%입니다."
    )
    if top_ctr:
        lines.append(
            f"CTR이 가장 높은 소재는 「{(top_ctr.get('ad_name') or '?')[:60]}」 "
            f"({fmt_pct(top_ctr['metrics'].get('ctr'))})로, 후킹·메시지 정합성을 다른 소재의 벤치마크로 쓸 수 있습니다."
        )
    if bot_ctr and bot_ctr is not top_ctr:
        lines.append(
            f"반대로 CTR이 가장 낮은 소재는 「{(bot_ctr.get('ad_name') or '?')[:60]}」 "
            f"({fmt_pct(bot_ctr['metrics'].get('ctr'))})로, 썸네일·첫 3초·문구를 점검할 필요가 있습니다."
        )
    if top_roas:
        lines.append(
            f"ROAS 1위는 「{(top_roas.get('ad_name') or '?')[:60]}」 "
            f"(ROAS {top_roas['metrics']['roas']:.2f}, 지출 {fmt_money(top_roas['metrics']['spend'])}) — "
            f"예산 추가 배분 후보입니다."
        )
    if overall_roas is not None:
        lines.append(
            f"전체 평균 ROAS는 {overall_roas:.2f}로, "
            f"기간 합계 매출 {fmt_money(total_purchase_value)} 기준입니다."
        )
    else:
        lines.append("픽셀 구매 이벤트가 잡히지 않아 ROAS는 계산되지 않았습니다 — 픽셀 설정을 확인하세요.")

    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--extra", default="", help="별도 요청사항 (자유 텍스트)")
    args = ap.parse_args()

    payload = json.loads(Path(args.input).read_text())
    ads = payload.get("ads", [])
    md_lines: list[str] = []

    today = datetime.now().strftime("%Y-%m-%d")
    md_lines.append(f"# 📊 Meta 광고 인사이트 보고서 — {today}")
    md_lines.append("")
    md_lines.append(f"- 광고 계정: `{payload.get('account_id')}`")
    md_lines.append(f"- 기간: `{payload.get('date_preset')}`")
    md_lines.append(f"- 수집 시각: `{payload.get('fetched_at')}`")
    md_lines.append(f"- 광고 수: **{len(ads)}**")
    if args.extra:
        md_lines.append(f"- 별도 요청사항: _{args.extra}_")
    md_lines.append("")

    md_lines.append("## ✨ 한국어 요약")
    md_lines.append("")
    for line in korean_summary(ads):
        md_lines.append(f"- {line}")
    md_lines.append("")

    md_lines.append("## 🥇 ROAS 상위 5")
    md_lines.append("")
    md_lines.append(render_table(ads, rank_by="roas", top_n=5))
    md_lines.append("")

    # 잘된 소재 — 고화질 미리보기 (fetch_insights.py가 hd_image_url 또는 hd_video_url을 채웠을 때만)
    by_roas = sorted(
        [a for a in ads if a["metrics"].get("roas") is not None],
        key=lambda a: a["metrics"]["roas"], reverse=True,
    )
    top_with_hd = [
        a for a in by_roas[:5]
        if (a.get("creative") or {}).get("hd_image_url")
        or (a.get("creative") or {}).get("hd_video_url")
    ]
    if top_with_hd:
        md_lines.append("### 🖼️ 잘된 소재 미리보기 (고화질)")
        md_lines.append("")
        for ad in top_with_hd:
            creative = ad.get("creative") or {}
            img_url = creative.get("hd_image_url")
            video_url = creative.get("hd_video_url")
            name = ad.get("ad_name") or "소재"
            roas = ad["metrics"].get("roas")
            roas_str = f"ROAS {roas:.2f}" if roas is not None else ""
            md_lines.append(f"**{name}** — {roas_str}")
            md_lines.append("")
            # 비디오 광고면 재생 가능한 영상 + 썸네일 둘 다, 이미지 광고면 이미지만
            if video_url:
                md_lines.append(f"!video[{name}]({video_url})")
                md_lines.append("")
            if img_url:
                md_lines.append(f"![{name}]({img_url})")
                md_lines.append("")

    md_lines.append("## 🥉 ROAS 하위 5 (지출 ₩1만 이상)")
    md_lines.append("")
    has_spend = [a for a in ads if (a["metrics"].get("spend") or 0) >= 10000]
    md_lines.append(render_table(has_spend or ads, rank_by="roas", top_n=5, ascending=True))
    md_lines.append("")

    md_lines.append("## 👁️ CTR 상위 5")
    md_lines.append("")
    md_lines.append(render_table(ads, rank_by="ctr", top_n=5))
    md_lines.append("")

    md_lines.append("## 💸 지출 상위 5")
    md_lines.append("")
    md_lines.append(render_table(ads, rank_by="spend", top_n=5))
    md_lines.append("")

    Path(args.output).write_text("\n".join(md_lines), encoding="utf-8")
    print(f"✓ 보고서 생성: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
