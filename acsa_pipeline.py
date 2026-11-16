"""
Module: acsa_pipeline.py
Mô tả: Pipeline toàn diện xử lý câu review từ Google Maps:
       Tokenize -> PhoBERT ABSA (34 Ngưỡng Động) -> Intent Detection -> JSON cho Mobile App
"""

import os
os.environ["USE_TORCH"] = "0"
os.environ["USE_TF"] = "1"
os.environ['TF_USE_LEGACY_KERAS'] = '1'   
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0' 

import sys
import numpy as np
import tensorflow as tf
from transformers import AutoTokenizer
from processors.reply_generator import AIReplyGenerator

from acsa_model import VLSP2018MultiTask
from processors.vietnamese_processor import VietnameseTextPreprocessor
from processors.vlsp2018_processor import PolarityMapping
from processors.intent_detector import HybridIntentDetector

# BẢNG 34 NGƯỠNG ĐỘNG TỐI ƯU ĐÃ ĐẠT KỶ LỤC F1 = 77.24%
OPTIMAL_THRESHOLDS = {
    'FACILITIES#CLEANLINESS': 0.34, 'FACILITIES#COMFORT': 0.28,
    'FACILITIES#DESIGN&FEATURES': 0.20, 'FACILITIES#GENERAL': 0.40,
    'FACILITIES#MISCELLANEOUS': 0.20, 'FACILITIES#PRICES': 0.20,
    'FACILITIES#QUALITY': 0.34, 'FOOD&DRINKS#MISCELLANEOUS': 0.20,
    'FOOD&DRINKS#PRICES': 0.22, 'FOOD&DRINKS#QUALITY': 0.22,
    'FOOD&DRINKS#STYLE&OPTIONS': 0.26, 'HOTEL#CLEANLINESS': 0.22,
    'HOTEL#COMFORT': 0.28, 'HOTEL#DESIGN&FEATURES': 0.20,
    'HOTEL#GENERAL': 0.34, 'HOTEL#MISCELLANEOUS': 0.26,
    'HOTEL#PRICES': 0.26, 'HOTEL#QUALITY': 0.30,
    'LOCATION#GENERAL': 0.20, 'ROOMS#CLEANLINESS': 0.50,
    'ROOMS#COMFORT': 0.44, 'ROOMS#DESIGN&FEATURES': 0.44,
    'ROOMS#GENERAL': 0.30, 'ROOMS#MISCELLANEOUS': 0.20,
    'ROOMS#PRICES': 0.28, 'ROOMS#QUALITY': 0.46,
    'ROOM_AMENITIES#CLEANLINESS': 0.22, 'ROOM_AMENITIES#COMFORT': 0.20,
    'ROOM_AMENITIES#DESIGN&FEATURES': 0.24, 'ROOM_AMENITIES#GENERAL': 0.44,
    'ROOM_AMENITIES#MISCELLANEOUS': 0.20, 'ROOM_AMENITIES#PRICES': 0.20,
    'ROOM_AMENITIES#QUALITY': 0.34, 'SERVICE#GENERAL': 0.42
}

class ACSAPipeline:
    def __init__(self, weights_path=None, pretrained_model='vinai/phobert-base', max_length=256):
        print("⏳ Đang khởi tạo bộ tiền xử lý và nạp mô hình PhoBERT...")
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(pretrained_model)
        self.preprocessor = VietnameseTextPreprocessor(
            vncorenlp_dir='D:/VnCoreNLP',
            max_correction_length=max_length
        )

        # 34 nhánh khía cạnh
        self.aspect_names = list(OPTIMAL_THRESHOLDS.keys())
        self.multi_branch_names = {name: f'output_{i+1}' for i, name in enumerate(self.aspect_names)}

        # Khởi tạo mô hình
        optimizer = tf.keras.optimizers.Adam(learning_rate=1e-5)
        self.model = VLSP2018MultiTask(
            pretrained_model, self.multi_branch_names, optimizer, multi_branch=True
        )

        # Nạp trọng số đã huấn luyện
        if weights_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            weights_path = os.path.join(base_dir, 'experiments', 'weights', 'Hotel-v2-phobert-normalized', 'Hotel-v2-phobert-normalized')
        
        self.model.load_weights(weights_path).expect_partial()
        print("✅ Đã nạp thành công Checkpoint trọng số PhoBERT!")

        # Khởi tạo Intent Detector
        self.intent_detector = HybridIntentDetector()

        self.reply_generator = AIReplyGenerator()

    def analyze_review(self, review_text: str, rating: int = None) -> dict:
        # 1. Tiền xử lý văn bản
        cleaned_text = self.preprocessor.process_batch([review_text], correct_errors=False)

        # 2. Tokenize
        inputs = self.tokenizer(
            cleaned_text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='tf'
        )

        tf_inputs = {col: inputs[col] for col in self.tokenizer.model_input_names}

        # 3. PhoBERT dự đoán xác suất (34 nhánh)
        raw_outputs = self.model.predict(tf_inputs, verbose=0)
        # raw_outputs có dạng list 34 phần tử, mỗi phần tử shape (1, 4)
        
        detected_aspects = []
        for j, aspect in enumerate(self.aspect_names):
            probs_col = raw_outputs[j][0] # shape (4,) -> [p_none, p_pos, p_neg, p_neu]
            sentiment_probs = probs_col[1:4]
            max_prob = np.max(sentiment_probs)
            best_cls = np.argmax(sentiment_probs) + 1 # 1: pos, 2: neg, 3: neu

            threshold = OPTIMAL_THRESHOLDS.get(aspect, 0.35)
            if max_prob >= threshold:
                polarity_str = PolarityMapping.INDEX_TO_POLARITY.get(best_cls, "neutral")
                detected_aspects.append({
                    "aspect": aspect,
                    "sentiment": polarity_str,
                    "confidence": round(float(max_prob), 4)
                })

        # 4. Nhận diện Ý định (Intent Detection) bằng Kiến trúc Lai
        intent_info = self.intent_detector.detect_intent(
            text=review_text,
            rating=rating,
            absa_results=detected_aspects
        )

        # 5. Đóng gói JSON hoàn chỉnh gửi về Mobile App
        return {
            "text": review_text,
            "rating": rating,
            "aspects_count": len(detected_aspects),
            "aspects": detected_aspects,
            "intent": intent_info["intent"],
            "intent_confidence": intent_info["confidence"],
            "detection_method": intent_info["detection_method"],
            "intent_reason": intent_info["reason"],
            "task_action": intent_info["task_action"]
        }

    def generate_reply_for_review(self, analysis_result: dict, hotel_name: str = None) -> dict:
        """
        Nhận kết quả từ analyze_review() và gọi AI sinh phản hồi phù hợp.
        """
        return self.reply_generator.generate_reply(
            review_text=analysis_result["text"],
            rating=analysis_result["rating"],
            absa_results=analysis_result["aspects"],
            intent=analysis_result["intent"],
            hotel_name=hotel_name
        )