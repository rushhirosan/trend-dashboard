"""
OpenAlex トレンドマネージャー

OpenAlex: 学術論文・著者・機関のオープンデータベース
- 認証不要（mailtoパラメータを追加すると高速プールにアクセス可能）
- ドキュメント: https://docs.openalex.org/
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)


class OpenAlexTrendsManager(BaseTrendsManager):
    """OpenAlex学術論文トレンド管理クラス"""

    BASE_URL = "https://api.openalex.org"

    # 研究分野のマッピング（OpenAlex concept → 日本語）
    CONCEPT_MAPPING = {
        "artificial intelligence": "人工知能",
        "machine learning": "機械学習",
        "deep learning": "ディープラーニング",
        "natural language processing": "自然言語処理",
        "computer vision": "コンピュータビジョン",
        "robotics": "ロボティクス",
        "climate change": "気候変動",
        "quantum computing": "量子コンピューティング",
        "biotechnology": "バイオテクノロジー",
        "neuroscience": "神経科学",
        "medicine": "医学",
        "biology": "生物学",
        "chemistry": "化学",
        "physics": "物理学",
        "mathematics": "数学",
        "computer science": "コンピュータサイエンス",
        "engineering": "工学",
        "economics": "経済学",
        "psychology": "心理学",
        "sociology": "社会学",
    }

    # カテゴリ別の検索キーワード
    CATEGORIES = {
        "ai": {
            "name": "AI・機械学習",
            "search": "artificial intelligence OR machine learning OR deep learning",
        },
        "nlp": {
            "name": "自然言語処理",
            "search": "natural language processing OR large language model OR transformer",
        },
        "climate": {
            "name": "気候・環境",
            "search": "climate change OR sustainability OR renewable energy",
        },
        "biotech": {
            "name": "バイオテクノロジー",
            "search": "biotechnology OR CRISPR OR gene therapy",
        },
        "quantum": {
            "name": "量子技術",
            "search": "quantum computing OR quantum machine learning",
        },
        "medical": {
            "name": "医学・ヘルスケア",
            "search": "medical OR healthcare OR drug discovery",
        },
        "trending": {
            "name": "最新トレンド",
            "search": None,  # 検索なし、最新の被引用数で取得
        },
    }

    def __init__(self):
        """初期化"""
        super().__init__(service_name="openalex", max_requests=50, window_seconds=60)

        # polite poolにアクセスするためのメールアドレス（任意）
        self.mailto = os.getenv("OPENALEX_EMAIL", "")

        logger.info(f"OpenAlex Trends Manager初期化:")
        logger.info(f"  API URL: {self.BASE_URL}")
        logger.info(f"  mailto: {'設定済み' if self.mailto else '未設定（10req/秒制限）'}")

    def _get_cache_key(self, category: str = "trending", *args, **kwargs) -> str:
        """キャッシュキーを返す"""
        return f"openalex_trends_{category}"

    def _get_from_cache(self, category: str = "trending", *args, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """キャッシュからデータを取得"""
        cached_data = self.db.get_openalex_trends_from_cache(category=category)
        return cached_data

    def _save_to_cache(self, data: List[Dict[str, Any]], category: str = "trending", *args, **kwargs) -> bool:
        """キャッシュにデータを保存"""
        try:
            return self.db.save_openalex_trends_to_cache(data, category=category)
        except Exception as e:
            logger.error(f"❌ OpenAlex キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, category: str = "trending", *args, **kwargs) -> bool:
        """キャッシュをクリア"""
        try:
            return self.db.clear_openalex_trends_cache(category=category)
        except Exception as e:
            logger.error(f"❌ OpenAlex キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key: str, data_count: int, *args, **kwargs) -> bool:
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ OpenAlex: cache_status更新エラー: {e}")
            return False

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """OpenAlex APIにリクエストを送信"""
        if params is None:
            params = {}

        # polite poolにアクセスするためemailパラメータを追加
        if self.mailto:
            params["mailto"] = self.mailto

        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"📡 OpenAlex APIリクエスト: {url}")
        logger.debug(f"   パラメータ: {params}")

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response.json()

    def _parse_work(self, work: dict, rank: int = 0) -> Dict[str, Any]:
        """論文データをパース"""
        # 著者情報を取得
        authorships = work.get("authorships", [])
        authors = []
        institutions = []
        for authorship in authorships[:5]:  # 最初の5人まで
            author = authorship.get("author", {})
            if author.get("display_name"):
                authors.append(author.get("display_name"))
            # 機関情報
            for inst in authorship.get("institutions", [])[:1]:
                if inst.get("display_name") and inst.get("display_name") not in institutions:
                    institutions.append(inst.get("display_name"))

        # トピック/コンセプトを取得
        concepts = work.get("concepts", [])[:5]
        concept_names = []
        for c in concepts:
            name = c.get("display_name", "")
            jp_name = self.CONCEPT_MAPPING.get(name.lower(), name)
            concept_names.append(jp_name)

        # Open Access情報
        open_access = work.get("open_access", {})
        is_oa = open_access.get("is_oa", False)
        oa_url = open_access.get("oa_url", "")

        # 発行日のパース
        pub_date = work.get("publication_date", "")
        try:
            pub_datetime = datetime.strptime(pub_date, "%Y-%m-%d") if pub_date else None
        except ValueError:
            pub_datetime = None

        return {
            "rank": rank,
            "work_id": work.get("id", "").replace("https://openalex.org/", ""),
            "title": work.get("title", "タイトルなし") or "タイトルなし",
            "doi": work.get("doi", ""),
            "url": work.get("doi") or work.get("id", ""),
            "publication_date": pub_date,
            "published_at": pub_datetime.isoformat() if pub_datetime else None,
            "cited_by_count": work.get("cited_by_count", 0),
            "authors": authors,
            "authors_display": ", ".join(authors[:3]) + ("..." if len(authors) > 3 else ""),
            "institutions": institutions,
            "institution_display": institutions[0] if institutions else "",
            "concepts": concept_names,
            "concepts_display": ", ".join(concept_names[:3]),
            "is_open_access": is_oa,
            "open_access_url": oa_url if is_oa else "",
            "type": work.get("type", ""),
            "source": "OpenAlex",
        }

    def _fetch_trends(
        self,
        category: str = "trending",
        limit: int = 25,
        days: int = 30,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """OpenAlex APIからトレンドデータを取得

        Args:
            category: カテゴリ（trending, ai, nlp, climate, biotech, quantum, medical）
            limit: 取得件数
            days: 過去何日間の論文を対象にするか

        Returns:
            Dict: 取得結果
        """
        try:
            self.rate_limiter.wait_if_needed()

            # 日付フィルター
            from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            # パラメータ構築
            params = {
                "filter": f"from_publication_date:{from_date}",
                "sort": "cited_by_count:desc",
                "per_page": min(limit, 100),
            }

            # カテゴリ別の検索条件を追加
            cat_config = self.CATEGORIES.get(category, self.CATEGORIES["trending"])
            if cat_config.get("search"):
                params["search"] = cat_config["search"]

            data = self._make_request("works", params)

            works = data.get("results", [])
            total_count = data.get("meta", {}).get("count", 0)

            if not works:
                logger.warning(f"⚠️ OpenAlex API: 論文が取得できませんでした (category={category})")
                return {
                    "success": True,
                    "data": [],
                    "status": "no_works",
                    "source": "openalex_api",
                    "category": category,
                }

            # データを整形
            formatted_data = []
            for i, work in enumerate(works[:limit], 1):
                try:
                    parsed = self._parse_work(work, rank=i)
                    formatted_data.append(parsed)
                except Exception as e:
                    logger.warning(f"⚠️ OpenAlex 論文データの処理でエラー: {e}", exc_info=True)
                    continue

            logger.info(f"✅ OpenAlex: {len(formatted_data)}件の論文を取得しました (category={category}, total={total_count:,})")

            return {
                "success": True,
                "data": formatted_data,
                "status": "api_fetched",
                "source": "openalex_api",
                "category": category,
                "category_name": cat_config.get("name", category),
                "total_count": total_count,
                "days": days,
            }

        except requests.exceptions.Timeout:
            logger.error("❌ OpenAlex API タイムアウトエラー", exc_info=True)
            return {"error": "OpenAlex API タイムアウト", "success": False}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ OpenAlex API リクエストエラー: {e}", exc_info=True)
            return {"error": f"OpenAlex APIリクエストエラー: {str(e)}", "success": False}
        except Exception as e:
            logger.error(f"❌ OpenAlex API エラー: {e}", exc_info=True)
            return {"error": f"OpenAlex API取得エラー: {str(e)}", "success": False}

    def get_trends(
        self,
        category: str = "trending",
        limit: int = 25,
        days: int = 30,
        force_refresh: bool = False,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """OpenAlexトレンドを取得（キャッシュ優先）

        Args:
            category: カテゴリ（trending, ai, nlp, climate, biotech, quantum, medical）
            limit: 取得件数
            days: 過去何日間の論文を対象にするか
            force_refresh: 強制更新フラグ

        Returns:
            Dict: トレンドデータ
        """
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,
            sort_key="cited_by_count",
            sort_reverse=True,
            category=category,
            days=days,
        )

        # カテゴリ名を追加
        if result and isinstance(result, dict):
            cat_config = self.CATEGORIES.get(category, self.CATEGORIES["trending"])
            result["category"] = category
            result["category_name"] = cat_config.get("name", category)

        return result

    def get_available_categories(self) -> List[Dict[str, str]]:
        """利用可能なカテゴリ一覧を取得"""
        return [
            {"id": cat_id, "name": cat_config["name"]}
            for cat_id, cat_config in self.CATEGORIES.items()
        ]

    def search_works(
        self,
        query: str,
        limit: int = 25,
        days: int = 365,
    ) -> Dict[str, Any]:
        """論文を検索

        Args:
            query: 検索クエリ
            limit: 取得件数
            days: 過去何日間の論文を対象にするか

        Returns:
            Dict: 検索結果
        """
        try:
            self.rate_limiter.wait_if_needed()

            from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            params = {
                "search": query,
                "filter": f"from_publication_date:{from_date}",
                "sort": "cited_by_count:desc",
                "per_page": min(limit, 100),
            }

            data = self._make_request("works", params)

            works = data.get("results", [])
            total_count = data.get("meta", {}).get("count", 0)

            formatted_data = []
            for i, work in enumerate(works[:limit], 1):
                try:
                    parsed = self._parse_work(work, rank=i)
                    formatted_data.append(parsed)
                except Exception as e:
                    logger.warning(f"⚠️ OpenAlex 論文データの処理でエラー: {e}")
                    continue

            logger.info(f"✅ OpenAlex検索: {len(formatted_data)}件の論文を取得 (query={query[:30]}...)")

            return {
                "success": True,
                "data": formatted_data,
                "query": query,
                "total_count": total_count,
                "source": "openalex_api",
            }

        except Exception as e:
            logger.error(f"❌ OpenAlex検索エラー: {e}", exc_info=True)
            return {"error": str(e), "success": False}

    def get_top_authors(self, limit: int = 10) -> Dict[str, Any]:
        """被引用数トップの著者を取得"""
        try:
            self.rate_limiter.wait_if_needed()

            params = {
                "sort": "cited_by_count:desc",
                "per_page": min(limit, 100),
            }

            data = self._make_request("authors", params)

            authors = data.get("results", [])
            formatted_data = []

            for i, author in enumerate(authors[:limit], 1):
                affiliations = author.get("affiliations", [])
                institution = ""
                if affiliations:
                    inst = affiliations[0].get("institution", {})
                    institution = inst.get("display_name", "")

                formatted_data.append({
                    "rank": i,
                    "author_id": author.get("id", "").replace("https://openalex.org/", ""),
                    "name": author.get("display_name", ""),
                    "cited_by_count": author.get("cited_by_count", 0),
                    "works_count": author.get("works_count", 0),
                    "institution": institution,
                    "source": "OpenAlex",
                })

            return {
                "success": True,
                "data": formatted_data,
                "source": "openalex_api",
            }

        except Exception as e:
            logger.error(f"❌ OpenAlex著者取得エラー: {e}", exc_info=True)
            return {"error": str(e), "success": False}

    def get_top_institutions(self, limit: int = 10, country: str = None) -> Dict[str, Any]:
        """論文数トップの研究機関を取得

        Args:
            limit: 取得件数
            country: 国コード（JP, US, CN など）
        """
        try:
            self.rate_limiter.wait_if_needed()

            params = {
                "sort": "works_count:desc",
                "per_page": min(limit, 100),
            }

            if country:
                params["filter"] = f"country_code:{country.upper()}"

            data = self._make_request("institutions", params)

            institutions = data.get("results", [])
            formatted_data = []

            for i, inst in enumerate(institutions[:limit], 1):
                formatted_data.append({
                    "rank": i,
                    "institution_id": inst.get("id", "").replace("https://openalex.org/", ""),
                    "name": inst.get("display_name", ""),
                    "works_count": inst.get("works_count", 0),
                    "cited_by_count": inst.get("cited_by_count", 0),
                    "country_code": inst.get("country_code", ""),
                    "type": inst.get("type", ""),
                    "source": "OpenAlex",
                })

            return {
                "success": True,
                "data": formatted_data,
                "country": country,
                "source": "openalex_api",
            }

        except Exception as e:
            logger.error(f"❌ OpenAlex機関取得エラー: {e}", exc_info=True)
            return {"error": str(e), "success": False}
