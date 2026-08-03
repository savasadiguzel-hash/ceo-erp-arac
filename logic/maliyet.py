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
from db.sorgular import stok_fiyat_gecmisi, masraf_fiyat_gecmisi, bom_listesi


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
