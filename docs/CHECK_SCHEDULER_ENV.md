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
