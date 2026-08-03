"""
Excel'den taslak (CEO ERP'ye henüz işlenmemiş) mamül ağacı okuma.

Çıktısı db.sorgular.bom_listesi() ile aynı şekildeki bir bom dict'idir,
böylece logic.maliyet.mamul_maliyet_hesapla() değişmeden kullanılabilir.

Desteklenen dosya şekilleri:
- Düz liste: Stok Kodu + Miktar sütunları (başlık adıyla bulunur), hiyerarşi yok.
  Miktarı boş satırlar kategori başlığı sayılıp atlanır (ör. "ELEKTRONİK").
- Hiyerarşik: yukarıdakine ek olarak Tip + Seviye sütunları da varsa,
  Mamül/Yarımamül/Reçete düğümleri kendi alt ağaçlarıyla özyinelemeli hesaplanır.
- Miktar sütunu hiç yoksa (yalnızca "Stok Kodu" başlığı, gerçek ADLASMKE şekli):
  miktar bilgisi olmadığından tüm bileşenler miktar=1 varsayılır (uyarı eklenir).
- Hiçbir tanınan başlık yoksa: Stok Hazırlık sekmesindeki pozisyonel tespit
  (Seviye-Tip / Tip+girinti / düz kod-ad) mantığı tekrarlanır.
"""
import re
from pathlib import Path

import openpyxl

_TIP_SECENEKLER = ["Hammadde", "Yarımamül", "Mamül", "Reçete", "Masraf"]
_BASLIK_ATLA = {"tip", "kod", "stok kodu", "stok adi", "stok adı",
                "ad", "adi", "adı", "type", "code", "name", "seviye"}

_TR_ASCII = str.maketrans({
    "İ": "i", "I": "i", "ı": "i",
    "Ş": "s", "ş": "s",
    "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u",
    "Ö": "o", "ö": "o",
    "Ç": "c", "ç": "c",
})

_BASLIK_KOD    = {"stok kodu", "kod", "code"}
_BASLIK_MIKTAR = {"miktar", "adet", "quantity", "qty"}
_BASLIK_TIP    = {"tip", "type"}
_BASLIK_SEVIYE = {"seviye", "level"}
_BASLIK_AD     = {"stok adi", "adi", "ad", "name"}


def _norm(v) -> str:
    if v is None:
        return ""
    return str(v).strip().translate(_TR_ASCII).lower()


