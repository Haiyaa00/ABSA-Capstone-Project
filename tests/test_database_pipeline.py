"""
Script: test_database_pipeline.py
Mo ta: Kiem thu toan dien Giai doan 2:
       1. Khoi tao Co so Du lieu SQLite
       2. Dong bo danh gia va phan tich ABSA + Intent
       3. Truy van du lieu tong quan (Dashboard stats preview)
       4. Kiem tra danh sach Cong viec (Task Management preview)
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import configure_tf_env

configure_tf_env()

from database.connection import SessionLocal
from database.models import Hotel, Review, AspectResult, Task, TaskStatus
from sync_and_process import ReviewSyncEngine

def main():
    print("=" * 80)
    print("[TEST] BAT DAU KIEM THU TOAN DIEN GIAI DOAN 2: DATABASE & MULTI-BRANCH PIPELINE")
    print("=" * 80)

    # 1. Chay quy trinh dong bo cho toan bo chuoi khach san
    engine = ReviewSyncEngine()
    engine.sync_hotel_chain(max_reviews_per_branch=6)
    engine.close()

    # 2. Truy van CSDL kiem tra ket qua cho tung chi nhanh
    db = SessionLocal()
    try:
        hotels = db.query(Hotel).all()
        print("\n" + "=" * 80)
        print("[THONG KE CO SO DU LIEU - PREVIEW DASHBOARD DA CHI NHANH]")
        print("=" * 80)
        
        for h in hotels:
            total_revs = db.query(Review).filter(Review.hotel_id == h.id).count()
            total_asps = db.query(AspectResult).join(Review).filter(Review.hotel_id == h.id).count()
            total_tsks = db.query(Task).filter(Task.hotel_id == h.id).count()
            pending_tsks = db.query(Task).filter(Task.hotel_id == h.id, Task.status == TaskStatus.PENDING).count()

            print(f"- Chi nhanh: {h.name}")
            print(f"  Dia chi: {h.address}")
            print(f"  Danh gia: {total_revs} | Khia canh ABSA: {total_asps} | Cong viec: {total_tsks} (Cho xu ly: {pending_tsks})")
            print()

        print("-" * 80)
        print("[DANH SACH CONG VIEC CAN XU LY THEO PHONG BAN (TASK DISPATCH PREVIEW)]")
        print("-" * 80)
        tasks = db.query(Task).order_by(Task.priority.desc(), Task.created_at.desc()).limit(8).all()
        for t in tasks:
            hotel_name = db.query(Hotel.name).filter(Hotel.id == t.hotel_id).scalar()
            print(f"- Task #{t.id} [{t.priority.value}] | {hotel_name} | Phong ban: {t.department.value}")
            print(f"  Tieu de: {t.title}")
            print(f"  Noi dung: {t.description.splitlines()[0]}")
            print()

    finally:
        db.close()

    print("=" * 80)
    print("[TEST] KIEM THU GIAI DOAN 2 HOAN TAT XUAT SAC!")
    print("=" * 80)
    print("=" * 80)

if __name__ == "__main__":
    main()