# Fly.ioデプロイ トラブルシューティング

## 問題: デプロイが中断される（503/504エラー）

### 症状
- `fly deploy`コマンドが長時間実行され、中断される
- エラーメッセージ: `503 Service Unavailable` または `504 Gateway Time-out`
- `Depot builder`関連のエラーが表示される

### 原因
Fly.ioのリモートビルドサービス（Depot builder）が一時的に不安定な場合に発生します。

### 解決策

#### 1. 時間をおいて再試行
Depot builderの問題は一時的なことが多いため、数分待ってから再デプロイを試してください。

```bash
fly deploy -a trends-dashboard
```

#### 2. ローカルビルドを使用（Dockerが必要）
ローカルでDockerが利用可能な場合：

```bash
fly deploy -a trends-dashboard --local-only
```

#### 3. WireGuard WebSocketを有効化
ネットワークの問題が原因の場合：

```bash
fly wireguard websockets enable
fly deploy -a trends-dashboard
```

#### 4. ビルドキャッシュをクリア
ビルドキャッシュの問題が原因の場合：

```bash
fly deploy -a trends-dashboard --no-cache
```

#### 5. 通常のビルダーを使用（Depotをスキップ）
Depot builderをスキップして通常のビルダーを使用：

```bash
# fly.tomlに以下を追加
[build]
  builder = "paketobuildpacks/builder:base"

# または環境変数で指定
export FLY_BUILDER=paketobuildpacks/builder:base
fly deploy -a trends-dashboard
```

### 確認方法

デプロイが成功したかどうか確認：

```bash
# アプリケーションの状態確認
fly status -a trends-dashboard

# ログ確認
fly logs -a trends-dashboard

# アプリケーションのURL確認
fly open -a trends-dashboard
```

### 備考

- デプロイは通常5-10分かかります
- ビルド時間は依存関係の数によって異なります
- サーバー側の問題の場合は、時間をおいて再試行するのが最善です

