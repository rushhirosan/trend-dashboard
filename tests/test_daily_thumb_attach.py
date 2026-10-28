"""日次サムネは同じ話題ならコピーし、変わった日だけ生成する。"""

from services.summary.daily_thumbs import attach_one, safe_fallback_topic, topic_key


JP_25 = "ニュースでは「テスト設計エージェント「TESTRA」」が上位に（7時3位 → 13時3位 → 19時2位）。"
JP_26 = "ニュースでは「テスト設計エージェント「TESTRA」」が上位に（7時5位 → 13時2位 → 19時1位）。"
US_GAME = 'News lead: 「Phantom Blade Zero Review」 (out@7 → out@13 → #3@19).'


def _md(lead: str) -> str:
    escaped = lead.replace("\\", "\\\\").replace('"', '\\"')
    return f'---\npreview_lead: "{escaped}"\n---\n\n本文\n'


def test_topic_key_ignores_rank_movement():
    assert topic_key(JP_25) == topic_key(JP_26)
    assert topic_key(US_GAME) != topic_key(JP_26)
    assert "7時" not in topic_key(JP_25)
    assert "out@7" not in topic_key(US_GAME)


def test_attach_reuses_image_when_topic_continues(tmp_path):
    docs = tmp_path / "docs"
    thumbs = tmp_path / "thumbs"
    docs.mkdir()
    thumbs.mkdir()
    (docs / "2026-10-25.md").write_text(_md(JP_25), encoding="utf-8")
    (docs / "2026-10-26.md").write_text(_md(JP_26), encoding="utf-8")
    (thumbs / "2026-10-25.jpg").write_bytes(b"same-jpeg")
    called = []

    result = attach_one(
        docs,
        thumbs,
        "2026-10-26",
        generate=lambda topic: called.append(topic) or b"new",
    )

    assert result == "reuse"
    assert called == []
    assert (thumbs / "2026-10-26.jpg").read_bytes() == b"same-jpeg"


def test_attach_reuses_across_a_day_that_has_no_image(tmp_path):
    docs = tmp_path / "docs"
    thumbs = tmp_path / "thumbs"
    docs.mkdir()
    thumbs.mkdir()
    (docs / "2026-10-24.md").write_text(_md(JP_25), encoding="utf-8")
    (docs / "2026-10-25.md").write_text(_md(JP_26), encoding="utf-8")
    (docs / "2026-10-26.md").write_text(_md(JP_26), encoding="utf-8")
    (thumbs / "2026-10-24.jpg").write_bytes(b"older")

    result = attach_one(docs, thumbs, "2026-10-26", generate=lambda topic: b"new")

    assert result == "reuse"
    assert (thumbs / "2026-10-26.jpg").read_bytes() == b"older"


def test_attach_generates_when_topic_changes(tmp_path):
    docs = tmp_path / "docs"
    thumbs = tmp_path / "thumbs"
    docs.mkdir()
    thumbs.mkdir()
    (docs / "2026-10-25.md").write_text(_md(JP_25), encoding="utf-8")
    (docs / "2026-10-26.md").write_text(_md(US_GAME), encoding="utf-8")
    (thumbs / "2026-10-25.jpg").write_bytes(b"robot")

    result = attach_one(docs, thumbs, "2026-10-26", generate=lambda topic: b"blade")

    assert result == "generated"
    assert (thumbs / "2026-10-26.png").read_bytes() == b"blade"
    assert not (thumbs / "2026-10-26.jpg").exists()


def test_attach_leaves_day_blank_when_generation_fails(tmp_path):
    docs = tmp_path / "docs"
    thumbs = tmp_path / "thumbs"
    docs.mkdir()
    (docs / "2026-10-26.md").write_text(_md(US_GAME), encoding="utf-8")

    result = attach_one(docs, thumbs, "2026-10-26", generate=lambda topic: None)

    assert result == "missing"
    assert list(thumbs.glob("*")) == []


def test_attach_does_not_replace_an_existing_thumb(tmp_path):
    docs = tmp_path / "docs"
    thumbs = tmp_path / "thumbs"
    docs.mkdir()
    thumbs.mkdir()
    (docs / "2026-10-26.md").write_text(_md(US_GAME), encoding="utf-8")
    (thumbs / "2026-10-26.jpg").write_bytes(b"keep")

    result = attach_one(docs, thumbs, "2026-10-26", generate=lambda topic: b"new")

    assert result == "skip"
    assert (thumbs / "2026-10-26.jpg").read_bytes() == b"keep"


def test_safe_fallback_topic_softens_military_leads():
    fighter = topic_key(
        "ニュースでは「日英伊の次期戦闘機、英国がドイツに呼びかけ」が上位に（7時圏外 → 13時1位）。"
    )
    assert "summit" in safe_fallback_topic(fighter)
    assert "spotlight" in safe_fallback_topic("普通のニュース見出し")
