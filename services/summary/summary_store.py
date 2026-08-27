"""公開用サマリー原稿の DB ストア（summary_documents テーブル）。

原稿の正本は git（docs/summaries/）のまま変えない。GitHub Actions が
生成・コミットした Markdown を ``POST /api/summaries/documents`` 経由で
ここへ upsert し、本番の閲覧ページが deploy を挟まずに最新原稿を出せる
ようにする（イメージ焼き込みだと deploy まで反映されない問題の解消）。

DB が無い環境（ローカル開発・テスト）では summary_pages.py が
リポジトリ内ファイルへフォールバックするため、本モジュールの関数は
DB エラー時に例外を投げず None / 空リスト / False を返す。
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional, Tuple

from database_config import TrendsCache
from utils.logger_config import get_logger

logger = get_logger(__name__)

KINDS = ("daily", "weekly")
REGIONS = ("jp", "us")

_DOC_ID_RES = {
    "daily": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "weekly": re.compile(r"^\d{4}-W\d{2}$"),
}

# 1原稿の上限。実際は数十KB想定で、異常な巨大 payload を弾くためのガード。
MAX_BODY_BYTES = 512 * 1024

_CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS summary_documents (
        kind VARCHAR(10) NOT NULL,
        region VARCHAR(10) NOT NULL,
        doc_id VARCHAR(20) NOT NULL,
        body_md TEXT NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (kind, region, doc_id)
    )
"""

_table_ready = False


def valid_doc(kind: str, region: str, doc_id: str) -> bool:
    """kind / region / doc_id の組み合わせが正しい形式か。"""
    if kind not in KINDS or region not in REGIONS:
        return False
    pattern = _DOC_ID_RES[kind]
    return bool(pattern.match(doc_id or ""))


def weekly_monday(week_id: str) -> Optional[date]:
    """``2026-W29`` → その ISO 週の月曜日。形式不正なら None。"""
    m = _DOC_ID_RES["weekly"].match(week_id or "")
    if not m:
        return None
    year_s, week_s = week_id.split("-W")
    try:
        return date.fromisocalendar(int(year_s), int(week_s), 1)
    except ValueError:
        return None


def _ensure_table(cache: TrendsCache) -> None:
    global _table_ready
    if _table_ready:
        return
    with cache.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(_CREATE_TABLE_SQL)
            conn.commit()
    _table_ready = True


def upsert_document(kind: str, region: str, doc_id: str, body_md: str) -> bool:
    """原稿を upsert する。DB エラー時は False（呼び出し側で 500 応答等）。"""
    if not valid_doc(kind, region, doc_id):
        return False
    try:
        cache = TrendsCache()
        _ensure_table(cache)
        with cache.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO summary_documents (kind, region, doc_id, body_md, updated_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (kind, region, doc_id)
                    DO UPDATE SET body_md = EXCLUDED.body_md, updated_at = NOW()
                    """,
                    (kind, region, doc_id, body_md),
                )
                conn.commit()
        return True
    except Exception as e:
        logger.error("❌ summary_documents upsert エラー (%s/%s/%s): %s", kind, region, doc_id, e, exc_info=True)
        return False


def has_document(kind: str, region: str, doc_id: str) -> Optional[bool]:
    """行の有無だけ見る。True=ある / False=無い / None=形式不正または DB エラー。

    本文は読まない（欠走チェック用）。DB 障害は欠走と区別するため None。
    """
    if not valid_doc(kind, region, doc_id):
        return None
    try:
        cache = TrendsCache()
        with cache.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1 FROM summary_documents
                    WHERE kind = %s AND region = %s AND doc_id = %s
                    LIMIT 1
                    """,
                    (kind, region, doc_id),
                )
                return cursor.fetchone() is not None
    except Exception as e:
        logger.warning(
            "⚠️ summary_documents 存在確認スキップ (%s/%s/%s): %s",
            kind,
            region,
            doc_id,
            e,
        )
        return None


def get_document(kind: str, region: str, doc_id: str) -> Optional[str]:
    """原稿本文を返す。行が無い・DB が使えない場合は None（ファイル fallback 用）。"""
    if not valid_doc(kind, region, doc_id):
        return None
    try:
        cache = TrendsCache()
        with cache.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT body_md FROM summary_documents
                    WHERE kind = %s AND region = %s AND doc_id = %s
                    """,
                    (kind, region, doc_id),
                )
                row = cursor.fetchone()
                return row[0] if row else None
    except Exception as e:
        # DB 未接続やテーブル未作成はファイル fallback で吸収するため warning に留める
        logger.warning("⚠️ summary_documents 取得スキップ (%s/%s/%s): %s", kind, region, doc_id, e)
        return None


def list_documents(kind: str, region: str) -> List[Tuple[str, str, datetime]]:
    """(doc_id, body_md, updated_at) を返す。DB が使えない場合は空リスト。"""
    if kind not in KINDS or region not in REGIONS:
        return []
    try:
        cache = TrendsCache()
        with cache.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT doc_id, body_md, updated_at FROM summary_documents
                    WHERE kind = %s AND region = %s
                    """,
                    (kind, region),
                )
                return [(r[0], r[1], r[2]) for r in cursor.fetchall()]
    except Exception as e:
        logger.warning("⚠️ summary_documents 一覧スキップ (%s/%s): %s", kind, region, e)
        return []


def purge_expired(
    daily_cutoff: date,
    weekly_cutoff: date,
    *,
    cache: Optional[TrendsCache] = None,
    dry_run: bool = False,
) -> dict:
    """保持期間超過の行を削除する（daily: doc_id < cutoff、weekly: ISO 週の月曜 < cutoff）。"""
    result = {"daily_rows_deleted": 0, "weekly_rows_deleted": 0, "ok": True}
    try:
        cache = cache or TrendsCache()
        _ensure_table(cache)
        with cache.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM summary_documents WHERE kind = 'daily' AND doc_id < %s",
                    (daily_cutoff.isoformat(),),
                )
                result["daily_rows_deleted"] = int(cursor.fetchone()[0])

                cursor.execute("SELECT DISTINCT doc_id FROM summary_documents WHERE kind = 'weekly'")
                expired_weeks = [
                    row[0]
                    for row in cursor.fetchall()
                    if (monday := weekly_monday(row[0])) is not None and monday < weekly_cutoff
                ]
                result["weekly_rows_deleted"] = len(expired_weeks)

                if not dry_run:
                    cursor.execute(
                        "DELETE FROM summary_documents WHERE kind = 'daily' AND doc_id < %s",
                        (daily_cutoff.isoformat(),),
                    )
                    if expired_weeks:
                        cursor.execute(
                            "DELETE FROM summary_documents WHERE kind = 'weekly' AND doc_id = ANY(%s)",
                            (expired_weeks,),
                        )
                    conn.commit()
    except Exception as e:
        logger.error("❌ summary_documents 保持クリーンアップ失敗: %s", e, exc_info=True)
        result["ok"] = False
    return result
