"""
Module: apify_ingestion.py
Mo ta: Thu thap du lieu danh gia tu Google Maps thong qua Apify Actor API.
       Ho tro co che Dual-Mode (Truy van Live hoac Che do Tap Mau chuan hoa).
"""

import re
from datetime import datetime
from core.config import settings
from core.logger import get_logger
from core.time_utils import utc_now

logger = get_logger(__name__)

class ReviewIngestionService:
    def __init__(self, api_token: str = None):
        self.api_token = api_token or settings.APIFY_API_TOKEN
        self.client = None

        if self.api_token:
            try:
                from apify_client import ApifyClient
                self.client = ApifyClient(self.api_token)
            except Exception as e:
                logger.warning("Khong the khoi tao Apify Client: %s", e)

    def fetch_reviews(self, maps_url: str, max_reviews: int = 20) -> list:
        """
        Lay danh sach review tu Google Maps.
        Neu co API Token hop le, goi Actor cua Apify.
        Neu khong co Token, tra ve tap du lieu mau da dang dung chuan thuc te.
        """
        if self.client and maps_url and "sample" not in maps_url:
            return self._fetch_from_apify(maps_url, max_reviews)
        else:
            logger.info("Su dung bo du lieu chuan hoa noi bo (Simulation Mode).")
            return self._get_mock_reviews(max_reviews)

    def _fetch_from_apify(self, maps_url: str, max_reviews: int) -> list:
        try:
            logger.info("Bat dau truy van Apify Google Maps Reviews Scraper: %s", maps_url)
            run_input = {
                "startUrls": [{"url": maps_url}],
                "maxReviews": max_reviews,
                "language": "vi",
                "personalData": False
            }
            # Goi actor chinh thuc tren Apify
            run = self.client.actor("compass/google-maps-reviews-scraper").call(run_input=run_input)
            
            dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "default_dataset_id", getattr(run, "defaultDatasetId", None))
            raw_items = self.client.dataset(dataset_id).iterate_items()
            standardized_reviews = []
            
            for item in raw_items:
                text = item.get("text", "").strip()
                if not text:
                    continue

                # Loc bo danh gia tieng Han, Nhat, Trung de toi uu cho PhoBERT Tieng Viet
                if re.search(r"[\uac00-\ud7a3\u3040-\u30ff\u4e00-\u9fff]", text):
                    continue
                
                published_str = item.get("publishedAtDate")
                review_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00")) if published_str else utc_now()
                if review_dt.tzinfo:
                    review_dt = review_dt.replace(tzinfo=None)

                standardized_reviews.append({
                    "external_id": item.get("reviewId") or item.get("id"),
                    "author_name": item.get("name", "Khach hang an danh"),
                    "rating": int(item.get("stars", 5) or 5),
                    "text": text,
                    "review_time": review_dt,
                    "source": "GOOGLE_MAPS"
                })
            logger.info("Da thu thap %d danh gia tu Apify.", len(standardized_reviews))
            return standardized_reviews
        except Exception as e:
            logger.error("Loi khi thu thap du lieu tu Apify: %s. Chuyen sang du lieu mau.", e)
            return self._get_mock_reviews(max_reviews)

    def _get_mock_reviews(self, limit: int = 20) -> list:
        """
        Tap du lieu mau chuan hoa thuc te tieng Viet chua day du cac kich ban:
        Khen ngoi, Khieu nai nghiem trong, Gop y cai thien, va Danh gia hon hop.
        """
        mock_data = [
            {
                "external_id": "gm_rev_1001",
                "author_name": "Nguyen Van An",
                "rating": 1,
                "text": "Phong 402 co gian bo len giuong, ga dem ban thiu hoi ham, le tan noi chuyen cuc ky vo van hoa. Yeu cau quan ly hoan tien ngay!",
                "review_time": datetime(2026, 11, 10, 8, 30),
                "source": "GOOGLE_MAPS"
            },
            {
                "external_id": "gm_rev_1002",
                "author_name": "Tran Thi Thu",
                "rating": 5,
                "text": "Khach san rat dep, ban Mai le tan sieu nhiet tinh ho tro gia dinh minh, view ngam bien tuyet voi, chac chan minh se quay lai.",
                "review_time": datetime(2026, 11, 11, 14, 15),
                "source": "GOOGLE_MAPS"
            },
            {
                "external_id": "gm_rev_1003",
                "author_name": "Le Hoang Minh",
                "rating": 4,
                "text": "Khach san nen lap them rem chong nang o cac phong huong Tay, va neu co them may say toc cong suat lon thi tuyet voi hon nhieu.",
                "review_time": datetime(2026, 11, 12, 19, 45),
                "source": "GOOGLE_MAPS"
            },
            {
                "external_id": "gm_rev_1004",
                "author_name": "Pham Minh Duc",
                "rating": 3,
                "text": "Vi tri gan trung tam di lai tien. Phong oc tam on, gia hoi dat mot chut so voi mat bang chung.",
                "review_time": datetime(2026, 11, 13, 9, 20),
                "source": "GOOGLE_MAPS"
            },
            {
                "external_id": "gm_rev_1005",
                "author_name": "Doan Bao Chau",
                "rating": 2,
                "text": "Do an sang buffet nguoi lanh va qua it mon, nuoc trai cay bi chua. Ban nha hang phuc vu rat cham.",
                "review_time": datetime(2026, 11, 14, 10, 0),
                "source": "GOOGLE_MAPS"
            },
            {
                "external_id": "gm_rev_1006",
                "author_name": "Hoang Nam Anh",
                "rating": 1,
                "text": "Dieu hoa phong 305 chay keu to ca dem khong ngu duoc, goi bao ve thi thai do xuc pham khach. Dich vu qua te!",
                "review_time": datetime(2026, 11, 15, 7, 10),
                "source": "GOOGLE_MAPS"
            }
        ]
        return mock_data[:limit]