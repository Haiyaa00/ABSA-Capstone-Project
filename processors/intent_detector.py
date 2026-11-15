"""
Module: intent_detector.py
Mô tả: Phân loại ý định khách hàng theo Kiến trúc Lai 2 Tầng (Rule-based Fast Filter + Gemini Fallback).
Các nhãn đầu ra:
  1. CRITICAL_COMPLAINT    (Khiếu nại nghiêm trọng -> Tạo Task Đỏ)
  2. IMPROVEMENT_SUGGESTION (Góp ý / Đề xuất cải thiện -> Tạo Task Vàng)
  3. GENERAL_FEEDBACK      (Đánh giá thông thường / Khen ngợi -> Không tạo Task)
"""

import os
import re
import json

class HybridIntentDetector:
    def __init__(self, gemini_api_key: str = None):
        self.api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.gemini_client = None

        # Khởi tạo client Gemini nếu có API key
        if self.api_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Cảnh báo] Không thể kết nối Gemini API: {e}. Hệ thống sẽ sử dụng Rule-based thuần túy.")

        # 1. Từ điển từ khóa báo động đỏ (CRITICAL KEYWORDS)
        self.critical_keywords = [
            "gián", "chuột", "mất đồ", "mất trộm", "lừa đảo", "lừa gạt",
            "thái độ lồi lõm", "vô văn hóa", "xấc xược", "bẩn kinh khủng", 
            "kinh tởm", "hôi thối", "hoàn tiền", "trả lại tiền", "bóc phốt", 
            "tẩy chay", "cạch mặt", "không bao giờ quay lại", "tệ hại nhất", 
            "tồi tệ nhất", "đòi gặp quản lý", "báo công an", "ngộ độc"
        ]

        # 2. Các mẫu câu góp ý cải thiện (IMPROVEMENT PATTERNS)
        self.suggestion_patterns = [
            "nên có", "nên thêm", "cần thêm", "cần có", "cần bổ sung", 
            "nên bổ sung", "mong khách sạn", "hy vọng lần sau", "nếu được thì", 
            "nếu có thêm", "giá như", "nên cải thiện", "cần khắc phục", 
            "nên thay", "cần thay", "đề xuất"
        ]

        # 3. Các khía cạnh nhạy cảm dễ gây khủng hoảng khi bị đánh giá tiêu cực
        self.sensitive_aspects = [
            "ROOMS#CLEANLINESS", "SERVICE#GENERAL", "HOTEL#MISCELLANEOUS", 
            "FACILITIES#QUALITY", "HOTEL#CLEANLINESS"
        ]

    # ================================================================
    # TẦNG 1: RULE-BASED FAST FILTER (< 1ms)
    # ================================================================
    def _rule_based_check(self, text: str, rating: int, absa_results: list) -> dict:
        text_lower = text.lower()
        neg_aspects = [a['aspect'] for a in absa_results if a.get('sentiment') == 'negative']
        pos_aspects = [a['aspect'] for a in absa_results if a.get('sentiment') == 'positive']

        # Quy tắc 1.1: Chứa từ khóa báo động đỏ
        matched_crit_kw = [kw for kw in self.critical_keywords if kw in text_lower]
        if matched_crit_kw:
            return {
                "intent": "CRITICAL_COMPLAINT",
                "confidence": 0.98,
                "method": "rule_based",
                "reason": f"Phát hiện từ khóa báo động nghiêm trọng: '{matched_crit_kw[0]}'"
            }

        # Quy tắc 1.2: Đánh giá 1-2 sao + có khía cạnh nhạy cảm bị đánh giá tiêu cực
        has_sensitive_neg = any(asp in self.sensitive_aspects for asp in neg_aspects)
        if rating and rating <= 2 and has_sensitive_neg:
            return {
                "intent": "CRITICAL_COMPLAINT",
                "confidence": 0.92,
                "method": "rule_based",
                "reason": f"Đánh giá {rating} sao kết hợp phản ánh tiêu cực ở khía cạnh nhạy cảm: {neg_aspects}"
            }

        # Quy tắc 2: Chứa mẫu câu đề xuất cải thiện
        matched_sugg = [pat for pat in self.suggestion_patterns if pat in text_lower]
        if matched_sugg:
            return {
                "intent": "IMPROVEMENT_SUGGESTION",
                "confidence": 0.90,
                "method": "rule_based",
                "reason": f"Phát hiện cấu trúc câu đề xuất cải thiện: '{matched_sugg[0]}'"
            }

        # Quy tắc 3: Đánh giá tốt rõ ràng (Rating >= 4 hoặc chỉ có lời khen, không có tiêu cực)
        if (rating and rating >= 4 and len(neg_aspects) == 0) or (len(pos_aspects) >= 2 and len(neg_aspects) == 0):
            return {
                "intent": "GENERAL_FEEDBACK",
                "confidence": 0.95,
                "method": "rule_based",
                "reason": "Phản hồi tích cực/khen ngợi rõ ràng, không có khía cạnh tiêu cực."
            }

        # Nếu là câu phức tạp, nước đôi -> Chuyển sang Tầng 2
        return None

    # ================================================================
    # TẦNG 2: LLM FALLBACK (GEMINI FLASH ROUTER)
    # ================================================================
    def _gemini_fallback_check(self, text: str, rating: int, absa_results: list) -> dict:
        if not self.gemini_client:
            # Fallback an toàn nếu chưa cấu hình Gemini
            return {
                "intent": "GENERAL_FEEDBACK",
                "confidence": 0.70,
                "method": "heuristic_fallback",
                "reason": "Nhận xét tổng thể trung tính (Gemini API chưa kích hoạt)."
            }

        prompt = f"""
Bạn là chuyên gia Quản trị Trải nghiệm Khách hàng ngành Khách sạn.
Hãy phân loại Ý ĐỊNH của câu đánh giá sau vào ĐÚNG 1 TRONG 3 NHÃN:
1. "CRITICAL_COMPLAINT": Khiếu nại nghiêm trọng, thái độ tệ, sự cố vệ sinh/an toàn, khách bức xúc, rủi ro danh tiếng cao.
2. "IMPROVEMENT_SUGGESTION": Khách góp ý, đề xuất khách sạn nên sửa chữa, bổ sung hay thay đổi cơ sở vật chất/dịch vụ.
3. "GENERAL_FEEDBACK": Khen ngợi thông thường, đánh giá trải nghiệm chung, hoặc nhận xét trung tính.

Dữ liệu đầu vào:
- Nội dung review: "{text}"
- Số sao đánh giá: {rating if rating else 'Không rõ'}/5 sao
- Khía cạnh phân tích từ AI: {json.dumps(absa_results, ensure_ascii=False)}

Hãy trả về DUY NHẤT một chuỗi JSON chuẩn có cấu trúc như sau:
{{"intent": "TÊN_NHÃN", "confidence": 0.95, "reason": "Giải thích ngắn gọn 1 câu"}}
"""
        try:
            response = self.gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            # Làm sạch JSON
            resp_text = response.text.strip()
            resp_text = re.sub(r'```json\s*', '', resp_text)
            resp_text = re.sub(r'```', '', resp_text).strip()
            result = json.loads(resp_text)
            result["method"] = "gemini_llm"
            return result
        except Exception as e:
            return {
                "intent": "GENERAL_FEEDBACK",
                "confidence": 0.65,
                "method": "gemini_error_fallback",
                "reason": f"Lỗi gọi LLM ({str(e)}), tự động gán nhãn thông thường."
            }

    # ================================================================
    # HÀM CHÍNH ĐIỀU PHỐI (MAIN PIPELINE)
    # ================================================================
    def detect_intent(self, text: str, rating: int = None, absa_results: list = None) -> dict:
        if absa_results is None:
            absa_results = []

        # 1. Chạy qua Tầng 1 (Rule-based)
        intent_result = self._rule_based_check(text, rating, absa_results)

        # 2. Nếu Tầng 1 không bắt được -> Kích hoạt Tầng 2 (Gemini Fallback)
        if intent_result is None:
            intent_result = self._gemini_fallback_check(text, rating, absa_results)

        # 3. Đính kèm hành động tương ứng cho Mobile App (Task Management)
        task_action = {
            "create_task": False,
            "task_type": "NONE",
            "priority": "LOW",
            "badge_color": "GREEN"
        }

        if intent_result["intent"] == "CRITICAL_COMPLAINT":
            task_action = {
                "create_task": True,
                "task_type": "CRITICAL_TASK",
                "priority": "HIGH",
                "badge_color": "RED"
            }
        elif intent_result["intent"] == "IMPROVEMENT_SUGGESTION":
            task_action = {
                "create_task": True,
                "task_type": "IMPROVEMENT_TASK",
                "priority": "MEDIUM",
                "badge_color": "YELLOW"
            }

        return {
            "intent": intent_result["intent"],
            "confidence": intent_result.get("confidence", 0.9),
            "detection_method": intent_result.get("method", "hybrid"),
            "reason": intent_result.get("reason", ""),
            "task_action": task_action
        }