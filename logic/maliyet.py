"""
Maliyet hesaplama iş mantığı. UI ve DB'den bağımsızdır.

Fonksiyonlar
------------
birim_maliyet()         : Tek stok için WA/FIFO/LIFO birim fiyat (önbellekli)
mamul_maliyet_hesapla() : Maliyet toplamı hesabı (önbellekli, iç kullanım)
mamul_tum_satirlar()    : Excel için tam BOM patlaması — tüm seviyeler dahil
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


def mamul_tum_satirlar(
    conn, mamul_kodu: str, metod: str, bas: str, bit: str,
    bom: dict,
    _cache: dict | None = None,
    _visiting: frozenset | None = None,
    _seviye: int = 1,
) -> tuple[list[dict], float]:
    """
    Excel için tam BOM patlaması — tüm seviyeler açılır.

    Alt-mamüller de BOM'da tanımlıysa onların bileşenleri de eklenir.
    Miktarlar BOM ağacı boyunca çarpılarak taşınır (örn. 2 adet A × 3 adet B = 6 adet B).

    Döner: (satirlar, birim_toplam)
      - satirlar : tip='ALT-MAMÜL' veya 'BİLEŞEN', seviye bilgisi dahil
      - birim_toplam: bu mamülün 1 biriminin toplam malzeme maliyeti
    """
    if _cache   is None: _cache   = {}
    if _visiting is None: _visiting = frozenset()

    if mamul_kodu in _visiting:
        return [], 0.0

    mamul = bom.get(mamul_kodu)
    if not mamul:
        return [], 0.0

    ziyaret = _visiting | {mamul_kodu}
    satirlar: list[dict] = []
    toplam = 0.0

    for b in mamul["bilesenleri"]:
        if b["kod"] in bom and b["kod"] not in ziyaret:
            # Alt-mamül: önce kendi birim maliyetini bul, sonra bileşenlerini aç
            alt_s, alt_birim = mamul_tum_satirlar(
                conn, b["kod"], metod, bas, bit, bom, _cache, ziyaret, _seviye + 1
            )
            satir_maliyet = b["miktar"] * alt_birim

            # Alt-mamül başlık satırı
            satirlar.append({
                "tip":        "ALT-MAMÜL",
                "kod":        b["kod"],
                "ad":         b["ad"],
                "bom_miktar": b["miktar"],
                "birim":      b["birim"],
                "birim_mal":  alt_birim,
                "satir_top":  satir_maliyet,
                "seviye":     _seviye,
            })
            # Alt-mamülün bileşenlerini miktarla ölçekleyerek ekle
            for alt in alt_s:
                satirlar.append({
                    **alt,
                    "bom_miktar": alt["bom_miktar"] * b["miktar"],
                    "satir_top":  alt["satir_top"]  * b["miktar"],
                })
            toplam += satir_maliyet
        else:
            # Yaprak bileşen: doğrudan fiyat sorgula
            bm = birim_maliyet(conn, b["kod"], metod, bas, bit, _cache)
            satir_maliyet = b["miktar"] * bm
            satirlar.append({
                "tip":        "BİLEŞEN",
                "kod":        b["kod"],
                "ad":         b["ad"],
                "bom_miktar": b["miktar"],
                "birim":      b["birim"],
                "birim_mal":  bm,
                "satir_top":  satir_maliyet,
                "seviye":     _seviye,
            })
            toplam += satir_maliyet

    return satirlar, toplam
