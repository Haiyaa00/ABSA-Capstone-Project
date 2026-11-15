"""
Script: test_intent_pipeline.py
Mục đích: Chạy thử nghiệm toàn bộ luồng từ PhoBERT ABSA đến Intent Detection.
"""
import os
os.environ["USE_TORCH"] = "0"
os.environ["USE_TF"] = "1"
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import json
from acsa_pipeline import ACSAPipeline

if __name__ == '__main__':
    pipeline = ACSAPipeline()

    test_samples = [
        {
            "review": "Phòng 402 có gián bò lên giường, ga đệm bẩn thỉu hôi hám, lễ tân nói chuyện cực kỳ vô văn hóa. Yêu cầu quản lý hoàn tiền ngay!",
            "rating": 1
        },
        {
            "review": "Khách sạn rất đẹp, nhân viên Mai lễ tân siêu nhiệt tình, view ngắm biển tuyệt vời, chắc chắn mình sẽ quay lại.",
            "rating": 5
        },
        {
            "review": "Khách sạn nên lắp thêm rèm chống nắng ở các phòng hướng Tây, và nếu có thêm máy sấy tóc công suất lớn thì tuyệt vời hơn nhiều.",
            "rating": 4
        },
        {
            "review": "Vị trí gần trung tâm đi lại tiện. Phòng ốc tạm ổn, giá hơi đắt một chút so với mặt bằng chung.",
            "rating": 3
        }
    ]

    print("\n" + "="*70)
    print("🚀 BẮT ĐẦU CHẠY THỬ NGHIỆM PIPELINE ABSA + INTENT DETECTION")
    print("="*70)

    for i, sample in enumerate(test_samples, 1):
        result = pipeline.analyze_review(sample["review"], sample["rating"])
        print(f"\n--- [TEST CASE #{i}] ---")
        print(f"📝 Review: {result['text']}")
        print(f"⭐ Rating: {result['rating']} sao")
        print(f"🔍 Khía cạnh bóc tách ({result['aspects_count']}):")
        for a in result['aspects']:
            print(f"   • {a['aspect']}: {a['sentiment'].upper()} (Độ tin cậy: {a['confidence']})")
        
        print(f"🎯 Ý định (Intent): {result['intent']} [Phương pháp: {result['detection_method']}]")
        print(f"💡 Lý do: {result['intent_reason']}")
        print(f"📋 Hành động Task: Tạo Task = {result['task_action']['create_task']} | Loại = {result['task_action']['task_type']} | Màu thẻ = {result['task_action']['badge_color']}")

    print("\n" + "="*70)
    print("🎉 KIỂM THỬ HOÀN TẤT THÀNH CÔNG!")
    print("="*70)