"""
Maliyet hesaplama iş mantığı. UI ve DB'den bağımsızdır.

Önbellekleme stratejisi
-----------------------
Her hesaplama oturumu için dışarıdan bir `_cache: dict` geçirilir.
- Anahtar formatı:  ("birim", stok_kodu, metod, bas, bit)
                    ("mamul", mamul_kodu, metod, bas, bit)
- Aynı parametrelerle daha önce hesaplanmış sonuçlar DB'ye gidilmeden döner.
- Paylaşılan alt bileşenler (çok mamülde geçen stoklar) tek seferinde sorgulanır.
- `_cache=None` geçilirse fonksiyon kendi önbelleğini oluşturur (bağımsız çağrı).

Performans notu
---------------
`bom` parametresi dışarıdan geçilmeli; geçilmezse lazy-load yapılır.
`excel.py` gibi çok mamül hesaplayan üst katmanlar BOM'u bir kez çekip
tüm çağrılara aynı dict'i geçerek gereksiz DB round-trip'lerini önler.
"""
from db.sorgular import (
    stok_fiyat_gecmisi, masraf_fiyat_gecmisi, bom_listesi,
    proje_satinalma_hareketleri,
)


def _metod_uygula(fiyatlar: list[dict], metod: str, bas: str, bit: str) -> float:
    """Fiyat geçmişi listesine seçilen yöntemi uygular. Boşsa 0.0 döner."""
    filtreli = [f for f in fiyatlar if bas <= f["tarih"] <= bit]
    if not filtreli:
        return 0.0
    if metod == "WA":
        top_t = sum(f["birim_fiyat"] * f["miktar"] for f in filtreli)
        top_m = sum(f["miktar"] for f in filtreli)
        return top_t / top_m if top_m else 0.0
    if metod == "FIFO":
        return min(filtreli, key=lambda x: x["tarih"])["birim_fiyat"]
    if metod == "LIFO":
        return max(filtreli, key=lambda x: x["tarih"])["birim_fiyat"]
    return 0.0


def birim_maliyet(
    conn, stok_kodu: str, metod: str, bas: str, bit: str,
    _cache: dict | None = None,
) -> float:
    """
    Stok için seçilen yönteme göre birim maliyet döner.
    metod: 'WA' | 'FIFO' | 'LIFO'   bas/bit: 'YYYY-MM-DD'

    Aynı (stok_kodu, metod, bas, bit) için _cache varsa DB'ye gidilmez.
    """
    if _cache is None:
        _cache = {}

    key = ("birim", stok_kodu, metod, bas, bit)
    if key in _cache:
        return _cache[key]

    sonuc = _metod_uygula(stok_fiyat_gecmisi(conn, stok_kodu, bas, bit), metod, bas, bit)
    _cache[key] = sonuc
    return sonuc


def masraf_birim_maliyet(
    conn, masraf_kodu: str, metod: str, bas: str, bit: str,
    _cache: dict | None = None,
) -> float:
    """
    Masraf kartı için seçilen yönteme göre birim maliyet döner (LIFO/FIFO/WA).

    Fallback: Masraf kartında fatura girişi yoksa, AYNI kod StokKarti'de
    aranır ve oradaki fatura geçmişi kullanılır. Böylece bir operasyon
    (ör. `GMP-200-230602:20` FREZE) maliyeti hangi kart tarafına
    işlendiyse oradan alınır — mükerrer sayım olmadan. Öncelik masrafta;
    masraf boşsa stok. Her iki durumda da seçilen yöntem (FIFO/LIFO/WA)
    uygulanır.
    """
    if _cache is None:
        _cache = {}

    key = ("masraf", masraf_kodu, metod, bas, bit)
    if key in _cache:
        return _cache[key]

    sonuc = _metod_uygula(masraf_fiyat_gecmisi(conn, masraf_kodu, bas, bit), metod, bas, bit)
    if sonuc == 0.0:
        # Masrafta fatura yok → aynı kodu StokKarti'de dene
        sonuc = _metod_uygula(stok_fiyat_gecmisi(conn, masraf_kodu, bas, bit), metod, bas, bit)

    _cache[key] = sonuc
    return sonuc


def birim_maliyet_oto(
    conn, kod: str, metod: str, bas: str, bit: str,
    _cache: dict | None = None,
) -> float:
    """
    Excel'den okunan taslak mamül ağaçlarında bir bileşenin stok mu masraf/
    operasyon mu olduğu bilinmez. Önce StokKarti fatura fiyatına bakar,
    sonuç 0.0 ise StokMasrafKarti'ye düşer (masraf_birim_maliyet'in
    masraf→stok fallback sırasının tersi — bu listede çoğunluk fiziksel parça).
    """
    if _cache is None:
        _cache = {}

    sonuc = birim_maliyet(conn, kod, metod, bas, bit, _cache)
    if sonuc == 0.0:
        sonuc = masraf_birim_maliyet(conn, kod, metod, bas, bit, _cache)
    return sonuc


