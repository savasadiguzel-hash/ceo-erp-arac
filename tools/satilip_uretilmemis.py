#!/usr/bin/env python3
"""
tools/satilip_uretilmemis.py
Satılıp henüz üretilmemiş ürünler raporu.

2026 (veya verilen tarih aralığında) satış faturası/irsaliyesi kesilmiş ama
güncel ERP bakiyesi negatif olan (yani üretimin satışı karşılayamadığı)
mamul/yarımamül kodlarını Excel'e döker.

Kullanım:
    python tools/satilip_uretilmemis.py
    python tools/satilip_uretilmemis.py --bas 01.01.2026 --bit 31.12.2026
    python tools/satilip_uretilmemis.py --dosya rapor.xlsx

Kapsam ve tanımlar
-------------------
- "Ürün" = `db.sorgular.mamul_agaci_listesi()`'nin döndürdüğü küme: reçetesi
  tanımlı (UretimReceteHatPlani.KartId'de karşılığı olan) aktif StokKarti'ler.
  Hammadde/bileşen satışları bu rapora girmez.
- "Satıldı" = `db.sorgular.satis_faturalari()` — IslemKodu 2 (Satış Faturası)
  + FaturaId'si boş IslemKodu 6 (henüz faturalaşmamış Satış İrsaliyesi).
  Faturalaşan irsaliyelerin mükerrer sayılmaması için zaten düzeltilmiş bir
  fonksiyon (bkz. ERP-OKUMA.md).
- "Üretilmedi" = CEO ERP'de bu kod için ayrı bir "üretim emri -> üretilen
  miktar" bağlantısı sorgulanabilir değil (kod tabanında böyle bir JOIN yok).
  Bunun yerine mevcut bakiye formülü kullanılır: `stok_guncel_bakiyeleri()`
  IslemKodu=16 (Üretimden Giriş) dahil TÜM giriş/çıkış hareketlerini netler;
  bir mamul kodun bugünkü ERP bakiyesi negatifse, bu satışın üretim +
  mevcut stokla karşılanamadığı anlamına gelir — Üretim Eksik Stok
  sekmesindeki "eksik" mantığıyla birebir aynı.
- Rapora yalnızca bakiyesi negatif olan (gerçekten eksik) ürünler girer;
  stoktan karşılanmış satışlar listelenmez.

Bu araç hiçbir mevcut sorgu fonksiyonunu değiştirmez (satis_faturalari,
stok_guncel_bakiyeleri, mamul_agaci_listesi olduğu gibi kullanılır) — bakiye/
depo mantığına dokunmaz, bu yüzden tools/mutabakat.py'ye ihtiyaç duymaz.
"""
import argparse
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

_BUGUN = date.today().strftime("%d.%m.%Y")


def _parse_tarih(metin: str) -> str:
    """'DD.MM.YYYY' doğrular, aynı formatta döner."""
    try:
        datetime.strptime(metin, "%d.%m.%Y")
    except ValueError:
        sys.exit(f"Geçersiz tarih: {metin!r} (beklenen format: GG.AA.YYYY)")
    return metin


def _grupla(satislar: list[dict], mamul_kodlari: set[str]) -> dict[str, dict]:
    """
    Satış satırlarını mamul kod kümesine filtreler, stok_kodu bazında gruplar.
    satis_faturalari() sonucu `sh.BelgeTarihi ASC` sıralı geldiği için, aynı
    kod için ilk görülen satır en erken tarih, son görülen satır en geç tarihtir.
    Döner: {stok_kodu: {stok_adi, miktar, tutar, ilk_tarih, son_tarih, belgeler}}
    """
    gruplar: dict[str, dict] = {}
    for s in satislar:
        kod = s["stok_kodu"]
        if kod not in mamul_kodlari:
            continue
        if kod not in gruplar:
            gruplar[kod] = {
                "stok_adi":  s["stok_adi"],
                "miktar":    0.0,
                "tutar":     0.0,
                "ilk_tarih": s["tarih"],
                "son_tarih": s["tarih"],
                "belgeler":  set(),
            }
        g = gruplar[kod]
        g["miktar"] += s["miktar"]
        g["tutar"]  += s["tutar"]
        g["son_tarih"] = s["tarih"]
        g["belgeler"].add((s["islem_turu"], s["belge_no"]))
    return gruplar


