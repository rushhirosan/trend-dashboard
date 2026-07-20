# X 日次投稿ガイド

> **運用停止（2026-07）— 本ドキュメントの自動運用はすべて使用していない。**
> Daily X post series（GHA workflow 削除済み・Discord 通知停止・X 投稿なし）。
> 以下は **停止前の設計メモ・手書きテンプレ・過去例** のみ。読み物の本体は **AI 日次サマリー**（`docs/summaries/daily/`）。

Trend Dashboard 向け **1日1ツイート（20時 JST）** の運用メモ・コピペテンプレ・過去に本番キャッシュで作った参考例を1つにまとめたものです。週1振り返りは [`weekly_template.md`](weekly_template.md)。**あくまでサンプル** — 投稿前にダッシュの更新時刻・文言を確認してください。

## 運用メモ（プロダクト仕様との整合）

<!-- 以下: 停止前の設計。現行運用では使用していない。 -->

- トレンド一括取得は **1 / 7 / 13 / 19 時（JST）** のスケジューラ実行がベース（**ダッシュボード更新は継続**）。
- ~~**20時投稿**~~ — **X 日次投稿は停止（2026-07）**
- ~~**JP / US を同じ JST 20:00**~~ — 停止前の設計メモ（`同時刻運用` 節参照）
- **現行の日次読み物:** **朝 6:50 JST** の **AI 日次サマリー**（`docs/summaries/daily/`）のみ
- **使用していない（停止済み）:**
  - GHA `Daily X post series` — workflow ファイル削除済み
  - Fly 19時 Discord — `services/daily_x_post_notify.py`（スケジューラ連携削除・env 既定 `false`）
  - X への手動投稿 — 運用なし
- **手動のみ（非本番）:** `scripts/generate_daily_x_post_series.py --write` で md を試せる

## ファイルの置き場

| 種別 | パス |
|------|------|
| **このガイド** | `daily_guide.md`（運用・テンプレ・過去の参考例） |
| **週次** | `weekly_template.md` |
| **自動生成** | ~~`daily/YYYY-MM-DD.md`~~ — **使用していない**（手動 `--write` のみ） |

サマリー原稿の運用は [`docs/summaries/README.md`](../summaries/README.md) を参照。


---

## テンプレート（毎日 20:00 · デイリー1ツイート）

<!-- 停止前のテンプレ。現行運用では使用していない。 -->

### 同時刻運用（JP + US）

**一旦の運用:** 日本語ポストと英語（US）ポストを **同じ JST 20:00** に出す。米国ではだいたい**朝**になるため、**US 側の先頭に前提を1行**入れる（例: 投稿が JST 夜であること・JP と同時・ダッシュは JST 更新サイクル）。文字が足りないときは前提だけ **返信ツイート** に分ける。

### テンプレート（コピペ用）

```
【今日のトレンド要約 YYYY-MM-DD】
JP: ・○○ ・○○ ・○○
US: ・○○ ・○○ ・○○
交差: （両方で見えたら1行 / なければ「—」）
反映: 当日分は主に13:00・19:00（JST）更新を想定
一覧: https://trends-dashboard.com/
```

※ URL は本番の公開 URL に合わせてください。

---

### ルール（簡易）

- JP / US **各3つ**を目安（収まらないときは各2つに落とす）。
- **断定は弱め**（「一覧上では〜が目立つ」など）。
- **ハッシュタグ**は使わないか、1個まで。

---

### 埋め例（実データではないダミー）

```
【今日のトレンド要約 2026-05-07】
JP: ・大型スポーツイベント関連 ・株・為替の短期的な話題 ・連休・旅行需要の話題
US: ・ハイテク決算・AI関連 ・選挙・政策ニュース ・エンタメ award シーズン
交差: —
反映: 当日分は主に13:00・19:00（JST）更新を想定
一覧: https://trends-dashboard.com/
```

---

### 1ポスト＝「今日の急上昇3つ」（旧・自動生成テンプレ — **使用していない**）

停止前は `generate_daily_x_post_series.py` の出力型。選定ロジック自体は `scripts/snapshot_rising.py` 経由で **AI 日次サマリーが引き続き利用**。

```
【YYYY-MM-DD】今日の急上昇3つ（JP）
① …（検索）
② …（動画）
③ …（ニュース）
一覧: https://trends-dashboard.com/
```

US 英語ブロックは `Today's rising 3 (US) YYYY-MM-DD · 8pm JST` 見出し。末尾は **`一覧: https://trends-dashboard.com/us`**（JP はルート URL）。欄名だけのラベル（`Pickup` 等）は選定から除外する。

