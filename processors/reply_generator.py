"""
Module: reply_generator.py
Mô tả: Sinh câu phản hồi thông minh cho khách hàng dựa trên:
       - Đánh giá gốc & Số sao
       - Kết quả phân tích ABSA (Khía cạnh tích cực / tiêu cực từ PhoBERT)
       - Ý định khách hàng (CRITICAL_COMPLAINT, IMPROVEMENT_SUGGESTION, GENERAL_FEEDBACK)
       - Kỹ thuật Grounding: Buộc LLM bám sát các khía cạnh cụ thể, chống ảo giác.
"""

from core.config import settings
from core.logger import get_logger
from processors.gemini_helper import create_gemini_client, generate_text_with_fallback

logger = get_logger(__name__)

class AIReplyGenerator:
    def __init__(self, api_key: str = None, model_name: str = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self.client = None

        if self.api_key:
            try:
                self.client = create_gemini_client(self.api_key)
            except Exception as e:
                logger.warning("Loi khoi tao Gemini Client: %s", e)

    def generate_reply(
        self,
        review_text: str,
        rating: int,
        absa_results: list,
        intent: str,
        hotel_name: str = None,
        manager_name: str = None,
        hotline: str = None
    ) -> dict:
        """
        Sinh câu phản hồi phù hợp với ngữ cảnh khách sạn.
        """
        hotel_name = hotel_name or settings.DEFAULT_HOTEL_NAME
        manager_name = manager_name or settings.HOTEL_MANAGER_NAME
        hotline = hotline or settings.HOTEL_HOTLINE

        # 1. Phân loại các khía cạnh khen / chê từ kết quả ABSA
        pos_aspects = [a['aspect'] for a in absa_results if a.get('sentiment') == 'positive']
        neg_aspects = [a['aspect'] for a in absa_results if a.get('sentiment') == 'negative']

        # 2. Xây dựng System Prompt & Tone theo từng loại Ý định (Intent)
        if intent == "CRITICAL_COMPLAINT":
            tone_guide = (
                "- Thái độ: Cực kỳ chân thành, cầu thị, nhận trách nhiệm, không bao biện, không đổ lỗi.\n"
                f"- Hành động: Xin lỗi sâu sắc về các sự cố cụ thể ({', '.join(neg_aspects) if neg_aspects else 'trải nghiệm chưa tốt'}).\n"
                f"- Cam kết: Khẳng định Ban Giám đốc đã chỉ đạo kiểm tra và khắc phục ngay sự cố.\n"
                f"- Lời mời: Cung cấp hotline {hotline} để trực tiếp trao đổi và có phương án bồi thường/hỗ trợ thỏa đáng."
            )
        elif intent == "IMPROVEMENT_SUGGESTION":
            tone_guide = (
                "- Thái độ: Biết ơn, trân trọng và cầu tiến.\n"
                "- Hành động: Cảm ơn chân thành vì những đóng góp quý báu mang tính xây dựng của quý khách.\n"
                "- Cam kết: Khẳng định đã chuyển ngay đề xuất này đến bộ phận Kỹ thuật / Quản lý để nghiên cứu nâng cấp dịch vụ trong thời gian sớm nhất."
            )
        else: # GENERAL_FEEDBACK
            tone_guide = (
                "- Thái độ: Nồng hậu, hiếu khách, ấm áp và chuyên nghiệp.\n"
                f"- Hành động: Cảm ơn khách đã dành thời gian đánh giá và hài lòng về ({', '.join(pos_aspects) if pos_aspects else 'dịch vụ'}).\n"
                "- Lời chúc: Chúc khách những chuyến đi tốt đẹp và mong sớm có cơ hội được đón tiếp lại."
            )

        # 3. Kỹ thuật Context Grounding trong Prompt
        prompt = f"""
Bạn là chuyên gia Quản lý Trải nghiệm Khách hàng đại diện cho {hotel_name}.
Nhiệm vụ của bạn là soạn một phản hồi chính thức, chuyên nghiệp và ấm áp gửi đến khách hàng vừa đăng đánh giá.

[THÔNG TIN ĐÁNH GIÁ CỦA KHÁCH HÀNG]
- Tên cơ sở: {hotel_name}
- Đánh giá gốc: "{review_text}"
- Số sao đánh giá: {rating if rating else 'Không rõ'}/5 sao
- Phân tích khía cạnh thực tế (ABSA Grounding):
  + Điểm khách hài lòng (Tích cực): {pos_aspects if pos_aspects else 'Không ghi nhận cụ thể'}
  + Điểm khách bức xúc / chưa ưng ý (Tiêu cực): {neg_aspects if neg_aspects else 'Không có'}
- Ý định chính (Intent): {intent}

[HƯỚNG DẪN SOẠN PHẢN HỒI]
{tone_guide}

[QUY TẮC BẮT BUỘC]
1. ĐÚNG TRỌNG TÂM: Phải nhắc đúng vào các khía cạnh khen/chê cụ thể mà khách nêu ở trên, tuyệt đối không xin lỗi hoặc cảm ơn chung chung, sáo rỗng.
2. ĐỘ DÀI: Khoảng 80 - 150 từ (vừa vặn, lịch sự, không dài dòng văn vở).
3. ĐỊNH DẠNG: Chỉ trả về nội dung câu trả lời hoàn chỉnh để gửi cho khách (bắt đầu bằng lời chào kính gửi, kết thúc bằng chữ ký {manager_name}). Không thêm bất kỳ lời dẫn nào khác.
"""

        # 4. Gọi Gemini API
        if not self.client:
            return {
                "success": False,
                "reply": f"Kính gửi Quý khách, {hotel_name} chân thành cảm ơn phản hồi của Quý khách và sẽ liên tục nỗ lực cải thiện chất lượng dịch vụ. Trân trọng, {manager_name}.",
                "source": "fallback_offline",
                "error": "Chưa cấu hình GEMINI_API_KEY trong file .env"
            }

        try:
            reply_text, model_used = generate_text_with_fallback(
                client=self.client,
                primary_model=self.model_name,
                prompt=prompt,
            )
            return {
                "success": True,
                "reply": reply_text,
                "source": "gemini_llm",
                "model_used": model_used,
            }
        except Exception as e:
            return {
                "success": False,
                "reply": f"Kính gửi Quý khách, {hotel_name} xin chân thành cảm ơn phản hồi của Quý khách. Chúng tôi luôn ghi nhận để hoàn thiện chất lượng phục vụ ngày một tốt hơn. Trân trọng, {manager_name}.",
                "source": "fallback_error",
                "error": str(e),
            }