def _hesapla_maliyet(kod: str, bom: dict, fiyatlar: dict,
                      _visiting: frozenset = frozenset()) -> tuple[float | None, bool]:
    """
    Bir kod için (fiyat, hesaplandi_mi) döner:
    - `fiyatlar` ({kod: birim_fiyat} — son_alis_fiyati_toplu sonucundan
      düzleştirilmiş) içinde doğrudan bir alım fiyatı varsa onu döner —
      hesaplandi_mi=False (gerçek alım fiyatı).
    - Yoksa ve kod reçeteli ise (`bom`'da bir kayıt varsa — ör. yarı mamül
      GMP-200-240506 gibi CEO ERP'de hiç satın alınmayıp sadece üretilen bir
      parça): kendi bileşenlerinin (miktar × bileşen fiyatı) toplamını
      özyinelemeli hesaplar — hesaplandi_mi=True. Fiyatı hiç bulunamayan
      alt bileşenler 0 katkı yapar — bu, Maliyet sekmesindeki
      `mamul_maliyet_hesapla()` ile aynı, zaten dokümante edilmiş davranış
      ("Sıfır maliyetli bileşen = veri boşluğu").
    - Ne doğrudan fiyat ne reçete varsa (gerçekten hiç veri yok) (None, False)
      döner — hücre boş bırakılır.
    - Döngüsel BOM referanslarına karşı `_visiting` korumalı.
    """
    if kod in _visiting:
        return None, False
    if kod in fiyatlar:
        return fiyatlar[kod], False
    if kod not in bom:
        return None, False

    toplam = 0.0
    herhangi_bulundu = False
    for bil in bom[kod]["bilesenleri"]:
        alt_fiyat, _ = _hesapla_maliyet(bil["kod"], bom, fiyatlar, _visiting | {kod})
        if alt_fiyat is not None:
            toplam += bil["miktar"] * alt_fiyat
            herhangi_bulundu = True

    return (toplam, True) if herhangi_bulundu else (None, False)
    return gruplar


def rapor_olustur(conn, bas: str, bit: str) -> list[dict]:
    """
    Döner: eksik > 0 olan ürünler, eksik miktara göre azalan sıralı.
    Her eleman: stok_kodu, stok_adi, satilan_miktar, satis_tutari,
                bakiye, eksik, ilk_tarih, son_tarih, belge_sayisi
    """
    from db.sorgular import mamul_agaci_listesi, satis_faturalari, stok_guncel_bakiyeleri

    mamuller = mamul_agaci_listesi(conn)
    mamul_kodlari = {kod for kod, _ in mamuller}
    print(f"Reçeteli (bizim ürettiğimiz) ürün sayısı: {len(mamul_kodlari)}")

    satislar = satis_faturalari(conn, bas, bit)
    print(f"{bas} — {bit} arası satış satırı: {len(satislar)}")

    gruplar = _grupla(satislar, mamul_kodlari)
    print(f"Bu aralıkta satılan ürün (mamul) kodu: {len(gruplar)}")

    if not gruplar:
        return []

    bakiyeler = stok_guncel_bakiyeleri(conn, list(gruplar.keys()))

    sonuc = []
    for kod, g in gruplar.items():
        bakiye = bakiyeler.get(kod, 0.0)
        if bakiye >= 0:
            continue
        eksik = -bakiye
        sonuc.append({
            "stok_kodu":      kod,
            "stok_adi":       g["stok_adi"],
            "satilan_miktar": round(g["miktar"], 2),
            "satis_tutari":   round(g["tutar"], 2),
            "bakiye":         round(bakiye, 2),
            "eksik":          round(eksik, 2),
            "ilk_tarih":      g["ilk_tarih"],
            "son_tarih":      g["son_tarih"],
            "belge_sayisi":   len(g["belgeler"]),
        })

    sonuc.sort(key=lambda r: r["eksik"], reverse=True)
    return sonuc