---

### 1ポスト＝「今日の3つ」（手書き・3件）

カテゴリ一覧ではなく **入口だけ** に絞る日向け。JP だけ / US だけでもよい。

#### 選び方（目安）

- **同じ話題の重複を避ける**（検索とニュースで同じなら、片方は別カテゴリにする）。
- **レイヤーを混ぜる**（例：大衆向け1・報道1・開発／サイバー1）。
- キャッシュが古いソースから取るときは **（鮮度注意）** など一言添える。

#### テンプレ A · ミニマル

```
【YYYY-MM-DD 今日の3つ / JP】
1) …
2) …
3) …
```

#### テンプレ B · 一覧へ誘導（推奨）

```
【YYYY-MM-DD】今日の3つ（JP）
① …（Google）
② …（World News）
③ …（Zenn）
一覧: https://trends-dashboard.com/
```

出典は **カッコ1語** に留め、本文は **12〜25文字程度** で要約してよい（長い公式タイトルは途中で切る）。

#### テンプレ C · US を1つだけ同居

```
【YYYY-MM-DD】今日の3つ
JP: … / … / …
US: …（HN）
一覧: https://trends-dashboard.com/
```

文字数が厳しい日は **USは省略**してテンプレ B に戻す。

---

### 1ポスト＝「今日の5つ」（①〜③ + ④Tech + ⑤エンタメ）

①〜③は **検索・動画（またはコミュニティの注目）・報道** など「今日」と言い切りやすい軸。④を **Tech**（開発・セキュリティ・プロダクト）、⑤を **エンタメ**（音楽・映画・Podcast 等）に固定すると毎回迷いにくい。

**X の文字数:** 無料は **最大 280 文字**（`https://` リンクは **約 23 文字分**として数えられることが多い）。**5 行は余裕がない**ので、長い公式名は略語にし、**US 英語**はテンプレ F の **1行目に同時刻前提**を入れると文字が詰まる。**2 ポスト目に④⑤**、または **前提だけ返信**、または項目を減らす。

#### テンプレ E · 5つ（JP）

```
【YYYY-MM-DD】今日の5つ（JP）
① …（Google）
② …（YouTube）
③ …（NHK または WN）
④ …（Zenn など Tech）
⑤ …（Apple Music チャートなど エンタメ）
一覧: https://trends-dashboard.com/
```

#### テンプレ F · 5つ（US · 英語）

1行目に **同時刻（JST）前提** を入れる（無料 280 文字なら短文で）。

```
Today's 5 (US) YYYY-MM-DD · 8pm JST, same as JP (~US AM)
① … (Google)
② … (CNN)
③ … (HN)
④ … (Tech)
⑤ … (Apple Music / film)
https://trends-dashboard.com/
```

**前提だけ返信に出す場合（英語）:**

```
Same post time as our JP tweet: 8pm JST (~US morning). US view reflects the dashboard’s JST refresh cycle (1/7/13/19 JST).
```

---

## 参考例 · 2026-05-07

本文は **本番の Trend Dashboard API（キャッシュ）を参照して作成したサンプル**です。  
実際の投稿直前に、画面上の更新時刻・文言を必ず確認してください。

---

### データの出どころ（サンプル作成時）


| 参照API                                  | 取り上げた観点                |
| -------------------------------------- | ---------------------- |
| `/api/google-trends?country=JP`        | 検索トレンド上位キーワード          |
| `/api/google-trends?country=US`        | 同上（US）                 |
| `/api/worldnews-trends?country=jp`     | ニュース見出し（JP向けフィード）      |
| `/api/nhk-trends`                      | NHK ニュース一覧             |
| `/api/youtube-trends?region=JP` / `US` | 急上昇動画タイトル              |
| `/api/hackernews-trends`               | Hacker News（主にUSテック文脈） |


**キャッシュ時刻の例（Google / NHK / HN など）:** `cache_as_of` ≈ `2026-05-06T22:41:21`（API応答値・DB保存形式。タイムゾーンは運用環境に依存）

定期ジョブは **1 / 7 / 13 / 19 時（JST）** の取得がベースですが、**ソースごとに最終更新時刻は一致しません**。投稿文の「反映」は「その日の複数スロット取得結果がキャッシュに載っている」旨に留めると安全です。

---

### A. おすすめ（JP・USで「注目」を具体語にした全文）

**ポイント:** JP は「検索 + 報道 + 動画」、US は「検索 + HN + 動画」。交差は中東・エネルギー・金融ニュースが両岸で顔を出している前提で1行。

