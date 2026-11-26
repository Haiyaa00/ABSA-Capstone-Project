"""
Module: gemini_helper.py
Mo ta: Ham tien ich dung chung khoi tao Gemini Client va goi API kem co che du phong model
       khi gap loi 503/qua tai, tranh bi treo request tren Mobile App.
"""

from typing import Tuple
from google import genai
from google.genai import types

DEFAULT_FALLBACK_MODELS = ("gemini-3.8-flash", "gemini-3.5-flash")


def create_gemini_client(api_key: str):
    """Khoi tao Gemini Client voi timeout 15s va khong retry ngam gay tre fallback."""
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=15000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def generate_text_with_fallback(client, primary_model: str, prompt: str) -> Tuple[str, str]:
    """
    Goi Gemini API theo thu tu uu tien: primary_model -> danh sach model du phong.
    Tra ve (noi_dung_phan_hoi, ten_model_da_dung). Nem lai loi cuoi cung neu tat ca that bai.
    """
    candidates = list(dict.fromkeys([primary_model, *DEFAULT_FALLBACK_MODELS]))
    last_error = None

    for model_name in candidates:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            return response.text.strip(), model_name
        except Exception as exc:
            last_error = exc

    raise last_error
