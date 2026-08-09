"""AI サマリー dogfood メール送信（自分宛・draft 可・生成直後想定）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence

from services.summary.summary_markdown_email import load_summary_email_bodies
from utils.email_service import EmailService
from utils.logger_config import get_logger

logger = get_logger(__name__)

JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class DogfoodSendResult:
    kind: str
    region: str
    doc_id: str
    path: str
    ok: bool
    skipped: bool = False
    error: str = ""


def default_daily_doc_id(*, today_jst: Optional[date] = None) -> str:
    """生成ジョブと同様、JST の昨日を business_day にする。"""
    d = today_jst or datetime.now(JST).date()
    return (d - timedelta(days=1)).isoformat()


def default_weekly_doc_id(*, today_jst: Optional[date] = None) -> str:
    """直前の完了 ISO 週（月曜始まり）。月曜朝の週次ジョブ想定。"""
    d = today_jst or datetime.now(JST).date()
    # 今週の月曜
    this_monday = d - timedelta(days=d.weekday())
    prev_monday = this_monday - timedelta(days=7)
    y, w, _ = prev_monday.isocalendar()
    return f"{y}-W{w:02d}"


def resolve_dogfood_to() -> str:
    to_addr = (os.getenv("SUMMARY_DOGFOOD_TO") or "").strip()
    if to_addr:
        return to_addr
    sender = (
        os.getenv("RESEND_FROM_EMAIL")
        or os.getenv("MAIL_FROM")
        or os.getenv("SENDER_EMAIL")
        or ""
    ).strip()
    if "@" in sender:
        return sender
    return ""


def dogfood_enabled() -> bool:
    """SUMMARY_DOGFOOD_ENABLED が明示 false でない限り、宛先があれば有効。"""
    flag = (os.getenv("SUMMARY_DOGFOOD_ENABLED") or "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    return bool(resolve_dogfood_to())


def build_subject(
    kind: str, region: str, doc_id: str, *, cross_source: bool = False
) -> str:
    base = f"[Trends-dashboard][{region.upper()}][{kind}] {doc_id}"
    if kind == "daily" and cross_source:
        if (region or "").lower() == "us":
            return f"{base} (cross-source)"
        return f"{base}（横断あり）"
    return base


def send_summary_dogfood(
    *,
    kind: str,
    doc_id: str,
    regions: Sequence[str] = ("jp", "us"),
    to_email: Optional[str] = None,
    dry_run: bool = False,
    email_service: Optional[EmailService] = None,
) -> List[DogfoodSendResult]:
    """指定 kind/doc_id を地域ごとに dogfood 送信。draft も送る。"""
    kind = kind.strip().lower()
    if kind not in ("daily", "weekly"):
        raise ValueError(f"unsupported kind: {kind}")

    to_addr = (to_email or resolve_dogfood_to()).strip()
    results: List[DogfoodSendResult] = []

    if not to_addr:
        logger.warning("SUMMARY_DOGFOOD_TO / From メールが未設定のため dogfood 送信をスキップ")
        for region in regions:
            results.append(
                DogfoodSendResult(
                    kind=kind,
                    region=region,
                    doc_id=doc_id,
                    path="",
                    ok=False,
                    skipped=True,
                    error="missing_recipient",
                )
            )
        return results

    svc = email_service or EmailService()
    if not dry_run and not svc.is_configured():
        logger.warning("メール送信設定が無いため dogfood 送信をスキップ")
        for region in regions:
            results.append(
                DogfoodSendResult(
                    kind=kind,
                    region=region,
                    doc_id=doc_id,
                    path="",
                    ok=False,
                    skipped=True,
                    error="email_not_configured",
                )
            )
        return results

    for region in regions:
        region_n = (region or "jp").strip().lower()
        try:
            path, text, html_body = load_summary_email_bodies(
                kind, doc_id, region=region_n
            )
        except FileNotFoundError as e:
            logger.warning("dogfood: 原稿なし %s", e)
            results.append(
                DogfoodSendResult(
                    kind=kind,
                    region=region_n,
                    doc_id=doc_id,
                    path=str(e),
                    ok=False,
                    skipped=True,
                    error="file_not_found",
                )
            )
            continue

        has_cross = (
            "複数ソースで重なった話題" in text
            or "Topics that overlapped across sources" in text
        )
        subject = build_subject(
            kind, region_n, doc_id, cross_source=has_cross
        )
        header = (
            f"(dogfood) draft 可・自動送信\n"
            f"kind={kind} region={region_n} id={doc_id}\n"
            f"path={path}\n\n"
        )
        text_out = header + text
        html_out = html_body.replace(
            "<body>",
            "<body><p><em>dogfood · draft OK · auto-send after generate</em></p>",
            1,
        )

        if dry_run:
            logger.info(
                "dry-run dogfood: to=%s subject=%s path=%s chars_text=%s",
                to_addr,
                subject,
                path,
                len(text_out),
            )
            results.append(
                DogfoodSendResult(
                    kind=kind,
                    region=region_n,
                    doc_id=doc_id,
                    path=str(path),
                    ok=True,
                    skipped=False,
                )
            )
            continue

        ok = svc.send_multipart(to_addr, subject, html_out, text_out)
        results.append(
            DogfoodSendResult(
                kind=kind,
                region=region_n,
                doc_id=doc_id,
                path=str(path),
                ok=ok,
                skipped=False,
                error="" if ok else "send_failed",
            )
        )
        if ok:
            logger.info("dogfood sent: %s %s %s → %s", kind, region_n, doc_id, to_addr)
        else:
            logger.error("dogfood send failed: %s %s %s", kind, region_n, doc_id)

    return results


def send_default_dogfood(
    kind: str,
    *,
    regions: Iterable[str] = ("jp", "us"),
    dry_run: bool = False,
) -> List[DogfoodSendResult]:
    kind = kind.strip().lower()
    doc_id = default_daily_doc_id() if kind == "daily" else default_weekly_doc_id()
    return send_summary_dogfood(
        kind=kind,
        doc_id=doc_id,
        regions=tuple(regions),
        dry_run=dry_run,
    )
