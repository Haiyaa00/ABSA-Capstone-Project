"""
Script: test_reply_generator.py
Mô tả: Kiểm thử độc lập quy trình sinh phản hồi thông minh từ Gemini LLM
       kết hợp đầu ra thực tế của PhoBERT ABSA và Intent Detection.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import configure_tf_env

configure_tf_env()

from acsa_pipeline import ACSAPipeline

if __name__ == '__main__':
    pipeline = ACSAPipeline()

    # 4 Kịch bản kiểm thử đại diện thực tế
    test_cases = [
        {
            "title": "KỊCH BẢN 1: KHIẾU NẠI KHẨN CẤP (Vệ sinh tệ + Lễ tân gắt)",
            "review": "Phòng 402 có gián bò lên giường, ga đệm bẩn thỉu hôi hám, lễ tân nói chuyện cực kỳ vô văn hóa. Yêu cầu quản lý hoàn tiền ngay!",
            "rating": 1
        },
        {
            "title": "KỊCH BẢN 2: KHEN NGỢI TÍCH CỰC (Nhân viên tốt + View đẹp)",
            "review": "Khách sạn rất đẹp, bạn Mai lễ tân siêu nhiệt tình hỗ trợ gia đình mình, view ngắm biển tuyệt vời, chắc chắn mình sẽ quay lại.",
            "rating": 5
        },
        {
            "title": "KỊCH BẢN 3: ĐÓNG GÓP Ý KIẾN CẢI THIỆN (Tiện nghi phòng)",
            "review": "Khách sạn nên lắp thêm rèm chống nắng ở các phòng hướng Tây, và nếu có thêm máy sấy tóc công suất lớn thì tuyệt vời hơn nhiều.",
            "rating": 4
        },
        {
            "title": "KỊCH BẢN 4: ĐÁNH GIÁ TRUNG TÍNH / HỖN HỢP (Khen vị trí, chê giá)",
            "review": "Vị trí gần trung tâm đi lại tiện. Phòng ốc tạm ổn, giá hơi đắt một chút so với mặt bằng chung.",
            "rating": 3
        }
    ]

    print("\n" + "="*80)
    print("🚀 BẮT ĐẦU KIỂM THỬ TÍNH NĂNG AI REPLY GENERATOR (GEMINI LLM)")
    print("="*80)

    for i, case in enumerate(test_cases, 1):
        print(f"\n[{case['title']}]")
        print(f"💬 Khách đánh giá ({case['rating']} ⭐): \"{case['review']}\"")
        
        # 1. Chạy qua PhoBERT ABSA + Intent Detection
        analysis = pipeline.analyze_review(case['review'], case['rating'])
        print(f"🎯 Bóc tách ABSA: {[a['aspect'] + ':' + a['sentiment'] for a in analysis['aspects']]}")
        print(f"📌 Ý định (Intent): {analysis['intent']}")

        # 2. Sinh câu phản hồi bằng Gemini LLM
        reply_info = pipeline.generate_reply_for_review(analysis)
        
        print("\n🤖 AI GỢI Ý PHẢN HỒI:")
        print("-" * 60)
        print(reply_info['reply'])
        print("-" * 60)
        print(f"Nguồn: {reply_info['source']} | Thành công: {reply_info['success']}")
        print("." * 80)

    print("\n" + "="*80)
    print("🎉 KIỂM THỬ GIAI ĐOẠN 1 HOÀN TẤT THÀNH CÔNG!")
    print("="*80)