```
【今日のトレンド要約 2026-05-07】

▼JP
・検索（Google）: 森且行 / エスワティニ / 齊藤京子 ほか
・報道（World News）: ホルムズ海峡・船舶、ギャル式会議の広がり など
・NHK: NYダウ・ナスダック・S&P最高値更新、「米とイランが覚書で合意に近づく」報道 など
・動画（YouTube）: BABYMONSTER「춤」、Snow Man「BANG!!」 ほか

▼US
・検索（Google）: knicks game tonight / bonnie tyler hospitalized portugal / star fox ほか
・HN: Valve が Steam Controller の CAD を公開、職場での「見せかけの生産性」話題 など
・動画（YouTube）: The Odyssey 予告、Paramount+「Dutton Ranch」予告 ほか

交差: 地政学・エネルギー（JP側はホルムズ／イラン関連報道、NHKでは米ガソリン価格や米・イラン報道も）

反映: 当日は 7:00 / 13:00 / 19:00（JST）の取得ジョブ由来のキャッシュを前提に要約
一覧: https://trends-dashboard.com/
```

---

### B. 短め（280文字に寄せる場合・項目は削ぎ落とし）

```
【今日のトレンド要約 2026-05-07】
JP: Google→森且行・エスワティニ・齊藤京子 / News→ホルムズ・ギャル式会議 / NHK→株高・米・イラン報道 / YT→BABYMONSTER・Snow Man
US: Google→Knicks・Bonnie Tyler・Star Fox / HN→Valve CAD公開・職場ネタ / YT→The Odyssey・Dutton Ranch
交差: 中東・エネルギー・株・イラン関連が日米ともに顔を出す一日
反映: 7/13/19時取得ベースのキャッシュ
一覧: https://trends-dashboard.com/
```

（文字数はクォートの改行・空白を削れば X の上限に寄せられる。）

---

### C. 丁寧モード（断定を弱める）

```
【今日のトレンド要約 2026-05-07】（ダッシュ上の印象）

▼JP
検索トレンドでは芸能・国名キーワードが上位。ニュースではホルムズ周辺や職場カルチャー系が目立つ。NHKでは米市場・イラン関連のヘッドラインが並ぶ。

▼US
検索はスポーツ・芸能・ゲーム reboot などバラエティ。HN は開発者文化・職場論が上位。動画は映画・ドラマ予告が目立つ。

交差: エネルギー・地政学（ソース横断で「同じテーマが続く」程度の書き方）

一覧: https://trends-dashboard.com/
```

---

### 週次サンプル（別曜日に出す前提・中身はダミー）

今日のデイリーだけ実データ起点にした場合、週次は **金曜 or 日曜の20時** に、同じフォーマットで「その週にデイリーで繰り返し出た語」を手で集約するのがおすすめ。

```
【今週の振り返り 2026-05-01〜2026-05-07】
JPよく出た: （その週のデイリーから集約）
USよく出た: （同上）
今週の印象: （1行）
一覧: https://trends-dashboard.com/
```

---

### 再生成のしかた

同じ構成で **最新キャッシュ** に差し替えるときは、本番から JSON を取ってキーワード・見出しを差し替えればよい。

```bash
curl -sS "https://trends-dashboard.com/api/google-trends?country=JP&force_refresh=false" | jq '.data[:8]'
curl -sS "https://trends-dashboard.com/api/nhk-trends?force_refresh=false" | jq '.data[:5]'
```

`jq` が無い環境では、返却 JSON の `data` 配列をブラウザの開発者ツールやエディタで見ても同じ。

---

## 参考例 · 2026-05-08

本ファイルのテーブルは、本番 `https://trends-dashboard.com/api/*` を自動取得したスナップショットです。

- **取得時刻:** `GENERATED_AT_UTC` ≈ **2026-05-07T22:29:03Z**
- **使い方:** 投稿直前にもう一度 API かサイトで確認し、日付と文言を差し替えること。

---

### 取得時のメモ


