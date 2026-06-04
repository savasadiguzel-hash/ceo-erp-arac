import os
import time
import base64
import json
from typing import Any
import requests
from dotenv import load_dotenv

load_dotenv()  # .env dosyasindaki degiskenleri ortama yukler

AI_MEMORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_memory.json")
AI_MEMORY_MAX  = 20   # prompte enjekte edilecek maksimum giris sayisi


# ---------------------------------------------------------------------------
# HAFIZA FONKSIYONLARI
# ---------------------------------------------------------------------------

def _load_ai_memory() -> list:
    """ai_memory.json'dan kayitlari yukler. Dosya yoksa bos liste dondurur."""
    try:
        if os.path.exists(AI_MEMORY_PATH):
            with open(AI_MEMORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def update_ai_memory(gorsel_ozet: str, kategori: str) -> None:
    """Yeni bir gorsel-ozellik + kategori ciftini ai_memory.json'a ekler.

    Dosya adi (part_name) KAYDEDILMEZ — sadece gorsel ozellik ve kategori.
    gorsel_ozet veya kategori bos ise islem atlaniyor.
    """
    if not gorsel_ozet or not kategori:
        return
    entries = _load_ai_memory()
    entries.append({"gorsel_ozet": gorsel_ozet, "kategori": kategori})
    try:
        with open(AI_MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _memory_context() -> str:
    """Son AI_MEMORY_MAX girisi prompte enjekte edilecek metin olarak dondurur."""
    entries = _load_ai_memory()
    if not entries:
        return ""
    recent = entries[-AI_MEMORY_MAX:]
    lines  = "\n".join(
        f"- Gorsel: '{e.get('gorsel_ozet','')}' -> Kategori: {e.get('kategori','')}"
        for e in recent
        if e.get("gorsel_ozet") and e.get("kategori")
    )
    if not lines:
        return ""
    return (
        "\n\nGecmiste benzer fiziksel ozelliklere sahip parcalar icin "
        "sirketimizin sectigi kategoriler sunlardir:\n"
        + lines
        + "\nLutfen bu yeni gorseli analiz ederken bu sirketin gorsel "
          "standartlarini dikkate al."
    )


# ---------------------------------------------------------------------------
# ANA ANALIZ FONKSIYONU
# ---------------------------------------------------------------------------

def analyze_part_with_vision(image_paths) -> dict:
    """Goruntu dosyasi/dosyalarini Gemini Vision API ile siniflandirir.

    image_paths: tek dosya yolu (str) veya yol listesi (list[str]).
    Liste verildiginde tum gorunumler tek istekte Gemini'ye gonderilir.

    Donus:
      Basari     : {"kategori": "...", "guven_orani": ..., "gerekce": "...", "gorsel_ozet": "..."}
      API arizasi: {"kategori": "API_ARIZASI"}
      API key yok: {}
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {}

    if isinstance(image_paths, str):
        image_paths = [image_paths]

    memory = _memory_context()

    try:
        _KATEGORI_ACIKLAMA = (
            "1. 'Mekanik': Metal veya plastik yapisal parcalar — sac levha, lazer kesim plaka, "
            "CNC govde, mil, aks, pim, flanş, braket, silindirik parca. "
            "METAL veya PLASTIK malzemeli, yapisal fonksiyonlu parcalar.\n"
            "2. 'Elektronik': Baski devre kartlari (PCB), sensorler, elektronik bilesenler.\n"
            "3. 'Optik': CAM veya kristal malzemeli her turlu optik eleman — kavisli mercekler, "
            "duz cam levhalar, optik pencereler, filtreler, prizmalar, aynalar. "
            "SolidWorks'te gri/saydam gorunseler de cam/kristal malzemeli duz levhalar "
            "MEKANIK degil OPTIK kategorisindedir.\n\n"
            "ONEMLI: Duz, yassı bir parca gorduğunde malzeme ipucuna bak — "
            "metalik/mat gri ise Mekanik, seffaf/cam gorunumlu ise Optik olabilir.\n\n"
        )

        multi = len(image_paths) > 1
        if multi:
            prompt = (
                "Sana ayni SolidWorks 3D CAD parcasinin birden fazla standart gorunum "
                "ekran goruntusunu veriyorum (izometrik, dimetrik, trimetrik). "
                "Tum gorunumleri birlikte degerlendir ve su 3 kategoriden hangisine ait "
                "oldugunu sec:\n"
                + _KATEGORI_ACIKLAMA
                + "KESINLIKLE sadece su 3 degerden birini kullan: 'Mekanik', 'Elektronik', 'Optik'. "
                "SADECE su JSON formatinda cevap ver: "
                "{\"kategori\": \"Mekanik\"|\"Elektronik\"|\"Optik\", "
                "\"guven_orani\": 0.94, \"gerekce\": \"nedeni\", "
                "\"gorsel_ozet\": \"parcayi 3-5 kelimeyle gorsel olarak betimle\"}"
                + memory
            )
        else:
            prompt = (
                "Sana bir SolidWorks 3D CAD parcasinin ekran goruntusunu veriyorum. "
                "Bu parcayi analiz et ve su 3 kategoriden hangisine ait oldugunu sec:\n"
                + _KATEGORI_ACIKLAMA
                + "KESINLIKLE sadece su 3 degerden birini kullan: 'Mekanik', 'Elektronik', 'Optik'. "
                "SADECE su JSON formatinda cevap ver: "
                "{\"kategori\": \"Mekanik\"|\"Elektronik\"|\"Optik\", "
                "\"guven_orani\": 0.94, \"gerekce\": \"nedeni\", "
                "\"gorsel_ozet\": \"parcayi 3-5 kelimeyle gorsel olarak betimle\"}"
                + memory
            )

        content_parts: list[dict[str, Any]] = [{"text": prompt}]
        for path in image_paths:
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            content_parts.append({"inlineData": {"mimeType": "image/png", "data": img_b64}})

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={api_key}"
        )
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": content_parts}],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        for attempt in range(3):
            try:
                time.sleep(5)  # burst korumasi + deneme arasi bekleme
                response = requests.post(url, headers=headers, json=payload, timeout=60)  # type: ignore[arg-type]

                if response.status_code == 200:
                    res_data = response.json()
                    text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return json.loads(text)

                if response.status_code in (429, 503):
                    print(f"      [API {response.status_code}] Deneme {attempt + 1}/3 basarisiz, yeniden deneniyor...")
                    continue

                print(f"      [API hata] HTTP {response.status_code}: {response.text[:120]}")
                break

            except requests.Timeout:
                print(f"      [Timeout] Deneme {attempt + 1}/3 basarisiz, yeniden deneniyor...")
                continue
            except Exception as e:
                print(f"      [Vision istisna] {e}")
                break

    except Exception as e:
        print(f"      [Vision istisna] {e}")

    return {"kategori": "API_ARIZASI"}
