"""trend_daily_snapshots のスロット健全性チェック（欠損検知・保存後検証）。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytz

from services.trend_snapshot_service import parse_scheduler_slot_key

JST = pytz.timezone("Asia/Tokyo")
SLOT_ORDER = ("07", "13", "19", "01")

# 定時スロットの captured_at 期待帯（JST）。外れていれば backfill 誤認防止の warning。
_SLOT_CAPTURE_HOURS: dict[str, tuple[int, int]] = {
    "07": (6, 9),
    "13": (12, 15),
    "19": (18, 21),
    "01": (0, 3),
}


def prior_slot_codes(slot_code: str) -> List[str]:
    """同一 business_day 内で、slot_code より前のスロットコード。"""
    if slot_code not in SLOT_ORDER:
        return []
    idx = SLOT_ORDER.index(slot_code)
    return list(SLOT_ORDER[:idx])


def count_snapshot_rows(db: Any, business_day: date, slot_code: str) -> int:
    if db is None:
        return 0
    if hasattr(db, "count_trend_daily_snapshot_rows"):
        try:
            return int(db.count_trend_daily_snapshot_rows(business_day, slot_code))
        except Exception:
            pass
    if not hasattr(db, "get_trend_daily_snapshots_for_business_day"):
        return 0
    try:
        rows = db.get_trend_daily_snapshots_for_business_day(business_day) or []
    except Exception:
        return 0
    return sum(1 for r in rows if str(r.get("slot") or "") == slot_code)


def slot_has_snapshot(db: Any, business_day: date, slot_code: str) -> bool:
    return count_snapshot_rows(db, business_day, slot_code) > 0


def find_missing_prior_slots(
    db: Any,
    business_day: date,
    current_slot_code: str,
) -> List[str]:
    """current_slot より前のスロットで DB 行が 0 のもの。"""
    missing: List[str] = []
    for code in prior_slot_codes(current_slot_code):
        if not slot_has_snapshot(db, business_day, code):
            missing.append(code)
    return missing


def format_prior_slot_gaps(missing: List[str], business_day: date) -> str:
    if not missing:
        return ""
    labels = ", ".join(f"{c}時" for c in missing)
    return f"⚠️ {business_day.isoformat()} の未保存スロット: {labels}"


def parse_slot_key(slot_key: str) -> Optional[Tuple[date, str]]:
    parsed = parse_scheduler_slot_key(slot_key)
    if not parsed:
        return None
    return parsed


def slot_key_for(business_day: date, slot_code: str) -> str:
    """business_day + slot_code → scheduler slot_key。"""
    slot_code = slot_code.zfill(2)
    if slot_code == "01":
        cal = business_day + timedelta(days=1)
        return f"1am_{cal.isoformat()}"
    if slot_code == "07":
        return f"7am_{business_day.isoformat()}"
    if slot_code == "13":
        return f"1pm_{business_day.isoformat()}"
    if slot_code == "19":
        return f"7pm_{business_day.isoformat()}"
    raise ValueError(f"unsupported slot_code: {slot_code}")


def iter_scheduled_slots_for_business_day(business_day: date) -> List[tuple[str, str]]:
    """(slot_code, slot_key) を定時順に返す。"""
    return [(code, slot_key_for(business_day, code)) for code in SLOT_ORDER]


def check_captured_at_in_slot_window(
    captured_at: datetime,
    business_day: date,
    slot_code: str,
) -> tuple[bool, str]:
    """captured_at が定時帯内か（JST）。戻り値: (ok, message)。"""
    hours = _SLOT_CAPTURE_HOURS.get(slot_code)
    if not hours:
        return True, ""
    lo, hi = hours
    if captured_at.tzinfo is None:
        cap = JST.localize(captured_at)
    else:
        cap = captured_at.astimezone(JST)

    if slot_code == "01":
        cal_day = business_day + timedelta(days=1)
    else:
        cal_day = business_day

    if cap.date() != cal_day:
        return False, (
            f"captured_at {cap.strftime('%Y-%m-%d %H:%M JST')} が "
            f"slot {slot_code} の暦日 {cal_day} と一致しません"
        )
    if not (lo <= cap.hour < hi):
        return False, (
            f"captured_at {cap.strftime('%H:%M JST')} が slot {slot_code} の"
            f" 期待帯 {lo:02d}:00–{hi:02d}:00 JST 外です（backfill 疑い）"
        )
    return True, ""


def slot_needs_recovery(
    db: Any,
    slot_key: str,
    *,
    require_completed: bool = False,
) -> bool:
    """refresh 未完了、またはスナップショット行が無ければ復旧対象。"""
    parsed = parse_slot_key(slot_key)
    if not parsed:
        return False
    business_day, slot_code = parsed
    # OOM 等で refresh 失敗後に古いキャッシュだけ snapshot された場合も再取得する
    if db and hasattr(db, "has_slot_completed"):
        if not db.has_slot_completed(slot_key):
            return True
    if slot_has_snapshot(db, business_day, slot_code):
        return False
    if require_completed and db and hasattr(db, "has_slot_completed"):
        if not db.has_slot_completed(slot_key):
            return False
    return True


def refresh_succeeded_for_snapshot(refresh_result: dict) -> bool:
    """全フェーズ成功時のみスナップショットを書く（失敗時の gap_retry 阻害を防ぐ）。"""
    if refresh_result.get("job_timed_out"):
        return False
    if refresh_result.get("jp_phase_failed") or refresh_result.get("us_phase_failed"):
        return False
    return bool(refresh_result.get("success"))


def write_and_verify_snapshot(
    managers: Dict[str, Any],
    db: Any,
    scheduler_slot_key: Optional[str],
    trigger_source: str,
    captured_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """スナップショット保存 + DB 読み戻し検証。"""
    from services.trend_snapshot_service import write_snapshots_for_scheduler_run

    empty: Dict[str, Any] = {
        "write_ok": False,
        "verified_ok": False,
        "row_count": 0,
        "business_day": "",
        "slot": "",
        "scheduler_slot_key": scheduler_slot_key or "",
    }
    if not scheduler_slot_key:
        return empty
    parsed = parse_slot_key(scheduler_slot_key)
    if not parsed:
        return empty
    business_day, slot_code = parsed
    cap = captured_at if captured_at is not None else datetime.now(JST)
    captured_at_ok, captured_at_warning = check_captured_at_in_slot_window(
        cap, business_day, slot_code
    )
    write_ok = write_snapshots_for_scheduler_run(
        managers=managers,
        scheduler_slot_key=scheduler_slot_key,
        trigger_source=trigger_source,
        captured_at=captured_at,
    )
    row_count = count_snapshot_rows(db, business_day, slot_code)
    verified_ok = bool(write_ok and row_count > 0)
    return {
        "write_ok": bool(write_ok),
        "verified_ok": verified_ok,
        "row_count": row_count,
        "business_day": business_day.isoformat(),
        "slot": slot_code,
        "scheduler_slot_key": scheduler_slot_key,
        "captured_at_ok": captured_at_ok,
        "captured_at_warning": captured_at_warning or None,
    }


def format_snapshot_status_for_discord(status: Optional[Dict[str, Any]]) -> str:
    if not status or not status.get("scheduler_slot_key"):
        return "（対象スロットなし）"
    base_ok = status.get("verified_ok")
    cap_warn = status.get("captured_at_warning")
    if base_ok and status.get("captured_at_ok", True):
        return (
            f"OK · {status.get('business_day')} · slot {status.get('slot')} · "
            f"{status.get('row_count')} series"
        )
    if base_ok and cap_warn:
        return (
            f"⚠️ 時刻帯外 · {status.get('business_day')} · slot {status.get('slot')} · "
            f"{status.get('row_count')} series · {cap_warn}"
        )
    row_count = status.get("row_count", 0)
    write_ok = status.get("write_ok")
    return (
        f"NG · {status.get('business_day')} · slot {status.get('slot')} · "
        f"DB {row_count}行 · write={'OK' if write_ok else '失敗'}"
    )
