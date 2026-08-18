"""有料 AI サマリーメール送信（購読者の region_plan に応じて JP/US を配信）。"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from services.billing.ai_summary_subscriber_manager import AiSummarySubscriberManager
from services.billing.region_plan import regions_for_plan
from services.summary.summary_dogfood_email import (
    build_subject,
    default_daily_doc_id,
    default_weekly_doc_id,
)
from services.summary.summary_markdown_email import load_summary_email_bodies
from utils.email_service import EmailService
from utils.logger_config import get_logger

logger = get_logger(__name__)

DEFAULT_SITE_BASE_URL = "https://trends-dashboard.com"


class SubscribersApiUnavailable(RuntimeError):
    """本番 API が未デプロイ / 一時不通。GHA では送信スキップ。"""


class SubscribersApiUnauthorized(RuntimeError):
    """SUMMARY_UPSERT_TOKEN 不一致。"""


@dataclass(frozen=True)
class PaidSendResult:
    kind: str
    region: str
    doc_id: str
    email: str
    ok: bool
    skipped: bool = False
    error: str = ""


def fetch_active_subscribers_from_site(
    *,
    base_url: Optional[str] = None,
    token: Optional[str] = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """本番アプリから有効購読者を取得する（GHA は Fly Postgres に直接繋がらない）。"""
    base = (base_url or os.getenv("TREND_DASHBOARD_BASE_URL") or DEFAULT_SITE_BASE_URL).rstrip(
        "/"
    )
    auth = (token or os.getenv("SUMMARY_UPSERT_TOKEN") or "").strip()
    if not auth:
        raise SubscribersApiUnavailable("SUMMARY_UPSERT_TOKEN が未設定")

    url = f"{base}/api/billing/ai-summary/subscribers"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {auth}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code in (404, 503):
            raise SubscribersApiUnavailable(f"HTTP {e.code}") from e
        if e.code == 401:
            raise SubscribersApiUnauthorized("unauthorized") from e
        raise
    except urllib.error.URLError as e:
        raise SubscribersApiUnavailable(str(e.reason or e)) from e

    rows = payload.get("subscribers") or []
    out: List[Dict[str, Any]] = []
    for row in rows:
        email = str((row or {}).get("email") or "").strip().lower()
        plan = str((row or {}).get("region_plan") or "").strip().lower()
        if email and plan:
            out.append({"email": email, "region_plan": plan})
    return out


def send_summary_paid(
    *,
    kind: str,
    doc_id: str,
    dry_run: bool = False,
    email_service: Optional[EmailService] = None,
    subscriber_manager: Optional[AiSummarySubscriberManager] = None,
    subscribers: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[PaidSendResult]:
    """有効購読者へ kind/doc_id を地域別に送信。"""
    kind = kind.strip().lower()
    if kind not in ("daily", "weekly"):
        raise ValueError(f"unsupported kind: {kind}")

    mgr = None if subscribers is not None else (subscriber_manager or AiSummarySubscriberManager())
    svc = email_service or EmailService()
    results: List[PaidSendResult] = []

    if not dry_run and not svc.is_configured():
        logger.warning("メール送信設定が無いため有料送信をスキップ")
        return results

    for region in ("jp", "us"):
        if subscribers is not None:
            region_subs = [
                sub
                for sub in subscribers
                if region in regions_for_plan(sub.get("region_plan"))
            ]
        else:
            region_subs = mgr.list_active_for_region(region)
        if not region_subs:
            continue

        try:
            path, text, html_body = load_summary_email_bodies(kind, doc_id, region=region)
        except FileNotFoundError as e:
            logger.warning("paid: 原稿なし region=%s %s", region, e)
            for sub in region_subs:
                results.append(
                    PaidSendResult(
                        kind=kind,
                        region=region,
                        doc_id=doc_id,
                        email=sub["email"],
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
        subject = build_subject(kind, region, doc_id, cross_source=has_cross)

        for sub in region_subs:
            email = sub["email"]
            plan_regions = regions_for_plan(sub["region_plan"])
            if region not in plan_regions:
                continue

            if dry_run:
                logger.info(
                    "dry-run paid: to=%s subject=%s path=%s plan=%s",
                    email,
                    subject,
                    path,
                    sub["region_plan"],
                )
                results.append(
                    PaidSendResult(
                        kind=kind,
                        region=region,
                        doc_id=doc_id,
                        email=email,
                        ok=True,
                    )
                )
                continue

            ok = svc.send_multipart(email, subject, html_body, text)
            results.append(
                PaidSendResult(
                    kind=kind,
                    region=region,
                    doc_id=doc_id,
                    email=email,
                    ok=ok,
                    error="" if ok else "send_failed",
                )
            )
            if ok:
                logger.info("paid sent: %s %s %s → %s", kind, region, doc_id, email)
            else:
                logger.error("paid send failed: %s %s → %s", kind, region, email)

    return results


def send_default_paid(
    kind: str,
    *,
    dry_run: bool = False,
) -> List[PaidSendResult]:
    kind = kind.strip().lower()
    doc_id = default_daily_doc_id() if kind == "daily" else default_weekly_doc_id()
    return send_summary_paid(kind=kind, doc_id=doc_id, dry_run=dry_run)