def mamul_maliyet_hesapla(
    conn, mamul_kodu: str, metod: str, bas: str, bit: str,
    _cache: dict | None = None,
    _visiting: frozenset | None = None,
    bom: dict | None = None,
) -> tuple[list[dict], float]:
    """
    Mamül için özyinelemeli bileşen bazında maliyet hesaplar.

    Çok seviyeli BOM desteği: bir bileşen de BOM'da mamül olarak varsa
    maliyeti özyinelemeli hesaplanır ve önbelleklenir.

    _cache   : Dışarıdan geçirilirse birden fazla mamül aynı önbelleği paylaşır.
               None ise bu çağrıya özgü dict oluşturulur.
    _visiting: Döngüsel BOM referanslarına karşı koruma (frozenset, değişmez).
    bom      : Dışarıdan geçirilirse DB'ye tekrar gidilmez (performans).
               None ise lazy-load yapılır.

    Döner: tuple[list[dict], float]
           Her koşulda ([], 0.0) veya (satirlar, toplam) biçiminde döner.
    """
    if _cache    is None: _cache    = {}
    if _visiting is None: _visiting = frozenset()
    if bom       is None: bom       = bom_listesi(conn)

    # Döngüsel BOM koruması: ziyaret yığınındaki mamüle tekrar girilmez
    if mamul_kodu in _visiting:
        return [], 0.0

    mamul_key = ("mamul", mamul_kodu, metod, bas, bit)
    if mamul_key in _cache:
        return _cache[mamul_key]

    mamul = bom.get(mamul_kodu)
    if not mamul:
        return [], 0.0

    ziyaret_edildi = _visiting | {mamul_kodu}   # frozenset birleşimi — orijinal değişmez

    satirlar: list[dict] = []
    toplam = 0.0

    for b in mamul["bilesenleri"]:
        if b.get("tip") == "masraf":
            bm = masraf_birim_maliyet(conn, b["kod"], metod, bas, bit, _cache)
        elif b["kod"] in bom:
            # Alt bileşen aynı zamanda bir mamül → özyinelemeli hesapla
            _, bm = mamul_maliyet_hesapla(
                conn, b["kod"], metod, bas, bit, _cache, ziyaret_edildi, bom
            )
        elif b.get("tip") == "stok_oto":
            # Excel taslak ağacından gelen, stok/masraf ayrımı bilinmeyen bileşen
            bm = birim_maliyet_oto(conn, b["kod"], metod, bas, bit, _cache)
        else:
            bm = birim_maliyet(conn, b["kod"], metod, bas, bit, _cache)

        satir_top = b["miktar"] * bm
        toplam   += satir_top
        if b.get("oto"):
            tip_etiket = "MASRAF (OTO)"
        elif b.get("tip") == "masraf":
            tip_etiket = "MASRAF"
        else:
            tip_etiket = "BİLEŞEN"
        satirlar.append({
            "tip":        tip_etiket,
            "bil_kod":    b["kod"],
            "bil_ad":     b["ad"],
            "bom_miktar": b["miktar"],
            "birim":      b["birim"],
            "birim_mal":  bm,
            "satir_top":  satir_top,
        })

    sonuc = (satirlar, toplam)
    _cache[mamul_key] = sonuc
    return sonuc


def proje_fiili_maliyet(
    conn, proje_kodu: str, bas: str, bit: str,
) -> tuple[list[dict], float]:
    """
    Bir projeye fiilen kesilmiş alış faturası/irsaliyesi satırlarını ve alış
    iadelerini bileşen kodu (bil_kod) bazında gruplayıp net toplam harcamayı
    döner. İade satırları negatif miktar/tutar olarak gelir.

    Ham satırlar proje_satinalma_hareketleri()'nden gelir (satır bazında
    ProjeId filtresiyle); burada sadece kod bazında toplanır — aynı kalem
    birden fazla faturada geçebilir. Alış iadeleri aynı kodun net miktar ve
    tutarından düşülür.

    Döner: tuple[list[dict], float]
           satirlar: [{"bil_kod","bil_ad","tip","miktar","tutar",
                       "birim_fiyat_ort","fatura_sayisi"}, ...]
           toplam:   tüm satırların tutar toplamı
    """
    hareketler = proje_satinalma_hareketleri(conn, proje_kodu, bas, bit)

    gruplar: dict[str, dict] = {}
    for h in hareketler:
        g = gruplar.setdefault(h["bil_kod"], {
            "bil_kod": h["bil_kod"], "bil_ad": h["bil_ad"], "tip": h["tip"],
            "miktar": 0.0, "tutar": 0.0, "hareket_idler": set(),
        })
        g["miktar"] += h["miktar"]
        g["tutar"]  += h["tutar"]
        g["hareket_idler"].add(h["hareket_id"])

    satirlar = []
    toplam = 0.0
    for g in gruplar.values():
        birim_fiyat_ort = g["tutar"] / g["miktar"] if g["miktar"] else 0.0
        satirlar.append({
            "bil_kod":         g["bil_kod"],
            "bil_ad":          g["bil_ad"],
            "tip":             g["tip"],
            "miktar":          g["miktar"],
            "tutar":           g["tutar"],
            "birim_fiyat_ort": birim_fiyat_ort,
            "fatura_sayisi":   len(g["hareket_idler"]),
        })
        toplam += g["tutar"]

    satirlar.sort(key=lambda x: x["bil_kod"])
    return satirlar, toplam


