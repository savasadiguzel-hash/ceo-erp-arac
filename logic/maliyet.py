"""Maliyet hesaplama iş mantığı. UI ve DB'den bağımsızdır."""
from db.sorgular import stok_fiyat_gecmisi, bom_listesi


def birim_maliyet(conn, stok_kodu: str, metod: str, bas: str, bit: str) -> float:
    """
    Stok için seçilen yönteme göre birim maliyet hesaplar.
    metod: 'WA' | 'FIFO' | 'LIFO'
    bas/bit: 'YYYY-MM-DD'
    """
    fiyatlar = stok_fiyat_gecmisi(conn, stok_kodu, bas, bit)
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


def mamul_maliyet_hesapla(
    conn, mamul_kodu: str, metod: str, bas: str, bit: str
) -> tuple[list[dict], float]:
    """
    Mamül için bileşen bazında maliyet hesaplar.
    Döner: (bileşen_satırları, hammadde_toplamı)

    bileşen_satırı anahtarları:
        tip, bil_kod, bil_ad, bom_miktar, birim, birim_mal, satir_top
    """
    bom = bom_listesi(conn)
    mamul = bom.get(mamul_kodu)
    if not mamul:
        return [], 0.0          # ← tutarsızlık düzeltildi (eskiden sadece [] dönüyordu)

    satirlar: list[dict] = []
    toplam = 0.0
    for b in mamul["bilesenleri"]:
        bm = birim_maliyet(conn, b["kod"], metod, bas, bit)
        satir_top = b["miktar"] * bm
        toplam += satir_top
        satirlar.append({
            "tip":        "BİLEŞEN",
            "bil_kod":    b["kod"],
            "bil_ad":     b["ad"],
            "bom_miktar": b["miktar"],
            "birim":      b["birim"],
            "birim_mal":  bm,
            "satir_top":  satir_top,
        })
    return satirlar, toplam
