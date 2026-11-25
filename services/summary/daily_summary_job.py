"""Fly APScheduler 用の日次ブリーフ生成ジョブ。

順序: スナップショット確認 → jp/us 生成 → DB upsert →（任意）サムネ → メール。
GHA schedule の代替。git コミットはしない（正本は summary_documents）。
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Sequence

from utils.logger_config import get_logger

logger = get_logger(__name__)

JST = timezone(timedelta(hours=9))
REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_SLOTS = ("07", "13", "19", "01")
REGIONS = ("jp", "us")
_THUMB_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


@dataclass
class DailySummaryJobResult:
    business_day: str
    skipped: bool = False
    reason: str = ""
    generated: list[str] = field(default_factory=list)
    published: list[str] = field(default_factory=list)
    email_ok: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        if self.skipped:
            return True
        if self.errors:
            return False
        return bool(self.published) and set(self.published) >= set(REGIONS)


def daily_summary_on_fly_enabled() -> bool:
    """DAILY_SUMMARY_ON_FLY が明示 false でない限り有効（Fly 本線用）。"""
    flag = (os.getenv("DAILY_SUMMARY_ON_FLY") or "true").strip().lower()
    return flag not in ("0", "false", "no", "off")


def default_business_day_jst(*, now: Optional[datetime] = None) -> date:
    if now is None:
        now = datetime.now(JST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    else:
        now = now.astimezone(JST)
    return now.date() - timedelta(days=1)


def _doc_path(region: str, business_day: str) -> Path:
    daily = REPO_ROOT / "docs" / "summaries" / "daily"
    if region == "us":
        return daily / "us" / f"{business_day}.md"
    return daily / f"{business_day}.md"


def _thumb_path(region: str, business_day: str) -> Optional[Path]:
    directory = REPO_ROOT / "static" / "images" / "summaries" / "daily" / (
        "us" if region == "us" else "jp"
    )
    if not directory.is_dir():
        return None
    found: list[Path] = []
    for path in directory.iterdir():
        if path.stem != business_day:
            continue
        if path.suffix.lower() in _THUMB_TYPES:
            found.append(path)
    if not found:
        return None
    # jpg 優先（publish_summaries_to_site と同じ）
    found.sort(key=lambda p: (0 if p.suffix.lower() in (".jpg", ".jpeg") else 1, p.name))
    return found[0]


def snapshot_slots_present(business_day: date | str) -> tuple[bool, set[str]]:
    """前日 business_day の必須スロットが DB にあるか。"""
    from database_config import TrendsCache

    doc_id = business_day.isoformat() if isinstance(business_day, date) else str(business_day)
    present: set[str] = set()
    try:
        cache = TrendsCache()
        with cache.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT slot
                    FROM trend_daily_snapshots
                    WHERE business_day = %s AND slot = ANY(%s)
                    """,
                    (doc_id, list(REQUIRED_SLOTS)),
                )
                for row in cur.fetchall():
                    present.add(str(row[0]))
    except Exception as e:
        logger.warning("⚠️ 日次ジョブ: スナップショット確認失敗 business_day=%s: %s", doc_id, e)
        return False, present
    missing = set(REQUIRED_SLOTS) - present
    return not missing, present


def already_published(business_day: str) -> bool:
    from services.summary.summary_store import has_document

    return all(has_document("daily", region, business_day) is True for region in REGIONS)


