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
"""
from db.sorgular import stok_fiyat_gecmisi, bom_listesi


def birim_maliyet(
    conn, stok_kodu: str, metod: str, bas: str, bit: str,
    _cache: dict | None = None,
) -> float:
    """
    Stok için seçilen yönteme göre birim maliyet döner.
    metod: 'WA' | 'FIFO' | 'LIFO'
    bas/bit: 'DD.MM.YYYY' formatında tarih aralığı
    Döner: float (birim maliyet)

    Aynı (stok_kodu, metod, bas, bit) için _cache varsa DB'ye gidilmez.
    """
    if _cache is None:
        _cache = {}

    key = ("birim", stok_kodu, metod, bas, bit)
    if key in _cache:
        return _cache[key]

    # stok_fiyat_gecmisi DD.MM.YYYY formatında tarih bekliyor
    fiyatlar = stok_fiyat_gecmisi(conn, stok_kodu, bas, bit)

    if not fiyatlar:
        sonuc = 0.0
    elif metod == "WA":
        # Ağırlıklı Ortalama: (Toplam Tutar) / (Toplam Miktar)
        top_tutar = sum(f["birim_fiyat"] * f["miktar"] for f in fiyatlar)
        top_miktar = sum(f["miktar"] for f in fiyatlar)
        sonuc = top_tutar / top_miktar if top_miktar else 0.0
    elif metod == "FIFO":
        # FIFO: En eski tarihli işlemin birim fiyatı
        sonuc = min(fiyatlar, key=lambda x: x["tarih"])["birim_fiyat"]
    elif metod == "LIFO":
        # LIFO: En yeni tarihli işlemin birim fiyatı
        sonuc = max(fiyatlar, key=lambda x: x["tarih"])["birim_fiyat"]
    else:
        sonuc = 0.0

    _cache[key] = sonuc
    return sonuc


def mamul_maliyet_hesapla(
    conn, mamul_kodu: str, metod: str, bas: str, bit: str,
    _cache: dict | None = None,
    _visiting: frozenset | None = None,
) -> tuple[list[dict], float]:
    """
    Mamül için özyinelemeli bileşen bazında maliyet hesaplar.

    Çok seviyeli BOM desteği: bir bileşen de BOM'da mamül olarak varsa
    maliyeti özyinelemeli hesaplanır ve önbelleklenir.

    _cache   : Dışarıdan geçirilirse birden fazla mamül aynı önbelleği paylaşır.
               None ise bu çağrıya özgü dict oluşturulur.
    _visiting: Döngüsel BOM referanslarına karşı koruma (frozenset, değişmez).

    Döner: tuple[list[dict], float]
           Her koşulda ([], 0.0) veya (satirlar, toplam) biçiminde döner.
           Bileşen satırları: tip, kod, ad, miktar, birim, birim_maliyet, satir_toplam
    """
    if _cache    is None: _cache    = {}
    if _visiting is None: _visiting = frozenset()

    # Döngüsel BOM koruması: ziyaret yığınındaki mamüle tekrar girilmez
    if mamul_kodu in _visiting:
        return [], 0.0

    mamul_key = ("mamul", mamul_kodu, metod, bas, bit)
    if mamul_key in _cache:
        return _cache[mamul_key]

    bom    = bom_listesi(conn)
    mamul  = bom.get(mamul_kodu)
    if not mamul:
        return [], 0.0

    ziyaret_edildi = _visiting | {mamul_kodu}   # frozenset birleşimi — orijinal değişmez

    satirlar: list[dict] = []
    toplam_malzeme = 0.0

    for b in mamul["bilesenleri"]:
        if b["kod"] in bom:
            # Alt bileşen aynı zamanda bir mamül (montaj) → özyinelemeli hesapla
            _, bilesen_maliyeti = mamul_maliyet_hesapla(
                conn, b["kod"], metod, bas, bit, _cache, ziyaret_edildi
            )
        else:
            # Basit stok bileşeni → birim maliyet hesapla
            bilesen_maliyeti = birim_maliyet(conn, b["kod"], metod, bas, bit, _cache)

        satir_maliyet = b["miktar"] * bilesen_maliyeti
        toplam_malzeme += satir_maliyet

        satirlar.append({
            "tip":        "BİLEŞEN",
            "kod":        b["kod"],
            "ad":         b["ad"],
            "bom_miktar": b["miktar"],
            "birim":      b["birim"],
            "birim_mal":  bilesen_maliyeti,
            "satir_top":  satir_maliyet,
        })

    sonuc = (satirlar, toplam_malzeme)
    _cache[mamul_key] = sonuc
    return sonuc
