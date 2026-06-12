"""fatura_yukle.py — PDF, PNG, JPEG ve JSON fatura dosyalarını parse eder."""
import base64
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent?key={key}"
)

_SCHEMA_PROMPT = (
    "Bu belge/görüntü bir tedarikçi faturasıdır. "
    "İçindeki tüm satır kalemlerini JSON array olarak çıkar.\n"
    "Her eleman şu alanları içermeli (eksikse null):\n"
    "  tedarikci   — fatura başlığındaki tedarikçi adı (string)\n"
    "  fatura_no   — fatura numarası (string)\n"
    "  tarih       — fatura tarihi GG.AA.YYYY formatında (string)\n"
    "  aciklama    — kalem açıklaması (string)\n"
    "  siparis_no  — sipariş/iş emri no (string veya null)\n"
    "  miktar      — sayısal miktar (number)\n"
    "  birim       — ölçü birimi: KG, Adet, Set, m, m2 vb. (string)\n"
    "  birim_fiyat — birim fiyat (number)\n"
    "  tutar       — toplam tutar (number)\n"
    "SADECE geçerli bir JSON array döndür. Başka hiçbir şey yazma."
)


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError(
            "GEMINI_API_KEY bulunamadı.\n"
            "PDF/görsel parse için .env dosyasına GEMINI_API_KEY eklenmeli."
        )
    return key


def _gemini_metin(metin: str) -> list:
    key = _api_key()
    payload = {
        "contents": [{"parts": [{"text": _SCHEMA_PROMPT + "\n\n" + metin}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    url = _GEMINI_URL.format(key=key)
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                return json.loads(text)
            if resp.status_code in (429, 503):
                import time; time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"Gemini API hatası: HTTP {resp.status_code}\n{resp.text[:200]}")
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == 2:
                raise RuntimeError(f"Gemini bağlantı hatası: {e}") from e
            import time; time.sleep(5)
    raise RuntimeError("Gemini API 3 denemede yanıt vermedi.")


def _gemini_gorsel(dosya_yolu: str, mime_type: str) -> list:
    key = _api_key()
    with open(dosya_yolu, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"text": _SCHEMA_PROMPT},
                {"inlineData": {"mimeType": mime_type, "data": img_b64}},
            ]
        }],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    url = _GEMINI_URL.format(key=key)
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=90)
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                return json.loads(text)
            if resp.status_code in (429, 503):
                import time; time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"Gemini API hatası: HTTP {resp.status_code}\n{resp.text[:200]}")
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == 2:
                raise RuntimeError(f"Gemini bağlantı hatası: {e}") from e
            import time; time.sleep(5)
    raise RuntimeError("Gemini Vision API 3 denemede yanıt vermedi.")


def parse_fatura(dosya_yolu: str) -> list:
    """Fatura dosyasını parse eder; list[dict] döndürür.

    Desteklenen formatlar: .pdf, .png, .jpg, .jpeg, .json
    """
    ext = os.path.splitext(dosya_yolu)[1].lower()

    if ext == ".json":
        with open(dosya_yolu, encoding="utf-8") as f:
            veri = json.load(f)
        if not isinstance(veri, list):
            raise ValueError("JSON dosyası bir liste içermelidir.")
        return veri

    if ext == ".pdf":
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError(
                "pdfplumber yüklü değil. Terminalde çalıştırın:\n"
                "  pip install pdfplumber"
            ) from exc
        with pdfplumber.open(dosya_yolu) as pdf:
            metin = "\n".join(
                (sayfa.extract_text() or "") for sayfa in pdf.pages
            )
        if len(metin.strip()) < 80:
            raise ValueError(
                "PDF metin içermiyor (taranmış görsel olabilir).\n"
                "Lütfen faturayı PNG veya JPEG olarak kaydedip tekrar deneyin."
            )
        return _gemini_metin(metin)

    if ext in (".png", ".jpg", ".jpeg"):
        mime = "image/png" if ext == ".png" else "image/jpeg"
        return _gemini_gorsel(dosya_yolu, mime)

    raise ValueError(
        f"Desteklenmeyen dosya formatı: '{ext}'\n"
        "Desteklenen: PDF, PNG, JPG, JPEG, JSON"
    )