def _kod_str(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _miktar_parse(v, uyarilar: list, kod: str) -> float:
    """Miktar hücresini float'a çevirir; "20M" gibi birim ekli metinlerde
    baştaki sayıyı alır. Hiç sayı yoksa 1.0 varsayar ve uyarı ekler."""
    if v is None:
        return 1.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        pass
    m = re.match(r"[\d.]+", s)
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    uyarilar.append(f"{kod}: miktar '{v}' sayıya çevrilemedi, 1 varsayıldı")
    return 1.0


def _header_haritasi(header_row) -> dict:
    harita: dict = {}
    for i, hucre in enumerate(header_row):
        n = _norm(hucre)
        if not n:
            continue
        if "kod_col" not in harita and n in _BASLIK_KOD:
            harita["kod_col"] = i
        elif "miktar_col" not in harita and n in _BASLIK_MIKTAR:
            harita["miktar_col"] = i
        elif "tip_col" not in harita and n in _BASLIK_TIP:
            harita["tip_col"] = i
        elif "seviye_col" not in harita and n in _BASLIK_SEVIYE:
            harita["seviye_col"] = i
        elif "ad_col" not in harita and n in _BASLIK_AD:
            harita["ad_col"] = i
    return harita


def _satir_dolu(row) -> bool:
    return any(v is not None and str(v).strip() != "" for v in row)


def excel_dosyasindan_bom_oku(dosya_yolu: str):
    """
    Döner: (bom, kok_kodlari, uyarilar)

    bom: {kod: {"ad": str, "birim": str, "bilesenleri": [{"kod","ad","miktar","birim","tip"}]}}
    kok_kodlari: en üst seviye mamül/reçete kod(lar)ı — mamul_maliyet_hesapla ile
                 tek tek çağrılacak "kök" kodlar (genelde tek).
    uyarilar: kullanıcıya gösterilecek uyarı metinleri.
    """
    wb = openpyxl.load_workbook(dosya_yolu, read_only=True, data_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()

    uyarilar: list[str] = []
    dosya_adi = Path(dosya_yolu).stem
    kok_sentetik = f"__EXCEL__{dosya_adi}"

    ilk = next((r for r in all_rows if _satir_dolu(r)), None)
    harita = _header_haritasi(ilk) if ilk else {}

    satirlar: list[dict] = []   # {depth, tip, kod, ad, miktar, birim}

    if "kod_col" in harita and "miktar_col" in harita:
        # ── Miktar sütunu adıyla bulundu: düz veya hiyerarşik ───────────────
        kod_col, miktar_col = harita["kod_col"], harita["miktar_col"]
        ad_col     = harita.get("ad_col")
        tip_col    = harita.get("tip_col")
        seviye_col = harita.get("seviye_col")
        hiyerarsik = tip_col is not None and seviye_col is not None

        baslik_gecildi = False
        for row in all_rows:
            if not _satir_dolu(row):
                continue
            if not baslik_gecildi:
                baslik_gecildi = True
                continue
            kod_ham = row[kod_col] if kod_col < len(row) else None
            if kod_ham is None or str(kod_ham).strip() == "":
                continue
            kod = _kod_str(kod_ham)
            miktar_ham = row[miktar_col] if miktar_col < len(row) else None
            if miktar_ham is None or str(miktar_ham).strip() == "":
                continue   # kategori başlığı satırı (ör. "ELEKTRONİK") — atla
            ad = str(row[ad_col]).strip() if (ad_col is not None and ad_col < len(row) and row[ad_col]) else kod
            tip_ham = row[tip_col] if (tip_col is not None and tip_col < len(row)) else None
            tip_str = str(tip_ham).strip() if tip_ham else ""
            if hiyerarsik:
                seviye_ham = row[seviye_col] if seviye_col < len(row) else None
                try:
                    depth = int(float(seviye_ham))
                except (TypeError, ValueError):
                    depth = 0
            else:
                depth = 1   # sentetik kökün altında tek seviye

            satirlar.append({"depth": depth, "tip": tip_str, "kod": kod, "ad": ad,
                              "miktar": _miktar_parse(miktar_ham, uyarilar, kod),
                              "birim": "ADET"})

        if not hiyerarsik:
            satirlar.insert(0, {"depth": 0, "tip": "Mamül", "kod": kok_sentetik,
                                 "ad": dosya_adi, "miktar": 1.0, "birim": "ADET"})

    elif "kod_col" in harita:
        # ── Miktar sütunu yok: gerçek ADLASMKE şekli — miktar=1 varsayılır ──
        uyarilar.append("Bu dosyada Miktar sütunu bulunamadı; tüm adetler 1 varsayıldı.")
        kod_col = harita["kod_col"]
        ad_col  = harita.get("ad_col")
        satirlar.append({"depth": 0, "tip": "Mamül", "kod": kok_sentetik,
                          "ad": dosya_adi, "miktar": 1.0, "birim": "ADET"})
        baslik_gecildi = False
        for row in all_rows:
            if not _satir_dolu(row):
                continue
            if not baslik_gecildi:
                baslik_gecildi = True
                continue
            kod_ham = row[kod_col] if kod_col < len(row) else None
            if kod_ham is None or str(kod_ham).strip() == "":
                continue
            kod = _kod_str(kod_ham)
            ad = str(row[ad_col]).strip() if (ad_col is not None and ad_col < len(row) and row[ad_col]) else kod
            satirlar.append({"depth": 1, "tip": "", "kod": kod, "ad": ad,
                              "miktar": 1.0, "birim": "ADET"})

    else:
        # ── Tanınan başlık yok: Stok Hazırlık'ın pozisyonel tespiti ─────────
        satirlar.append({"depth": 0, "tip": "Mamül", "kod": kok_sentetik,
                          "ad": dosya_adi, "miktar": 1.0, "birim": "ADET"})
        for row in all_rows:
            if not _satir_dolu(row):
                continue
            raw = [str(v).strip() if v is not None else "" for v in row[:7]]
            while len(raw) < 7:
                raw.append("")
            col_a = raw[0]
            if _norm(col_a) in _BASLIK_ATLA:
                continue
            try:
                depth = int(float(col_a))
                tip_val = raw[1] if raw[1] in _TIP_SECENEKLER else "Hammadde"
                kod, ad, miktar_ham = raw[2], (raw[3] or raw[2]), (raw[5] or "1")
            except (ValueError, TypeError):
                if col_a in _TIP_SECENEKLER:
                    girinti = len(raw[1]) - len(raw[1].lstrip(" "))
                    tip_val, depth = col_a, girinti // 2 + 1
                    kod = raw[1].strip()
                    ad, miktar_ham = (raw[2] or kod), (raw[4] or "1")
                else:
                    tip_val, depth = "Hammadde", 1
                    kod = col_a
                    ad, miktar_ham = (raw[1] or kod), "1"
            if not kod:
                continue
            satirlar.append({"depth": depth, "tip": tip_val, "kod": _kod_str(kod), "ad": ad,
                              "miktar": _miktar_parse(miktar_ham, uyarilar, kod),
                              "birim": "ADET"})

    # ── Ortak geçiş: depth/parent_stack → bom dict ──────────────────────────
    bom: dict = {}
    kok_kodlari: list[str] = []
    parent_stack: list[tuple[int, str]] = []
    cocuklu: set[str] = set()
    islenmis: list[tuple[dict, str | None]] = []

    for s in satirlar:
        depth = s["depth"]
        while parent_stack and parent_stack[-1][0] >= depth:
            parent_stack.pop()
        parent_kod = parent_stack[-1][1] if parent_stack else None
        islenmis.append((s, parent_kod))
        if parent_kod is not None:
            cocuklu.add(parent_kod)
        parent_stack.append((depth, s["kod"]))

    for s, parent_kod in islenmis:
        kod, ad, miktar, birim, tip_str = s["kod"], s["ad"], s["miktar"], s["birim"], s["tip"]
        if kod in cocuklu or parent_kod is None:
            bom.setdefault(kod, {"ad": ad, "birim": birim, "bilesenleri": []})
        if parent_kod is None:
            kok_kodlari.append(kod)
            continue
        bom.setdefault(parent_kod, {"ad": "", "birim": "ADET", "bilesenleri": []})
        mevcut = next((b for b in bom[parent_kod]["bilesenleri"] if b["kod"] == kod), None)
        if mevcut is not None:
            # Düzleştirilmiş listede aynı kod birden fazla alt-montajdan gelmiş
            # olabilir (ör. aynı vida birden fazla yerde) — miktarlar toplanır.
            mevcut["miktar"] += miktar
            continue
        if _norm(tip_str) == "masraf":
            b_tip = "masraf"
        elif kod in cocuklu:
            b_tip = "stok"   # 'kod in bom' dispatch'te recursion tetikler
        else:
            b_tip = "stok_oto"
        bom[parent_kod]["bilesenleri"].append({
            "kod": kod, "ad": ad, "miktar": miktar, "birim": birim, "tip": b_tip,
        })

    return bom, kok_kodlari, uyarilar