def _alt_parca_sayfasi_yaz(
    wb,
    alt_parcalar: list[dict],
    acik_uretim_ihtiyaclari: dict[str, float],
) -> None:
    """
    "Alt Parça İhtiyacı" sayfası — satılıp üretilmemiş ürünlerin eksik
    miktarları reçete/bom_listesi() ile en alt kademeye kadar patlatılmış
    hâli (db.sorgular.ihtiyac_bom_patlat). Stok satırları (eksik > 0) üstte,
    masraf/operasyon satırları (bakiye kavramı yok) altta bilgi amaçlı.
    """
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    ws = wb.create_sheet("Alt Parça İhtiyacı")
    basliklar = [
        "Stok Kodu", "Stok Adı", "Tip",
        "Toplam İhtiyaç Miktarı", "Güncel ERP Bakiyesi", "Eksik Miktar",
        "Son Alım Fiyatı (₺)", "Son Alım Tarihi",
        "Açık Üretim Emri İhtiyacı", "Hangi Ürün(ler) İçin",
    ]
    ws.append(basliklar)
    hrow = ws.max_row
    for cell in ws[hrow]:
        cell.fill      = PatternFill("solid", fgColor="4A148C")
        cell.font      = Font(name="Segoe UI", bold=True, color="FFFFFF", size=11)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[hrow].height = 26

    eksik_font    = Font(name="Segoe UI", size=11, color="C62828", bold=True)
    normal_font   = Font(name="Segoe UI", size=11)
    masraf_font   = Font(name="Segoe UI", size=11, italic=True, color="757575")
    hesaplanan_font = Font(name="Segoe UI", size=11, italic=True, color="1565C0")
    ince_alt      = Border(bottom=Side(style="thin", color="E0E0E0"))

    for r_ in alt_parcalar:
        masraf = r_["tip"] == "masraf"
        son = r_.get("son_fiyat")   # {'fiyat', 'tarih', 'hesaplanan'} veya None (hiç alım/veri yok)
        hesaplanan = bool(son and son.get("hesaplanan"))
        tarih_hucre = "Hesaplanan (alt bileşenlerden)" if hesaplanan else (son["tarih"] if son else None)
        ws.append([
            r_["kodu"], r_["adi"], "Masraf/Operasyon" if masraf else "Stok",
            r_["toplam_ihtiyac"],
            "—" if masraf else r_["bakiye"],
            "—" if masraf else r_["eksik"],
            son["fiyat"] if son else None,
            tarih_hucre,
            None if masraf else acik_uretim_ihtiyaclari.get(r_["kodu"], 0.0),
            ", ".join(r_["kaynaklar"]),
        ])
        r = ws.max_row
        for c in (4, 5, 6, 7, 9):
            ws.cell(row=r, column=c).alignment = Alignment(horizontal="right")
        font = masraf_font if masraf else normal_font
        for c in range(1, 11):
            ws.cell(row=r, column=c).font = font
            ws.cell(row=r, column=c).border = ince_alt
        if not masraf:
            ws.cell(row=r, column=6).font = eksik_font
        if son:
            ws.cell(row=r, column=7).number_format = '#,##0.00'
        if hesaplanan:
            ws.cell(row=r, column=7).font = hesaplanan_font
            ws.cell(row=r, column=8).font = hesaplanan_font

    for col, w in zip("ABCDEFGHIJ", [22, 42, 16, 18, 16, 14, 16, 16, 22, 40]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = f"A{hrow + 1}"
    ws.auto_filter.ref = f"A{hrow}:J{ws.max_row}"


def excel_yaz(satirlar: list[dict], dosya: Path, bas: str, bit: str,
              alt_parcalar: list[dict] | None = None,
              acik_uretim_ihtiyaclari: dict[str, float] | None = None) -> None:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Üretilmesi Gereken"

    basliklar = [
        "Stok Kodu", "Stok Adı",
        f"Satılan Miktar\n({bas} — {bit})", "Satış Tutarı (₺)",
        "Güncel ERP Bakiyesi", "Üretilmesi Gereken Miktar",
        "İlk Satış Tarihi", "Son Satış Tarihi", "Belge Sayısı",
    ]
    ws.append(basliklar)
    hrow = ws.max_row
    for cell in ws[hrow]:
        cell.fill      = PatternFill("solid", fgColor="1A237E")
        cell.font      = Font(name="Segoe UI", bold=True, color="FFFFFF", size=11)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[hrow].height = 30

    eksik_font  = Font(name="Segoe UI", size=11, color="C62828", bold=True)
    normal_font = Font(name="Segoe UI", size=11)
    ince_alt    = Border(bottom=Side(style="thin", color="E0E0E0"))

    for s in satirlar:
        ws.append([
            s["stok_kodu"], s["stok_adi"],
            s["satilan_miktar"], s["satis_tutari"],
            s["bakiye"], s["eksik"],
            s["ilk_tarih"], s["son_tarih"], s["belge_sayisi"],
        ])
        r = ws.max_row
        for c in range(3, 7):
            ws.cell(row=r, column=c).alignment = Alignment(horizontal="right")
            ws.cell(row=r, column=c).font = normal_font
        ws.cell(row=r, column=5).font = eksik_font   # bakiye (negatif)
        ws.cell(row=r, column=6).font = eksik_font   # eksik (üretilmesi gereken)
        for c in range(1, 10):
            ws.cell(row=r, column=c).border = ince_alt

    toplam_satir = len(satirlar) + 2
    toplam_eksik  = sum(s["eksik"] for s in satirlar)
    toplam_tutar  = sum(s["satis_tutari"] for s in satirlar)
    fill_toplam = PatternFill("solid", fgColor="E8F5E9")
    font_toplam = Font(name="Segoe UI", size=11, bold=True, color="1B5E20")
    for c in range(1, 10):
        cell = ws.cell(row=toplam_satir, column=c)
        cell.fill = fill_toplam
        cell.font = font_toplam
    ws.cell(row=toplam_satir, column=1, value=f"TOPLAM  ({len(satirlar)} ürün)")
    ws.cell(row=toplam_satir, column=4, value=round(toplam_tutar, 2)).alignment = Alignment(horizontal="right")
    ws.cell(row=toplam_satir, column=6, value=round(toplam_eksik, 2)).alignment = Alignment(horizontal="right")

    for col, w in zip("ABCDEFGHI", [22, 45, 16, 16, 16, 20, 16, 16, 12]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = f"A{hrow + 1}"
    ws.auto_filter.ref = f"A{hrow}:I{ws.max_row - 1}"

    if alt_parcalar:
        _alt_parca_sayfasi_yaz(
            wb,
            alt_parcalar,
            acik_uretim_ihtiyaclari or {},
        )

    wb.save(dosya)


def main():
    p = argparse.ArgumentParser(description="Satılıp henüz üretilmemiş ürünler raporu")
    p.add_argument("--bas", default="01.01.2026", help="Başlangıç tarihi (GG.AA.YYYY, varsayılan: 01.01.2026)")
    p.add_argument("--bit", default=_BUGUN, help="Bitiş tarihi (GG.AA.YYYY, varsayılan: bugün)")
    p.add_argument("--dosya", type=Path, default=None, help="Çıktı Excel dosyası")
    args = p.parse_args()

    bas = _parse_tarih(args.bas)
    bit = _parse_tarih(args.bit)
    dosya = args.dosya or BASE / f"satilip_uretilmemis_{date.today().strftime('%Y%m%d')}.xlsx"

    from config import DB_DEFAULTS
    from db.baglanti import get_connection

    print(f"Bağlanılıyor: {DB_DEFAULTS.get('sunucu')} / {DB_DEFAULTS.get('veritabani')}")
    try:
        conn = get_connection(**DB_DEFAULTS)
    except Exception as e:
        sys.exit(f"DB bağlantısı kurulamadı: {e}")

    satirlar = rapor_olustur(conn, bas, bit)

    if not satirlar:
        print("\nSatılıp da üretilmemiş (bakiyesi negatif) ürün bulunamadı.")
        return

    from db.sorgular import (
        ihtiyac_bom_patlat,
        son_alis_fiyati_toplu,
        acik_uretim_emri_ihtiyaclari,
        bom_listesi,
    )

    bom = bom_listesi(conn)   # ihtiyac_bom_patlat() ile paylaşılır (tekrar DB'ye gidilmez)
    ihtiyaclar = {s["stok_kodu"]: s["eksik"] for s in satirlar}
    alt_parcalar = ihtiyac_bom_patlat(conn, ihtiyaclar, bom=bom)

    # Fiyat sorgusu için, alt_parcalar'daki kodların yanı sıra — reçeteli
    # (bom'da) olanların KENDİ bileşenlerini de (eksik olmasalar bile) topla;
    # aksi hâlde yarı mamüllerin maliyet toplamı eksik veriyle hesaplanır.
    def _tum_bilesen_kodlari(kod: str, gorulen: set) -> None:
        if kod in gorulen:
            return
        gorulen.add(kod)
        for bil in bom.get(kod, {}).get("bilesenleri", []):
            _tum_bilesen_kodlari(bil["kod"], gorulen)

    tum_kodlar: set[str] = set()
    for a in alt_parcalar:
        _tum_bilesen_kodlari(a["kodu"], tum_kodlar)

    masraf_kodlari = [k for k in tum_kodlar if k.count(":") == 1]
    stok_kodlari   = [k for k in tum_kodlar if k.count(":") != 1]
    son_fiyatlar = son_alis_fiyati_toplu(conn, stok_kodlari, masraf_kodlari)
    fiyat_map = {k: v["fiyat"] for k, v in son_fiyatlar.items()}

    for a in alt_parcalar:
        dogrudan = son_fiyatlar.get(a["kodu"])
        if dogrudan:
            a["son_fiyat"] = {**dogrudan, "hesaplanan": False}
            continue
        hesaplanan, bulundu = _hesapla_maliyet(a["kodu"], bom, fiyat_map)
        a["son_fiyat"] = {"fiyat": hesaplanan, "tarih": None, "hesaplanan": True} if bulundu else None

    alt_stok_kodlari = [a["kodu"] for a in alt_parcalar if a["tip"] == "stok"]
    acik_uretim_ihtiyaclari = acik_uretim_emri_ihtiyaclari(conn, alt_stok_kodlari)

    excel_yaz(
        satirlar,
        dosya,
        bas,
        bit,
        alt_parcalar,
        acik_uretim_ihtiyaclari,
    )

    toplam_eksik = sum(s["eksik"] for s in satirlar)
    toplam_tutar = sum(s["satis_tutari"] for s in satirlar)
    print(f"\nUYARI: {len(satirlar)} ürünün üretimi satışın gerisinde kaldı.")
    print(f"   Toplam eksik miktar : {toplam_eksik:,.2f}")
    print(f"   Etkilenen satış tutarı: {toplam_tutar:,.2f} TL")
    print(f"\nEn acil 10 ürün:")
    for s in satirlar[:10]:
        print(f"  {s['stok_kodu']:<22} {s['stok_adi'][:35]:<35} "
              f"eksik={s['eksik']:>10,.2f}  bakiye={s['bakiye']:>10,.2f}")

    stok_eksik = [a for a in alt_parcalar if a["tip"] == "stok"]
    masraf_kalem = [a for a in alt_parcalar if a["tip"] == "masraf"]
    print(f"\nAlt parça patlatması: {len(stok_eksik)} stok kodu eksik, "
          f"{len(masraf_kalem)} masraf/operasyon kalemi (bilgi amaçlı).")
    if stok_eksik:
        print("En acil 10 alt parça:")
        for a in stok_eksik[:10]:
            print(f"  {a['kodu']:<22} {a['adi'][:35]:<35} "
                  f"eksik={a['eksik']:>10,.2f}  ({', '.join(a['kaynaklar'][:3])})")

    print(f"\nExcel kaydedildi: {dosya}")


if __name__ == "__main__":
    main()
