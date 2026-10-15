"""官公需 KKJ の低メモリ取得設定。"""

import xml.sax
from io import BytesIO

from services.trends import kkj_trends as kkj


def test_ranking_fetch_count_default(monkeypatch):
    monkeypatch.delenv("KKJ_RANKING_FETCH_COUNT", raising=False)
    assert kkj._ranking_fetch_count() == kkj.LOW_MEMORY_RANKING_COUNT


def test_ranking_fetch_count_env(monkeypatch):
    monkeypatch.setenv("KKJ_RANKING_FETCH_COUNT", "30")
    assert kkj._ranking_fetch_count() == 30


def test_ranking_fetch_count_clamped(monkeypatch):
    monkeypatch.setenv("KKJ_RANKING_FETCH_COUNT", "9999")
    assert kkj._ranking_fetch_count() == kkj._RANKING_FETCH_COUNT_HARD_MAX


def test_fetch_trends_deadline_returns_stale_path(monkeypatch):
    times = iter([1000.0, 2000.0])
    monkeypatch.setattr(kkj.time, "monotonic", lambda: next(times, 2000.0))
    monkeypatch.setenv("KKJ_FETCH_DEADLINE_SECONDS", "60")
    mgr = kkj.KKJTrendsManager.__new__(kkj.KKJTrendsManager)
    mgr.rate_limiter = type("Limiter", (), {"wait_if_needed": lambda self: None})()
    result = mgr._fetch_trends()
    assert result["success"] is False
    assert result["error"] == "kkj_fetch_deadline"


def test_sax_skips_huge_project_description():
    """ProjectDescription が巨大でも SearchHits / 案件メタだけ取れ、メモリに載せない。"""
    huge = "あ" * 200_000
    payload = f"""<?xml version="1.0" encoding="utf-8"?>
<Results>
  <SearchResults>
    <SearchHits>2</SearchHits>
    <SearchResult>
      <ProjectName>案件A</ProjectName>
      <ExternalDocumentURI>https://example.com/a.pdf</ExternalDocumentURI>
      <PrefectureName>東京都</PrefectureName>
      <OrganizationName>東京都</OrganizationName>
      <LgCode>13</LgCode>
      <CftIssueDate>2026-10-01T00:00:00+09:00</CftIssueDate>
      <ProjectDescription>{huge}</ProjectDescription>
    </SearchResult>
    <SearchResult>
      <ProjectName>案件B</ProjectName>
      <ExternalDocumentURI>https://example.com/b.pdf</ExternalDocumentURI>
      <PrefectureName>大阪府</PrefectureName>
      <OrganizationName>大阪府</OrganizationName>
      <LgCode>27</LgCode>
      <CftIssueDate>2026-10-02T00:00:00+09:00</CftIssueDate>
      <ProjectDescription>{huge}</ProjectDescription>
    </SearchResult>
  </SearchResults>
</Results>
""".encode("utf-8")

    handler = kkj._KkjSaxHandler(want_results=True, max_results=10)
    xml.sax.parse(BytesIO(payload), handler)

    assert handler.search_hits == 2
    assert len(handler.results) == 2
    assert handler.results[0]["title"] == "案件A"
    assert handler.results[0]["prefecture"] == "東京都"
    assert handler.results[0]["url"] == "https://example.com/a.pdf"
    assert handler.results[0]["cft_issue_date"] == "2026-10-01"
    assert handler.results[1]["prefecture"] == "大阪府"
    # 本文は結果 dict に載せない
    assert "description" not in handler.results[0]
    assert all(len(str(v)) < 10_000 for r in handler.results for v in r.values())


def test_sax_hits_only_skips_search_results():
    payload = b"""<?xml version="1.0" encoding="utf-8"?>
<Results>
  <SearchResults>
    <SearchHits>99</SearchHits>
    <SearchResult>
      <ProjectName>x</ProjectName>
      <ProjectDescription>should be skipped entirely</ProjectDescription>
    </SearchResult>
  </SearchResults>
</Results>
"""
    handler = kkj._KkjSaxHandler(want_results=False)
    xml.sax.parse(BytesIO(payload), handler)
    assert handler.search_hits == 99
    assert handler.results == []