def _run_script(args: Sequence[str], *, timeout: int) -> tuple[int, str]:
    cmd = [sys.executable, *args]
    logger.info("日次ジョブ subprocess: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        )
    except subprocess.TimeoutExpired as e:
        return 124, f"timeout after {timeout}s: {e}"
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    detail = "\n".join(x for x in (stdout, stderr) if x)
    return proc.returncode, detail


def generate_region_markdown(business_day: str, region: str, *, force: bool = True) -> tuple[bool, str]:
    script = str(REPO_ROOT / "scripts" / "generate_ai_daily_summary.py")
    args = [
        script,
        "--write",
        "--region",
        region,
        "--business-day",
        business_day,
    ]
    if force:
        args.append("--force")
    # 機械生成が既定。DB 直読み（Fly 上は DATABASE_URL あり）
    timeout = int(os.getenv("DAILY_SUMMARY_GENERATE_TIMEOUT_SECONDS", "600"))
    code, detail = _run_script(args, timeout=timeout)
    if code != 0:
        return False, detail or f"exit {code}"
    path = _doc_path(region, business_day)
    if not path.is_file():
        return False, f"markdown missing after generate: {path}"
    return True, detail


def publish_markdown_to_db(business_day: str, regions: Sequence[str] = REGIONS) -> list[str]:
    from services.summary.summary_store import upsert_document

    published: list[str] = []
    for region in regions:
        path = _doc_path(region, business_day)
        if not path.is_file():
            logger.warning("日次ジョブ: upsert スキップ（ファイルなし） %s/%s", region, business_day)
            continue
        body = path.read_text(encoding="utf-8")
        if upsert_document("daily", region, business_day, body):
            published.append(region)
            logger.info("📝 日次ジョブ upsert OK daily/%s/%s (%d bytes)", region, business_day, len(body))
        else:
            logger.error("❌ 日次ジョブ upsert 失敗 daily/%s/%s", region, business_day)
    return published


def attach_and_publish_thumbs(business_day: str) -> None:
    """サムネ失敗は原稿・メールを止めない。"""
    from services.summary.daily_thumbs import attach_missing
    from services.summary.summary_store import upsert_thumb

    try:
        attach_missing(only_date=business_day, regions=REGIONS)
    except Exception as e:
        logger.warning("⚠️ 日次ジョブ: サムネ生成スキップ %s: %s", business_day, e)
        return

    for region in REGIONS:
        path = _thumb_path(region, business_day)
        if path is None:
            continue
        content_type = _THUMB_TYPES.get(path.suffix.lower())
        if not content_type:
            continue
        try:
            image = path.read_bytes()
            if upsert_thumb("daily", region, business_day, image, content_type):
                logger.info("🖼️ 日次ジョブ thumb upsert OK %s/%s", region, business_day)
            else:
                logger.warning("⚠️ 日次ジョブ thumb upsert 失敗 %s/%s", region, business_day)
        except Exception as e:
            logger.warning("⚠️ 日次ジョブ thumb 読込失敗 %s/%s: %s", region, business_day, e)


def send_emails(business_day: str) -> tuple[bool, list[str]]:
    """dogfood → paid。設定が無ければスキップ（エラーにはしない）。"""
    errors: list[str] = []
    try:
        from services.summary.summary_dogfood_email import dogfood_enabled, send_summary_dogfood

        if dogfood_enabled():
            results = send_summary_dogfood(kind="daily", doc_id=business_day, regions=REGIONS)
            failed = [r for r in results if not r.ok and not r.skipped]
            if failed:
                errors.append(
                    "dogfood: "
                    + ", ".join(f"{r.region}:{r.error or 'failed'}" for r in failed)
                )
        else:
            logger.info("日次ジョブ: dogfood スキップ（未設定）")
    except Exception as e:
        logger.exception("日次ジョブ: dogfood 例外")
        errors.append(f"dogfood: {e}")

    try:
        from services.summary.summary_paid_email import send_summary_paid

        results = send_summary_paid(kind="daily", doc_id=business_day)
        failed = [r for r in results if not r.ok and not r.skipped]
        if failed:
            errors.append(
                "paid: "
                + ", ".join(f"{r.email}:{r.error or 'failed'}" for r in failed[:5])
            )
    except Exception as e:
        # 購読者ゼロ・未設定は正常系に近い
        logger.warning("日次ジョブ: paid メールスキップ/失敗: %s", e)

    return not errors, errors


def run_daily_summary_job(
    *,
    business_day: Optional[str] = None,
    force: bool = False,
    send_mail: bool = True,
    attach_thumbs: bool = True,
) -> DailySummaryJobResult:
    """本番本線: スナップショット確認 → 生成 → DB → メール。"""
    bd = (business_day or "").strip() or default_business_day_jst().isoformat()
    result = DailySummaryJobResult(business_day=bd)

    if not force and already_published(bd):
        result.skipped = True
        result.reason = "already_published"
        logger.info("✅ 日次ジョブ: 既に DB にあるためスキップ business_day=%s", bd)
        return result

    ready, present = snapshot_slots_present(bd)
    if not ready:
        missing = sorted(set(REQUIRED_SLOTS) - present)
        result.errors.append(f"snapshots_incomplete missing={','.join(missing)}")
        logger.warning(
            "⚠️ 日次ジョブ: スナップショット未揃い business_day=%s present=%s missing=%s",
            bd,
            sorted(present),
            missing,
        )
        return result

    for region in REGIONS:
        ok, detail = generate_region_markdown(bd, region, force=True)
        if ok:
            result.generated.append(region)
        else:
            result.errors.append(f"generate/{region}: {detail[:500]}")
            logger.error("❌ 日次ジョブ generate 失敗 region=%s: %s", region, detail[:500])

    if not result.generated:
        return result

    result.published = publish_markdown_to_db(bd, result.generated)
    missing_pub = [r for r in result.generated if r not in result.published]
    for region in missing_pub:
        result.errors.append(f"publish/{region}: upsert_failed")

    if attach_thumbs and result.published:
        try:
            attach_and_publish_thumbs(bd)
        except Exception as e:
            logger.warning("⚠️ 日次ジョブ: サムネ段階スキップ: %s", e)

    # メールは DB に載った分だけ。両 region 揃ってから送る（片方欠けると不完全配信）
    if send_mail and set(result.published) >= set(REGIONS):
        email_ok, email_errors = send_emails(bd)
        result.email_ok = email_ok
        result.errors.extend(email_errors)
    elif send_mail:
        result.errors.append("email_skipped: not_both_regions_published")
        logger.warning(
            "⚠️ 日次ジョブ: 両 region 未揃いのためメールスキップ published=%s",
            result.published,
        )

    if result.ok:
        logger.info(
            "✅ 日次ジョブ完了 business_day=%s published=%s email_ok=%s",
            bd,
            result.published,
            result.email_ok,
        )
    else:
        logger.error(
            "❌ 日次ジョブ失敗 business_day=%s errors=%s",
            bd,
            result.errors,
        )
    return result
