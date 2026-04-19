# スケジューラ環境の確認方法

二重実行を防ぐため、本番で「gunicorn worker 数」と「Fly.io マシン数」が想定どおりか確認する手順です。

---

## 1. Gunicorn の worker 数

### 設定が上書きされていないか（コード上）

- **Dockerfile** の `CMD` を確認する  
  - 例: `CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "1200", "--workers", "1", "wsgi:app"]`  
  - `--workers 1` が入っていれば、そのイメージでは 1 worker で起動します。
- **fly.toml** で起動コマンドを上書きしていないか確認する  
  - `[processes]` の `processes = ["app"]` は「プロセス種類の名前」だけで、コマンドは Dockerfile の `CMD` のままです。  
  - `[build]` や `[env]` に `CMD` を変える設定は通常ありません。  
  - カスタムコマンドを渡している場合は `fly.toml` の `[processes]` や `Dockerfile` の `CMD` を一緒に確認してください。

### 本番で実際に何プロセスか確認する（Fly.io SSH）

アプリ名を `trends-dashboard` としています。別名なら `-a <app名>` を付けてください。

```bash
# 1. アプリのマシンに SSH
fly ssh console -a trends-dashboard
```

コンテナは `python:3.11-slim` ベースのため **`ps` コマンドは入っていません**。次のいずれかで確認します。

**方法A: Python で /proc を読む（推奨）**

```bash
python3 -c "
import os
for pid in os.listdir('/proc'):
    if not pid.isdigit():
        continue
    try:
        with open(f'/proc/{pid}/cmdline') as f:
            cmd = f.read().replace(chr(0), ' ').strip()
            if 'gunicorn' in cmd:
                print(pid, cmd[:80])
    except (FileNotFoundError, PermissionError):
        pass
"
```

**方法B: シェルで /proc を確認**

```bash
for f in /proc/[0-9]*/cmdline; do
  [ -r "$f" ] && echo -n "$f: " && cat "$f" 2>/dev/null | tr '\0' ' '; echo
done 2>/dev/null | grep gunicorn
```

**想定（workers=1 の場合）**

- `gunicorn` を含む行が **2行**（master + worker の2プロセス）なら正常です。
- 3行以上あれば、`--workers` が 2 以上で動いている可能性があります。

確認後は `exit` で SSH を抜けてください。

---

## 2. Fly.io のマシン数

### 設定ファイル（fly.toml）

```bash
# リポジトリ内
grep -E "min_machines_running|max_machines_running" fly.toml
```

- `min_machines_running = 1`  
- `max_machines_running = 1`  
なら、スケールは 1 台に制限されています。

### 本番で実際に何台動いているか（CLI）

```bash
# マシン数・VMサイズ・リージョンなどを表示
fly scale show -a trends-dashboard
```

出力例（1台の場合）:

```
VM Resources
...
Machines
PROCESS ID              REGION  STATE   CHECKS
app     xxxxxxxx-xxxx    nrt     started ...
```

- `Machines` の行数が **1行（1台）** なら想定どおりです。  
- 2行以上あれば、その時点では複数マシンが起動しています。

### Web ダッシュボード

1. https://fly.io/dashboard にログイン  
2. 対象アプリ `trends-dashboard` を開く  
3. 「Machines」や「Scale」の画面で、現在のマシン数と min/max を確認  

---

## 3. まとめチェックリスト

| 確認項目               | どこで見る           | 望ましい値 |
|------------------------|----------------------|------------|
| Gunicorn worker 数     | Dockerfile CMD       | `--workers 1` |
| 実際の gunicorn プロセス | `fly ssh console` → `ps aux \| grep gunicorn` | master + worker の 2 プロセス |
| マシン数（設定）       | `fly.toml`           | `min/max_machines_running = 1` |
| マシン数（実際）       | `fly scale show`     | 1 台 |

これらがすべて 1 であれば、スケジューラは「1 マシン × 1 worker」で動いており、先に入れた DB ロックの修正と合わせて二重実行は起きにくくなります。

---

## 4. Discord が来ない場合（コミット 94794d 以降）

DB ロックを「他が保持中」のときはファイルロックにフォールバックしないようにしたため、**ロックを取れなかったプロセスは実行も Discord 送信もしません**。以下を確認してください。

### ログでスキップが出ていないか

- 本番ログで `スケジューラーDB分散ロックは他プロセスが保持中のためスキップ` が出ている場合、**別プロセス/別マシンがロックを取っており、このプロセスでは実行していません**。
- その場合、**ロックを取った側**のプロセスで実行と Discord 送信が行われているはずです。ロックを取った側がクラッシュやタイムアウトで落ちていると、誰も Discord を送れません。

