# 日次 X ツイート案（2026-05-09 〜 固定型）

`daily_template.md` / `samples_2026-05-08.md` で固めた型のまま、**日付ごとに JP / US の「今日の5つ」**を並べたファイルです。

- **自動投入:** `scripts/generate_daily_x_post_series.py` が **`trend_daily_snapshots`** の **7時・13時・19時（スロット 07/13/19）**を読み、ラベルごとに「複数スロットへの登場」と「順位の上がり（07→13→19）」をスコアにして①〜⑤を選び、このファイルの該当日付ブロックを上書きします。入力は **`DATABASE_URL` で直接 DB** か、**`--from-api`** で本番の **`GET /api/summaries/daily-snapshots?business_day=…`**（AI 日次サマリーと同じ行）。ソース別の `/api/google-trends` 等は使いません（`pip install requests psycopg2-binary`）。
- **GitHub Actions:** `.github/workflows/daily-x-post-series.yml` が **JST 20:10 前後（UTC 11:10）** に `--from-api --write` を実行し、`TREND_DASHBOARD_BASE_URL`（既定で本番）の **daily-snapshots** から当日分を読み、差分があればコミットして push します。
- 一覧: [https://trends-dashboard.fly.dev/](https://trends-dashboard.fly.dev/)
- 鮮度: [https://trends-dashboard.fly.dev/data-status](https://trends-dashboard.fly.dev/data-status)

**US 返信に足す場合（任意・英語）:**

```
Dashboard refreshes on a JST schedule (1/7/13/19 JST). Same post time as our JP tweet (8pm JST ≈ US morning).
```

---

## 2026-05-09

### JP — 今日の5つ

```
【2026-05-09】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ（英語・同時刻前提）

```
Today's 5 (US) 2026-05-09 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-10

### JP — 今日の5つ

```
【2026-05-10】今日の5つ（JP）
① 株式／阿部亮平（Google）
② HAN "back to life" | [Str…（YouTube）
③ 【速報中】磐越道 部活バス21人死傷事故 …（NHK・WN）
④ CodexをローカルLLMで駆動する／WR…（Tech）
⑤ ライラック／ザ・スーパーマリオギャラク…（Apple Music・映画）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-10 · 8pm JST, same as JP (~US AM)
① rachel campos-duffy /… (Google)
② Frontier plane reportedly… (CNN)
③ A recent experience w… (HN)
④ CVE-2026-42208 · THN · cPan… (Tech)
⑤ Choosin' Texas … (Apple Music)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-11

### JP — 今日の5つ

```
【2026-05-11】今日の5つ（JP）
① 千葉 対 群馬／柳川るい（Google）
② BOYNEXTDOOR (보이넥스트도어) '똑똑…（YouTube）
③ 高市内閣支持率61％ 不支持23％ NHK…（NHK・WN）
④ コードを書かなくなった我々は何者か —— …（Tech）
⑤ 爆裂愛してる／プークーと魔法の植物（Apple Music・映画）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-11 · 8pm JST, same as JP (~US AM)
① ryan seacrest / bianc… (Google)
② Live updates: Hantavirus … (CNN)
③ Hardware Attestation … (HN)
④ CVE-2026-42208 · DEV · Meme… (Tech)
⑤ Choosin' Texas … (Apple Music)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-12

### JP — 今日の5つ

```
【2026-05-12】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-12 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-13

### JP — 今日の5つ

```
【2026-05-13】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-13 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-14

### JP — 今日の5つ

```
【2026-05-14】今日の5つ（JP）
① 超かぐや姫／入江大生（検索）
② かぐや (cv. 夏吉ゆうこ) & 月見ヤチヨ (cv.…（動画）
③ 広島 呉の船解体現場で火災 船や廃材が焼ける…（ニュース）
④ Qt 6 を Zephyr…（IT）
⑤ 夜の踊り子／プークーと魔法の植物（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-14 · 8pm JST
① pga championship tee times /… (Search)
② Backrooms | Official Promo | A24 (Video)
③ Live updates: Trump arrives in… (News)
④ CVE-2026-42208 · DEV · How to… (IT)
⑤ Choosin' Texas / Swapped (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-15

### JP — 今日の5つ

```
【2026-05-15】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-15 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-16

### JP — 今日の5つ

```
【2026-05-16】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-16 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-17

### JP — 今日の5つ

```
【2026-05-17】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-17 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-18

### JP — 今日の5つ

```
【2026-05-18】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-18 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-19

### JP — 今日の5つ

```
【2026-05-19】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-19 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-20

### JP — 今日の5つ

```
【2026-05-20】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-20 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-21

### JP — 今日の5つ

```
【2026-05-21】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-21 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## 2026-05-22

### JP — 今日の5つ

```
【2026-05-22】今日の5つ（JP）
① 黒島結菜／corinthians x…（検索）
② Replace to be -…（動画）
③ 政府・日銀の介入警戒で今週も神経質な展開か…（ニュース）
④ CodexをローカルLLMで駆動する／WR…（IT）
⑤ 爆裂愛してる／ザ・スーパーマリオギャラクシ…（エンタメ）
一覧: https://trends-dashboard.fly.dev/
```

### US — 今日の5つ

```
Today's 5 (US) 2026-05-22 · 8pm JST
① kelsey plum / atlanta braves… (Search)
② Escape 50 Pros, Win $50,000 (Video)
③ Atlanta announces Bobby Cox,… (News)
④ CVE-2026-42208 · DEV · How… (IT)
⑤ Choosin' Texas / The Super… (Entertainment)
https://trends-dashboard.fly.dev/
```

---

## この先の日付を足すとき

1. 直前の `## YYYY-MM-DD` ブロックをコピーする。
2. 見出しとフェンス内の日付を **翌日** に置換する。
3. ①〜⑤は **`DATABASE_URL` ありなら** `python scripts/generate_daily_x_post_series.py --write`、**なければ** `python scripts/generate_daily_x_post_series.py --from-api --write`（本番 `/api/summaries/daily-snapshots`）で埋める（手動で直す場合はダッシュまたは `curl` で確認）。

```bash
curl -sS "https://trends-dashboard.fly.dev/api/summaries/daily-snapshots?business_day=2026-05-15" | head
```