| 状況                        | カテゴリ                                                                                        |
| ------------------------- | ------------------------------------------------------------------------------------------- |
| レスに `cache_as_of` が付かなかった | World News（JP/US）                                                                           |
| `(データなし)`                 | BLS、USAspending（`/us-admin-trends` 経由）                                                      |
| `cache_as_of` が他より古い      | 楽天（**2026-02-07** と表示。鮮度は [/data-status](https://trends-dashboard.com/data-status) で確認） |


---

### JP — カテゴリごとのハイライト（各先頭〜2件）


| カテゴリ          | ハイライト                                                                        |
| ------------- | ---------------------------------------------------------------------------- |
| Google        | グローバル・タッグ・リーグ戦 / 高橋 遥 人                                                      |
| YouTube       | ILLIT 「It's Me」Official MV (Performance ver.) / Motoki Ohmori「催し」Official MV |
| Apple Music   | 爆裂愛してる / 好きすぎて滅!                                                             |
| World News    | 「アゲだね！」ギャル式会議拡大… / ホルムズ封鎖、沿岸に見えた黒煙…                                          |
| Podcast       | ヤング日経（サクッとわかるビジネスニュース） / 夢を叶える英語術                                            |
| 楽天            | 母の日・カーネーション等。（キャッシュ日付要注意）                                                    |
| はてな           | 認知負債 - kawasima / 趣味にすぐ飽きる人と…｜かぽ                                             |
| NHK           | イラン複数メディア「米軍が船舶を攻撃…」 / 自賠責の保険料 13年ぶり引き上げ                                     |
| Qiita         | 個人開発の運用コストを本当に0円に… / GW勉強向け技術書まとめ                                            |
| PR TIMES      | 都市ガス SNS / AYAKO SAKURAI 銀座蔦屋イベント                                            |
| Wikipedia(ja) | 細木数子 / ハンタウイルス                                                               |
| GitHub        | build-your-own-x / awesome                                                   |
| App Store     | ジハンピ / TikTok Lite                                                           |
| IPA           | Windows 10 のサポート終了の注意喚起 / FileZen OSコマンドインジェクション（JVN#84622767）               |
| JPCERT        | PackageKit TOCTOU / PHPUnit 引数インジェクション                                       |
| Zenn          | Web 標準動向 2026年4月版 / AI の Plan Mode をなんとなく承認しないために                            |
| Note          | 編集賞（浦岡敬一賞）選考理由 / Claude と Google マップタイムライン                                   |
| OpenAlex(JP)  | TheYKHC Journal Vol.1 — The Genesis / A2.5 価値観テンソル…（論文タイトル長め）                |
| Bluesky(JP)   | 息抜き / 夏の暑さを思い出した                                                             |
| 株(JP)         | ソフトバンクグループ / 住友電気工業                                                          |
| 暗号資産          | Bitcoin / Ethereum                                                           |
| 映画(JP)        | ザ・スーパーマリオギャラクシー・ムービー / エイペックス・プレデター                                          |
| 本(JP)         | キングダム 79 / BLUE GIANT MOMENTUM（8）                                            |
| 行政            | e-Stat 先頭: `cpi` / 調達シグナル: **AI関連** 約294・`trend: up`（詳細は `/admin-trends`）    |


※ 音楽チャート（JP/US 共通）は **Apple Music RSS**（most-played）由来。REST では従来どおり `music-trends?service=spotify` などの表記のことがある。

---

### US — カテゴリごとのハイライト


| カテゴリ            | ハイライト                                                                     |
| --------------- | ------------------------------------------------------------------------- |
| Google          | gta online / deportación                                                  |
| YouTube         | The Odyssey                                                               |
| Apple Music     | Choosin' Texas / I Can't Love You Anymore                                 |
| World News      | Class-A war criminals feature / PM Modi 鉄道プロジェクト                          |
| Podcast         | Digital Social Hour / The Dylan Gemelli Podcast                           |
| Hacker News     | The Burning Man MOOP Map / Chrome On-device AI 表記                         |
| Product Hunt    | Brila / Fathom 3.0                                                        |
| CNN             | Andes hantavirus / Craig Berry 関連                                         |
| GlobeNewswire   | Acadian Timber 取締役選 / BioSyent 決算日程                                       |
| Medium          | Cybercrime / AI Predictive Analytics                                      |
| DEV.to          | Gemma 4 Challenge / Google Cloud NEXT Winners                             |
| Wikipedia(en)   | Vijay (actor) / 2026 Tamil Nadu Legislative Assembly election             |
| CISA KEV        | CVE-2026-6973 / CVE-2026-0300                                             |
| The Hacker News | Ivanti EPMM CVE-2026-6973 / PCPJack                                       |
| BLS             | （データなし）                                                                   |
| USAspending     | （データなし）                                                                   |
| OpenAlex(US)    | African Journal of Biotechnology / African Journal of Business Management |
| Bluesky         | superb fairywren / FEMA Texas floods                                      |
| 株(US)           | Fortinet / CRWD                                                           |
| 映画(US)          | The Super Mario Galaxy Movie / Apex                                       |
| 本(US)           | The Odyssey of Homer / The Illustrated Art of War                         |
| App Store       | Grok / Canva                                                              |


---

### X — スレッド案

#### 1/4

```
【今日のハイライト 2026-05-08】JP・USとも、ダッシュ上のソース別キャッシュからカテゴリごとに要約（定期取得は 1/7/13/19 時 JST 起点）。
↓続く
```

#### 2/4 · JP

```
▽JP
Google・YT・Apple Music／NHK・World News／はてな・Qiita・Zenn・Note／株・暗号・映画・本／行政（e-Stat・調達）。詳細文言はサイトのタブ単位。
```

#### 3/4 · US

```
▽US
Google・YT・Apple Music、HN・CNN・サイバー（CVE）、Globe／Medium／DEV、Wiki・アプリ。※BLS・USAspending は当時キャッシュ空。
```

#### 4/4

```
一覧: https://trends-dashboard.com/
```

---

### X — 1ツイート圧縮版

```
【2026-05-08】JP: 検索・報道〜開発コミュニティ・株/エンタメ・行政。US: 検索・動画・HN/CNN・CVE。カテゴリ別→ https://trends-dashboard.com/
```

---

### X — 今日の5つ案（①〜③根拠重視 + ④Tech + ⑤エンタメ）

**①〜③** は「今日トレンド」と言い切れる根拠が厚い軸（検索・動画・報道）。**④** は開発／セキュリティ／プロダクト寄りの **Tech**。**⑤** は音楽・映画など **エンタメ**（②の YouTube と役割が近い日は、⑤を **Apple Music** チャート・映画・本に寄せて被りを減らす。データは Apple Music RSS、サイト/API のラベルが混在することがある）。

**運用（一旦）:** **JP と US を同じ時刻（JST 20:00）**に出す。US 向け英語ポストは現地ではだいたい**朝**になるので、**冒頭に前提を一文**入れる（ダッシュの更新も **1/7/13/19 JST** 基準であることと整合させやすい）。

**文字数（X）:** 無料アカウントは **投稿最大 280 文字**（有料プランは長文可）。`https://…` は表示が短くても **概ね 23 文字分**としてカウントされる想定で、本文は **280 以内**に収めること。下の **JP は短文版**（長い公式タイトルは省略）。**US は英語＋前提1行**（下例は 276 文字前後）。それでも厳しい日は **2ポスト目に④⑤だけ**、または前提を返信に分ける。

#### JP（280 文字以内の圧縮例）

```
【2026-05-08】今日の5つ（JP）
① タッグ・リーグ戦／高橋遥人（Google）
② ILLIT「It's Me」Perf.ver.（YouTube）
③ イラン船舶攻撃／ホルムズ沿岸（NHK・WN）
④ Plan Mode記事／PHPUnit注入（Zenn・JPCERT）
⑤ 爆裂愛してる／マリオG映画（Apple Music・映画）
一覧: https://trends-dashboard.com/
```

- **①〜③** … 前段の「根拠重視3つ」と同じ趣旨。World News はこの日 `cache_as_of` が付かなかったため投稿前に鮮度確認。
- **④** … Qiita「運用コスト0円」、IPA 注意喚起などに差し替え可。
- **⑤** … Podcast・本（キングダム等）に置き換えてもよい。

#### US（英語・280 文字以内 · 同時刻前提つき）

```
Today's 5 (US) 2026-05-08 · 8pm JST, same as JP (~US AM)
① gta online / deportación (Google)
② Andes hantavirus (CNN)
③ MOOP map / Chrome AI (HN)
④ CVE-2026-6973 · CISA/THN · Gemma 4 (Tech)
⑤ Choosin' Texas / Mario Galaxy · Apex (Apple Music)
https://trends-dashboard.com/
```

- **1行目** … 日本 20 時＝米国朝であること、JP と同時投稿であることを明示。長文化するなら返信に **「Dashboard refreshes on a JST schedule (1/7/13/19).」** などを足す。
- **①〜③** … 検索・ケーブルニュース・HN で「いま」のレイヤーを分ける。
- **④** … 脆弱性・開発チャレンジ寄り。Product Hunt などに置き換え可。
- **⑤** … YouTube 先頭が目立つ日は **⑤に YouTube** を足すか **App Store**（Grok 等）を混ぜてもよい。

---

### 同じリストを取り直す（例）

```bash
curl -sS "https://trends-dashboard.com/api/google-trends?country=JP&force_refresh=false"
```
