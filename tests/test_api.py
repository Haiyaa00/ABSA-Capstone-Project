"""
Script: test_api.py
Mo ta: Kiem thu tich hop toan dien cho tang REST API Backend (Giai doan 3) bang FastAPI TestClient.
       Kiem tra tu xac thuc JWT, Dashboard, Feed, Gemini Reply, Phan tich Live den Task Management.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import configure_tf_env

configure_tf_env()

from uuid import uuid4
from fastapi.testclient import TestClient

from api.main import app
from database.connection import SessionLocal
from database.models import Review, User


def cleanup_test_artifacts(review_id: int = None, username: str = None) -> None:
    """Don dep du lieu tam sinh ra trong qua trinh test de giu sach CSDL."""
    db = SessionLocal()
    try:
        if review_id is not None:
            rev = db.query(Review).filter(Review.id == review_id).first()
            if rev:
                db.delete(rev)
        if username is not None:
            usr = db.query(User).filter(User.username == username).first()
            if usr:
                db.delete(usr)
        db.commit()
    finally:
        db.close()


def run_api_tests():
    print("=" * 80)
    print("[API TEST] BAT DAU KIEM THU TOAN DIEN REST API BACKEND (FASTAPI)")
    print("=" * 80)

    created_review_id = None
    temp_username = f"test_mgr_{uuid4().hex[:6]}"

    try:
        with TestClient(app) as client:
            # 1. Health Check
            resp = client.get("/health")
            assert resp.status_code == 200, f"Health check that bai: {resp.text}"
            print("[PASS] 1. GET /health -> 200 OK")

            # 2. Chan truy cap chua dang nhap
            resp_unauth = client.get("/api/hotels")
            assert resp_unauth.status_code == 401, f"Ky vong 401 khi thieu token, nhan {resp_unauth.status_code}"
            print("[PASS] 2. GET /api/hotels (khong token) -> 401 Unauthorized")

            # 3. Dang nhap bang tai khoan admin mac dinh
            resp_login = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
            assert resp_login.status_code == 200, f"Dang nhap that bai: {resp_login.text}"
            token = resp_login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("[PASS] 3. POST /api/auth/login -> Cap JWT Token thanh cong")

            # 4. Kiem tra GET /api/auth/me
            resp_me = client.get("/api/auth/me", headers=headers)
            assert resp_me.status_code == 200
            assert resp_me.json()["username"] == "admin"
            print("[PASS] 4. GET /api/auth/me -> Xac thuc phien hop le")

            # 5. Lay danh sach khach san
            resp_hotels = client.get("/api/hotels", headers=headers)
            assert resp_hotels.status_code == 200
            hotels = resp_hotels.json()
            assert len(hotels) >= 1, "Phai co it nhat 1 khach san trong DB"
            first_hotel_id = hotels[0]["id"]
            print(f"[PASS] 5. GET /api/hotels -> Tim thay {len(hotels)} chi nhanh (ID dau tien={first_hotel_id})")

            # 6. Dang ky tai khoan tam
            resp_reg = client.post(
                "/api/auth/register",
                json={
                    "username": temp_username,
                    "password": "password123",
                    "full_name": "Kiem Thu Vien",
                    "hotel_id": first_hotel_id,
                    "role": "MANAGER",
                },
            )
            assert resp_reg.status_code == 201, f"Dang ky that bai: {resp_reg.text}"
            print(f"[PASS] 6. POST /api/auth/register -> Tao tai khoan '{temp_username}' thanh cong")

            # 7. Dashboard Stats (Toan chuoi & Chi nhanh)
            resp_dash = client.get("/api/dashboard/stats", headers=headers)
            assert resp_dash.status_code == 200, f"Dashboard that bai: {resp_dash.text}"
            dash_data = resp_dash.json()
            assert len(dash_data["category_groups"]) == 6, "Phai tra ve du 6 nhom khia canh lon"
            assert "aspect_drilldown" in dash_data
            assert "critical_alerts" in dash_data
            print(
                f"[PASS] 7. GET /api/dashboard/stats -> Tong review={dash_data['overview']['total_reviews']}, "
                f"6 nhom bieu do hop le, co drill-down & alerts"
            )

            # 8. Phan tich truc tiep mot cau khieu nai bang PhoBERT + Intent (Manual Analyze)
            sample_review = (
                "Phòng 402 có gián bò lên giường, ga đệm bẩn thỉu hôi hám, "
                "lễ tân nói chuyện cực kỳ vô văn hóa. Yêu cầu quản lý hoàn tiền ngay!"
            )
            resp_manual = client.post(
                "/api/reviews/analyze-manual",
                headers=headers,
                json={
                    "hotel_id": first_hotel_id,
                    "text": sample_review,
                    "rating": 1,
                    "author_name": "Khach Kiem Thu",
                    "save_to_db": True,
                },
            )
            assert resp_manual.status_code == 200, f"Analyze manual that bai: {resp_manual.text}"
            manual_data = resp_manual.json()
            created_review_id = manual_data["review_id"]
            created_task_id = manual_data["created_task_id"]
            assert manual_data["intent"] == "CRITICAL_COMPLAINT"
            assert created_review_id is not None
            assert created_task_id is not None
            print(
                f"[PASS] 8. POST /api/reviews/analyze-manual -> Boc tach {manual_data['aspects_count']} khia canh, "
                f"Intent={manual_data['intent']}, tu sinh Task ID={created_task_id}"
            )

            # 9. Feed & Chi tiet Review
            resp_feed = client.get(
                f"/api/reviews?hotel_id={first_hotel_id}&intent=CRITICAL_COMPLAINT&is_replied=false",
                headers=headers,
            )
            assert resp_feed.status_code == 200
            assert any(item["id"] == created_review_id for item in resp_feed.json()["items"])

            resp_detail = client.get(f"/api/reviews/{created_review_id}", headers=headers)
            assert resp_detail.status_code == 200
            print(f"[PASS] 9. GET /api/reviews & GET /api/reviews/{created_review_id} -> Loc va xem chi tiet OK")

            # 10. Sinh cau tra loi bang Gemini LLM & Xac nhan da gui
            resp_gen = client.post(
                f"/api/reviews/{created_review_id}/generate-reply",
                headers=headers,
                json={"force_regenerate": True},
            )
            assert resp_gen.status_code == 200, f"Generate reply that bai: {resp_gen.text}"
            reply_log = resp_gen.json()["reply_log"]
            reply_id = reply_log["id"]
            assert reply_log["source"] == "gemini_llm", f"Ky vong gemini_llm nhung nhan: {reply_log}"
            print(f"[PASS] 10. POST /api/reviews/{created_review_id}/generate-reply -> Source={reply_log['source']}")

            # 11. Chinh sua va danh dau da phan hoi
            resp_confirm = client.patch(
                f"/api/reviews/replies/{reply_id}",
                headers=headers,
                json={
                    "edited_reply": reply_log["generated_reply"] + " (Da xac nhan boi Quan ly)",
                    "mark_as_used": True,
                },
            )
            assert resp_confirm.status_code == 200
            assert resp_confirm.json()["is_used"] is True

            resp_detail_after = client.get(f"/api/reviews/{created_review_id}", headers=headers)
            assert resp_detail_after.json()["is_replied"] is True
            print(f"[PASS] 11. PATCH /api/reviews/replies/{reply_id} -> Da danh dau is_replied=True")

            # 12. Task Management: Loc & Cap nhat trang thai, phong ban, ghi chu
            resp_tasks = client.get(f"/api/tasks?hotel_id={first_hotel_id}&status=PENDING", headers=headers)
            assert resp_tasks.status_code == 200
            assert any(t["id"] == created_task_id for t in resp_tasks.json()["items"])

            resp_patch_task = client.patch(
                f"/api/tasks/{created_task_id}",
                headers=headers,
                json={
                    "status": "RESOLVED",
                    "department": "HOUSEKEEPING",
                    "resolution_note": "Da tong ve sinh phong 402 va xin loi khach.",
                },
            )
            assert resp_patch_task.status_code == 200, f"Patch task that bai: {resp_patch_task.text}"
            patched_task = resp_patch_task.json()
            assert patched_task["status"] == "RESOLVED"
            assert patched_task["department"] == "HOUSEKEEPING"
            assert patched_task["resolved_at"] is not None
            print(f"[PASS] 12. PATCH /api/tasks/{created_task_id} -> Cap nhat trang thai, phong ban va ghi chu OK")
    finally:
        cleanup_test_artifacts(review_id=created_review_id, username=temp_username)

    print("\n" + "=" * 80)
    print("[API TEST] TOAN BO 12 CA KIEM THU REST API DA VUOT QUA 100%!")
    print("=" * 80)


if __name__ == "__main__":
    run_api_tests()