def proje_fark_raporu(
    bom_satirlari: list[dict], satinalma_satirlari: list[dict],
    tolerans: float = 0.01,
) -> list[dict]:
    """
    Teorik BOM satırlarını (mamul_maliyet_hesapla'dan, birden fazla mamül
    seçildiyse önceden bil_kod bazında toplanmış olmalı) fiili satınalma
    satırlarıyla (proje_fiili_maliyet'ten) bil_kod üzerinden birleştirir.

    Sadece ortak kodlar değil, iki tarafın kod kümesinin BİRLEŞİMİ (union)
    üzerinden gidilir — bir tarafta olup diğerinde olmayan kalemler de
    (fazladan satın alınan / BOM'da olup faturası bu projeye işlenmemiş
    kalemler) rapora düşer.

    Not: BOM satırlarındaki "tip" alanı görüntü etiketidir (BİLEŞEN/MASRAF/
    MASRAF (OTO)); satınalma satırlarındaki "tip" ise 'stok'/'masraf'
    kaynak ayrımıdır — burada sadece görüntüleme amaçlı taşınır, eşleştirme
    anahtarı her koşulda bil_kod'dur.

    Her eleman:
      bil_kod, bil_ad, tip,
      bom_miktar, bom_tutar,
      satinalma_miktar, satinalma_tutar,
      fark_miktar, fark_tutar,
      durum: "Sadece Satınalmada" | "Sadece BOM'da" | "Miktar Farkı" | "Eşleşiyor"
    """
    bom_map: dict[str, dict] = {}
    for b in bom_satirlari:
        g = bom_map.setdefault(b["bil_kod"], {
            "bil_ad": b["bil_ad"], "tip": b["tip"], "miktar": 0.0, "tutar": 0.0,
        })
        g["miktar"] += b["bom_miktar"]
        g["tutar"]  += b["satir_top"]

    sat_map = {s["bil_kod"]: s for s in satinalma_satirlari}

    tum_kodlar = set(bom_map) | set(sat_map)
    sonuc = []
    for kod in tum_kodlar:
        b = bom_map.get(kod)
        s = sat_map.get(kod)

        bil_ad     = (b["bil_ad"] if b else None) or (s["bil_ad"] if s else "")
        tip        = (b["tip"] if b else None) or (s["tip"] if s else "")
        bom_miktar = b["miktar"] if b else 0.0
        bom_tutar  = b["tutar"]  if b else 0.0
        sat_miktar = s["miktar"] if s else 0.0
        sat_tutar  = s["tutar"]  if s else 0.0

        fark_miktar = sat_miktar - bom_miktar
        fark_tutar  = sat_tutar  - bom_tutar

        if b is None:
            durum = "Sadece Satınalmada"
        elif s is None:
            durum = "Sadece BOM'da"
        elif abs(fark_miktar) > tolerans:
            durum = "Miktar Farkı"
        else:
            durum = "Eşleşiyor"

        sonuc.append({
            "bil_kod": kod, "bil_ad": bil_ad, "tip": tip,
            "bom_miktar": bom_miktar, "bom_tutar": bom_tutar,
            "satinalma_miktar": sat_miktar, "satinalma_tutar": sat_tutar,
            "fark_miktar": fark_miktar, "fark_tutar": fark_tutar,
            "durum": durum,
        })

    # Görünürlük için önce farklı/eşleşmeyen kalemler, sonra koda göre
    _oncelik = {"Sadece Satınalmada": 0, "Sadece BOM'da": 1, "Miktar Farkı": 2, "Eşleşiyor": 3}
    sonuc.sort(key=lambda x: (_oncelik[x["durum"]], x["bil_kod"]))
    return sonuc
