#!/usr/bin/env python3
"""
Discord通知・スケジューラの簡易チェック（秘密情報は表示しない）
- 環境変数が設定されているか
- ローカルで /health と /api/alert/test を叩く場合の例
"""
import os
import sys

def main():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"
    loaded = False
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key = line.split("=", 1)[0].strip()
                if key in ("DISCORD_WEBHOOK_URL", "ENABLE_SCHEDULER"):
                    # 値は表示しない（秘密情報のため）
                    val = line.split("=", 1)[1].strip()
                    if key == "DISCORD_WEBHOOK_URL":
                        status = "設定あり" if val and "discord" in val.lower() else "未設定 or 無効"
                    else:
                        status = "true" if val.lower() == "true" else "false"
                    print(f"  {key}: {status}")
                    loaded = True
    if not loaded:
        # .env を読まなかった、または該当キーが無い → os.environ で再確認
        url = os.getenv("DISCORD_WEBHOOK_URL", "")
        print(f"  DISCORD_WEBHOOK_URL: {'設定あり' if url and 'discord' in url else '未設定 or 無効'}")
        sch = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
        print(f"  ENABLE_SCHEDULER: {sch}")

    print()
    print("--- 確認手順 ---")
    print("1) スケジューラ状態: curl -s http://localhost:5000/health | jq '.checks.scheduler'")
    print("2) Webhook状態:      curl -s http://localhost:5000/api/alert/test")
    print("   Discord テスト:   curl -X POST http://localhost:5000/api/alert/test")
    print("3) 手動で1回実行:   curl -X POST http://localhost:5000/api/scheduler/execute")
    print()
    print("スケジュール: 毎日 1:00 / 7:00 / 13:00 / 19:00 (JST)。通知はその実行後に送られます。")
    return 0

if __name__ == "__main__":
    sys.exit(main())
