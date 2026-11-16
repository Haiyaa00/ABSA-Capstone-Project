"""
Module: sync_and_process.py
Mo ta: Luong tich hop tu dong (ETL Pipeline):
       Thu thap Review -> Luu CSDL -> PhoBERT ABSA -> Intent -> Phan cong Task tu dong.
"""

import os
os.environ["USE_TORCH"] = "0"
os.environ["USE_TF"] = "1"
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from datetime import datetime
from database.connection import SessionLocal, init_db
from database.models import Hotel, Review, AspectResult, Task, TaskType, TaskPriority, TaskStatus, Department
from processors.apify_ingestion import ReviewIngestionService
from acsa_pipeline import ACSAPipeline

class ReviewSyncEngine:
    def __init__(self):
        print("[PIPELINE] Khoi dong dong co dong bo va xu ly du lieu...")
        init_db()
        self.db = SessionLocal()
        self.ingestion_service = ReviewIngestionService()
        self.ai_pipeline = ACSAPipeline()

    def _determine_department(self, aspect_category: str) -> Department:
        """
        Quy tac phan cong phong ban tu dong dua tren khia canh ABSA:
        - ROOM / ROOMS -> Housekeeping hoac Maintenance
        - SERVICE -> Front Desk
        - FOOD&DRINKS -> F_AND_B
        - FACILITIES -> Maintenance
        """
        asp = aspect_category.upper()
        if "CLEANLINESS" in asp or "ROOMS#CLEANLINESS" in asp:
            return Department.HOUSEKEEPING
        elif "FOOD&DRINKS" in asp:
            return Department.F_AND_B
        elif "SERVICE" in asp:
            return Department.FRONT_DESK
        elif "FACILITIES" in asp or "COMFORT" in asp:
            return Department.MAINTENANCE
        return Department.MANAGEMENT

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
                review_time=r_item.get("review_time", datetime.utcnow()),
                source=r_item.get("source", "GOOGLE_MAPS"),
                is_processed=False
            )
            self.db.add(review)
            inserted_count += 1

        self.db.commit()
        print(f"[DATABASE] Da ghi nhan {inserted_count} danh gia moi vao co so du lieu.")

        # 3. Chay Mo hinh AI tren cac review chua xu ly
        unprocessed = self.db.query(Review).filter(
            Review.hotel_id == hotel.id,
            Review.is_processed == False
        ).all()

        print(f"[AI ENGINE] Bat dau phan tich ABSA & Intent cho {len(unprocessed)} danh gia...")

        for rev in unprocessed:
            analysis = self.ai_pipeline.analyze_review(rev.text, rev.rating)
            
            # Luu cac khia canh ABSA
            for a in analysis["aspects"]:
                aspect_record = AspectResult(
                    review_id=rev.id,
                    aspect_category=a["aspect"],
                    sentiment=a["sentiment"],
                    confidence=a["confidence"]
                )
                self.db.add(aspect_record)

            # Xu ly tao Task tu dong dua vao Intent
            intent = analysis["intent"]
            task_action = analysis["task_action"]

            if task_action["create_task"]:
                # Xac dinh phong ban xu ly dua tren khia canh tieu cuc dau tien
                neg_aspects = [a["aspect"] for a in analysis["aspects"] if a["sentiment"] == "negative"]
                target_dept = self._determine_department(neg_aspects[0]) if neg_aspects else Department.MANAGEMENT

                task_type_enum = TaskType.CRITICAL_TASK if intent == "CRITICAL_COMPLAINT" else TaskType.IMPROVEMENT_TASK
                priority_enum = TaskPriority.HIGH if intent == "CRITICAL_COMPLAINT" else TaskPriority.MEDIUM

                task_title = f"[{'KHAN CAP' if intent == 'CRITICAL_COMPLAINT' else 'DE XUAT'}] {rev.author_name} ({rev.rating}*)"
                task_desc = f"Noi dung: {rev.text}\nKhia canh phan anh: {', '.join(neg_aspects) if neg_aspects else 'Theo danh gia chung'}"

                new_task = Task(
                    hotel_id=hotel.id,
                    review_id=rev.id,
                    title=task_title,
                    description=task_desc,
                    task_type=task_type_enum,
                    priority=priority_enum,
                    status=TaskStatus.PENDING,
                    department=target_dept
                )
                self.db.add(new_task)
                print(f"[TASK CREATED] Sinh cong viec moi: {task_title} -> Phong ban: {target_dept.value}")

            rev.is_processed = True

        self.db.commit()
        print("[PIPELINE] Hoan tat quy trinh dong bo va phan tich du lieu.")

    def sync_hotel_chain(self, branches: list = None, max_reviews_per_branch: int = 15):
        """
        Dong bo du lieu danh gia cho toan bo cac chi nhanh trong chuoi khach san.
        Tu dong doc danh sach URL tu TARGET_GOOGLE_MAPS_URL trong .env neu khong truyen truc tiep.
        """
        if not branches:
            env_urls_str = os.getenv("TARGET_GOOGLE_MAPS_URL", "")
            env_urls = [u.strip() for u in env_urls_str.split(",") if u.strip().startswith("http")]

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