### ロック状態の確認

```bash
# アプリの /api ベース URL を指定
curl -s "https://あなたのアプリ.fly.dev/api/scheduler/lock-status"
```

- `lock` が `null` または `holder_id` が `null` なら未使用。
- `holder_id` が入っていて `lock_until` が未来なら、その時刻まで別プロセスがロック保持中です（有効期限はデフォルト 30 分）。

### 実行が長すぎてワーカーが落ちていないか

- Gunicorn の `--timeout`（例: 1200 = 20 分）より長く `refresh_all_trends` がかかると、ワーカーが強制終了し、**そのプロセスでは Discord 送信まで届きません**。ロックは 30 分で自動解放されるため、次回のスケジュール実行時は別プロセスが実行できます。
- タイムアウトを十分大きくする（例: `--timeout 1200`）か、トレンド取得の負荷を下げてください。

---

## 5. 外部 cron との二重トリガーに注意

アプリ内の **APScheduler** がすでに **1:00 / 7:00 / 13:00 / 19:00（JST）** にトレンド取得を実行しています。

**やってはいけないこと**

- 上記と同じ時刻に、**外部の cron サービス**（cron-job.org、Fly.io Cron、GitHub Actions など）で  
  `POST /api/scheduler/execute` を叩かないでください。  
- 同じ時刻に「APScheduler」と「外部 cron」の両方が動くと、**二重実行**になり、Discord に同じ時刻で 2 通（例: 7:00 と 7:17）届くことがあります。

**推奨**

- 定期実行は **APScheduler のみ**に任せる。  
- マシンを起こす目的で外部 cron を使う場合は、**実行はさせず** `GET /health` だけにし、起動は 7:00 などスケジュール時刻の少し前（例: 6:55）にすると安全です。

---

## 6. デプロイ時刻の調整（二重実行防止）

ローリングデプロイ時に新旧マシンが同時に存在する間、両方のスケジューラが同じ時刻（例: 7:00）に発火し、二重実行になることがあります。DBロックで抑止されますが、念のため以下を推奨します。

**推奨**

- デプロイは **1:00 / 7:00 / 13:00 / 19:00（JST）の前後 10 分を避ける**（例: 6:50〜7:10、12:50〜13:10 など）。
- 自動デプロイや CI/CD を使う場合、 cron やスケジュールを上記時刻からずらす。

---

## 7. 二重実行が疑われる場合の調査

Discord 通知の **実行ID** と **ホスト・プロセスID** で、どのマシン・プロセスで実行されたか判別できます（コミット以降）。

- 実行IDの形式: `scheduler_YYYYMMDD_HHMMSS_MMM_p{PID}`（例: `scheduler_20260223_070000_032_p12`）
- 通知の「ホスト」「プロセスID」フィールドを確認
- ログで `[二重実行防止]` を含む WARNING が出ていれば、ロックでスキップされた側

---

## 8. OOM（Out of memory）と Discord

### アプリ内でできること

- **OOM が起きた瞬間**はプロセスが SIGKILL されるため、**その場で Discord を送ることはできない**（Python が動かない）。
- 代わりに **`utils/memory_watchdog`** が、cgroup の上限に対する **RSS 比率**を定期的に見て、**逼迫時に事前通知**する（`DISCORD_WEBHOOK_URL` があり、`DISCORD_MEMORY_PRESSURE_ALERT` が true のとき）。閾値は環境変数 `MEMORY_PRESSURE_WARN_RATIO` / `MEMORY_PRESSURE_CRITICAL_RATIO` で調整可能。
- **Webhook の生存確認**: `GET /api/alert/test` で `webhook_configured` と現在のメモリ概算を JSON で返す（送信はしない）。テスト送信は `POST /api/alert/test`。

### Grafana / Fly ログで「Out of memory」を監視

- ログ検索クエリ例: `Out of memory` または `Killed process` / `gunicorn`（カーネルが OOM した行を拾う）。
- **Grafana アラート**で上記にマッチしたら通知チャネルへ（公式の Discord 通知や Webhook 連携を利用）。これが「OOM 発生後」の確実な検知手段になる。

### 本番での確認コマンド例

```bash
curl -s "https://あなたのアプリ.fly.dev/api/alert/test"
curl -s -X POST "https://あなたのアプリ.fly.dev/api/alert/test"
```
