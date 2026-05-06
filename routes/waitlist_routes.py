"""Waitlist API（AIサマリー Fake door）"""

from flask import Blueprint, jsonify, request

from services.waitlist.ai_summary_waitlist_manager import AiSummaryWaitlistManager
from utils.logger_config import get_logger

logger = get_logger(__name__)

waitlist_bp = Blueprint("waitlist", __name__, url_prefix="/api/waitlist")

_manager = None


def _get_manager():
    global _manager
    if _manager is None:
        _manager = AiSummaryWaitlistManager()
    return _manager


@waitlist_bp.route("/ai-summary", methods=["POST"])
def ai_summary_waitlist():
    """Fake door からのメール登録"""
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email")
        region = (data.get("region") or "jp").strip().lower()
        source = (data.get("source") or "fake_door").strip()

        mgr = _get_manager()
        ok, message = mgr.add(email, region, source)
        if ok:
            return jsonify({"success": True, "message": message})
        return jsonify({"success": False, "error": message}), 400
    except Exception as e:
        logger.error("❌ waitlist ai-summary API エラー: %s", e, exc_info=True)
        return jsonify({"success": False, "error": "サーバーエラーが発生しました"}), 500
