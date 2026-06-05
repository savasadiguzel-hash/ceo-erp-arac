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
from db.sorgular import stok_fiyat_gecmisi, bom_listesi


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

    fiyatlar = stok_fiyat_gecmisi(conn, stok_kodu, bas, bit)
    filtreli  = [f for f in fiyatlar if bas <= f["tarih"] <= bit]

    if not filtreli:
        sonuc = 0.0
    elif metod == "WA":
        top_t = sum(f["birim_fiyat"] * f["miktar"] for f in filtreli)
        top_m = sum(f["miktar"] for f in filtreli)
        sonuc = top_t / top_m if top_m else 0.0
    elif metod == "FIFO":
        sonuc = min(filtreli, key=lambda x: x["tarih"])["birim_fiyat"]
    elif metod == "LIFO":
        sonuc = max(filtreli, key=lambda x: x["tarih"])["birim_fiyat"]
    else:
        sonuc = 0.0

    _cache[key] = sonuc
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
        if b["kod"] in bom:
            # Alt bileşen aynı zamanda bir mamül → özyinelemeli hesapla
            _, bm = mamul_maliyet_hesapla(
                conn, b["kod"], metod, bas, bit, _cache, ziyaret_edildi, bom
            )
        else:
            bm = birim_maliyet(conn, b["kod"], metod, bas, bit, _cache)

        satir_top = b["miktar"] * bm
        toplam   += satir_top
        satirlar.append({
            "tip":        "BİLEŞEN",
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
