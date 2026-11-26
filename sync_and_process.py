"""
Module: sync_and_process.py
Mo ta: Luong tich hop tu dong (ETL Pipeline):
       Thu thap Review -> Luu CSDL -> PhoBERT ABSA -> Intent -> Phan cong Task tu dong.
"""

from core.config import configure_tf_env, settings
from core.logger import get_logger
from core.time_utils import utc_now

configure_tf_env()

from database.connection import SessionLocal, init_db
from database.models import Hotel, Review
from processors.apify_ingestion import ReviewIngestionService
from acsa_pipeline import ACSAPipeline
from api.services.review_processor import apply_analysis_to_review, determine_department

logger = get_logger(__name__)


class ReviewSyncEngine:
    def __init__(self, ai_pipeline=None):
        logger.info("Khoi dong dong co dong bo va xu ly du lieu...")
        init_db()
        self.db = SessionLocal()
        self.ingestion_service = ReviewIngestionService()
        self.ai_pipeline = ai_pipeline or ACSAPipeline()

    def _determine_department(self, aspect_category: str):
        """Giu tuong thich nguoc, uy quyen cho module review_processor dung chung."""
        return determine_department(aspect_category)

    def sync_hotel_reviews(self, hotel_name: str, maps_url: str = None, address: str = None, max_reviews: int = 10):
        # 1. Kiem tra hoac tao khach san trong CSDL
        hotel = self.db.query(Hotel).filter(Hotel.name == hotel_name).first()
        if not hotel:
            hotel = Hotel(
                name=hotel_name,
                google_maps_url=maps_url or "https://maps.google.com/sample",
                address=address or "Viet Nam"
            )
            self.db.add(hotel)
            self.db.commit()
            self.db.refresh(hotel)
            print(f"[DATABASE] Tao moi thong tin khach san: ID={hotel.id}, Ten='{hotel.name}'")
        elif address and hotel.address != address:
            hotel.address = address
            if maps_url:
                hotel.google_maps_url = maps_url
            self.db.commit()

        # 2. Thu thap review
        raw_reviews = self.ingestion_service.fetch_reviews(maps_url, max_reviews)
        inserted_count = 0

        for r_item in raw_reviews:
            # Chong trung lap bang external_id
            exists = self.db.query(Review).filter(
                Review.hotel_id == hotel.id,
                Review.external_id == r_item["external_id"]
            ).first()

            if exists:
                continue

            review = Review(
                hotel_id=hotel.id,
                external_id=r_item["external_id"],
                author_name=r_item.get("author_name", "Khach hang"),
                rating=r_item["rating"],
                text=r_item["text"],
                review_time=r_item.get("review_time", utc_now()),
                source=r_item.get("source", "GOOGLE_MAPS"),
                is_processed=False
            )
            self.db.add(review)
            inserted_count += 1

        self.db.commit()
        logger.info("Da ghi nhan %d danh gia moi vao co so du lieu.", inserted_count)

        # 3. Chay Mo hinh AI tren cac review chua xu ly
        unprocessed = self.db.query(Review).filter(
            Review.hotel_id == hotel.id,
            Review.is_processed == False
        ).all()

        logger.info("Bat dau phan tich ABSA & Intent cho %d danh gia...", len(unprocessed))

        for rev in unprocessed:
            analysis = self.ai_pipeline.analyze_review(rev.text, rev.rating)
            created_task = apply_analysis_to_review(self.db, rev, analysis)
            if created_task is not None:
                logger.info(
                    "Sinh cong viec moi: %s -> Phong ban: %s",
                    created_task.title,
                    created_task.department.value,
                )

        self.db.commit()
        logger.info("Hoan tat quy trinh dong bo va phan tich du lieu.")

    def sync_hotel_chain(self, branches: list = None, max_reviews_per_branch: int = 15):
        """
        Dong bo du lieu danh gia cho toan bo cac chi nhanh trong chuoi khach san.
        Tu dong doc danh sach URL tu TARGET_GOOGLE_MAPS_URL trong .env neu khong truyen truc tiep.
        """
        if not branches:
            env_urls = [u.strip() for u in settings.TARGET_GOOGLE_MAPS_URL.split(",") if u.strip().startswith("http")]

            default_branches = [
                {
                    "name": "Khach san Muong Thanh Grand Ha Noi",
                    "address": "KDT Linh Dam, Hoang Mai, Ha Noi",
                    "url": env_urls[0] if len(env_urls) > 0 else "https://maps.app.goo.gl/zaLutmJjLD8G98fu8"
                },
                {
                    "name": "Khach san Muong Thanh Luxury Quang Ninh",
                    "address": "Duong Ha Long, Bai Chay, TP. Ha Long, Quang Ninh",
                    "url": env_urls[1] if len(env_urls) > 1 else "https://maps.app.goo.gl/jtXXvZijC9RyoocbA"
                },
                {
                    "name": "Khach san Muong Thanh Holiday Moc Chau",
                    "address": "Hoang Quoc Viet, Phieng Luong, Moc Chau, Son La",
                    "url": env_urls[2] if len(env_urls) > 2 else "https://maps.app.goo.gl/drgHsEUBkmk6DG9z9"
                }
            ]
            branches = default_branches

        print("=" * 80)
        print(f"[CHAIN SYNC] Bat dau dong bo chuoi gom {len(branches)} chi nhanh...")
        print("=" * 80)

        for idx, branch in enumerate(branches, 1):
            print(f"\n>>> [{idx}/{len(branches)}] DONG BO CHI NHANH: {branch['name']}")
            print(f"    Dia chi: {branch.get('address', 'Chua cap nhat')}")
            print(f"    Google Maps: {branch['url']}")

            self.sync_hotel_reviews(
                hotel_name=branch["name"],
                maps_url=branch["url"],
                address=branch.get("address"),
                max_reviews=max_reviews_per_branch
            )

        print("\n" + "=" * 80)
        print(f"[CHAIN SYNC] Hoan tat dong bo thanh cong cho toan bo {len(branches)} chi nhanh!")
        print("=" * 80)

    def close(self):
        self.db.close()


if __name__ == "__main__":
    engine = ReviewSyncEngine()
    engine.sync_hotel_chain(max_reviews_per_branch=15)
    engine.close()