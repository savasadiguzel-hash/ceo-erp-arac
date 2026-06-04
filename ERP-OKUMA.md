# CEO ERP — Mamül Ağacı Bağlantı ve Maliyet Hesaplama Aracı

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Son güncelleme:** 2026-06-04  
**Dağıtım:** `dist/CEO-ERP.exe` + `dist/config.json` (PyInstaller 6.20.0, ~44 MB)

---

## Kurulum

1. `dist/CEO-ERP.exe` ve `dist/config.json` dosyalarını aynı klasöre koy
2. `config.json` içindeki bağlantı bilgilerini düzenle:

```json
{
  "sunucu": "WIN-3FATBI9RQAA\\CEO1",
  "veritabani": "504",
  "kullanici": "sa",
  "sifre_enc": "Y2VvLjEyMzQ="
}
```

> `sifre_enc` değeri base64 ile kodlanmıştır. `ceo.1234` → `Y2VvLjEyMzQ=`

---

## Proje Amaçları

### Araç 1 — Mamül Ağacı Bağlantı Aracı
Maliyeti olan ama hiçbir reçeteye bağlı olmayan stok kalemlerini tespit ederek doğru mamüle atar.

### Araç 2 — Maliyet Hesaplama
Reçete ağacı en alt hammaddeye kadar patlatılarak **LIFO, FIFO veya Ağırlıklı Ortalama** yöntemiyle maliyet raporu üretir. İşçilik manuel girilir.

---

## CEO ERP Veritabanı Tablo Yapısı

### BOM (Reçete) Hiyerarşisi

```
UretimRecete              ← Reçete başlığı (mamül kodu, adı)
  └── UretimReceteHatPlani    ← Operasyon/montaj adımı satırı
        └── UretimReceteHatPlaniGirdi  ← GERÇEK girdiler (hammadde, parça)
```

> **Kritik:** Gerçek bileşenler `UretimReceteHatPlaniGirdi` tablosundadır.
> `UretimReceteHatPlani` sadece operasyon başlığıdır.

### Diğer Önemli Tablolar

| Tablo | Kullanım |
|---|---|
| `StokKarti` | Stok kodu, adı, aktif durumu |
| `StokHareket` | Fatura başlığı (tarih, belge no) |
| `StokHareketDetay` | Fatura satırı (birim fiyat, miktar) — `IslemKartId` → `StokKarti.Id` |
| `UretimReceteHatPlani` | Tipi=1: çıktı mamülün kendisi; Tipi=2: bazı eski reçetelerde bileşen |

---

## BOM Patlatma Mantığı (Araç 2)

```
bom_listesi(conn)
  ├── 1. Sorgu: UretimReceteHatPlaniGirdi → gerçek reçete girdileri
  │
  └── 2. Sorgu: StokKarti KOD:XX eşleşmesi → operasyon adımları
        CEO ERP'de imalat operasyonları ayrı stok kodu olarak tutulur:
        GMP-200-230602:20  (FREZE)
        GMP-200-230602:60  (KAPLAMA)
        GMP-200-230602:100 (LAZER KAZIMA)
        Gerçek reçetesi olmayan stoklar için bu :XX kodlar
        otomatik alt bileşen olarak eklenir.

mamul_tum_satirlar()
  ├── Bileşen BOM'da mamül olarak tanımlıysa → ALT-MAMÜL (özyinelemeli)
  │     └── miktarlar üst seviyeyle çarpılarak taşınır
  │
  └── Bileşen yaprak ise → birim_maliyet() → stok_fiyat_gecmisi()
        └── LIFO / FIFO / WA
```

**Örnek — GMP-101-230014 BORESIGHTER SP:**
```
MAMÜL: GMP-101-230014
  BİLEŞEN: OPTICAL RETICLE
  ALT-MAMÜL: GMP-200-230602  (GÖVDE)
    BİLEŞEN:  GMP-200-230602:20   FREZE
    BİLEŞEN:  GMP-200-230602:60   KAPLAMA
    BİLEŞEN:  GMP-200-230602:100  LAZER KAZIMA
    BİLEŞEN:  GMP-200-230602:110  ÇAPAK ALMA
  BİLEŞEN: LENS, VİDA, O-RING...
TOPLAM
```

---

## Dosya Yapısı

```
C:\yeni-erp\
├── main.py              ← Giriş noktası
├── config.py            ← config.json okur; config_kaydet() ile yazar
├── config.json          ← Yerel DB bilgileri (gitignore — repoya gitmez)
├── ceo_erp.log          ← Log dosyası (gitignore)
├── requirements.txt
├── ERP-OKUMA.md
│
├── db/
│   ├── baglanti.py      ← get_connection() · cursor_ctx() · baglanti_ctx()
│   └── sorgular.py      ← mamul_agaci_listesi · recetesiz_faturali_stoklar
│                           bom_listesi · stok_fiyat_gecmisi · stoku_mamule_bagla
│
├── logic/
│   ├── maliyet.py       ← birim_maliyet() · mamul_maliyet_hesapla()
│   │                       mamul_tum_satirlar()  ← tam BOM patlaması
│   └── excel.py         ← maliyet_excel_kaydet() · baglama_excel_kaydet()
│
└── ui/
    ├── stil.py
    ├── ana_menu.py      ← Sayfa 0
    ├── baglanti.py      ← Sayfa 1: DB bağlantı formu
    ├── tarama.py        ← Sayfa 2: TaramaThread
    ├── eslestirme.py    ← Sayfa 3
    ├── rapor.py         ← Sayfa 4
    ├── maliyet.py       ← Sayfa 5: MaliyetHesaplamaThread
    └── ana_pencere.py   ← QMainWindow, sayfa yönetimi
```

---

## Excel Raporu — Araç 2 (Maliyet)

Her mamül için satır tipleri:

| Renk | Tip | İçerik |
|---|---|---|
| Koyu mavi | **MAMÜL** | Hammadde toplamı · İşçilik · Genel toplam |
| Orta mavi | **ALT-MAMÜL** | Ara montaj başlığı (özyinelemeli açılır) |
| Açık gri | **BİLEŞEN** | Hammadde/parça — birim maliyet · satır maliyeti |
| Turuncu | **İŞÇİLİK** | Manuel girilen işçilik tutarı |
| Yeşil | **TOPLAM** | Hammadde + işçilik özeti |

**Sütunlar:** Tip · Seviye · Mamül Kodu · Mamül Adı · Bileşen Kodu · Bileşen Adı · BOM Miktarı · Birim · Birim Maliyet · Satır Maliyeti · Hammadde Toplamı · İşçilik · Genel Toplam

---

## Teknik Yığın

| Bileşen | Teknoloji |
|---|---|
| Dil | Python 3.14 |
| Arayüz | PyQt5 5.15.11 (Fusion teması) |
| Excel çıktı | openpyxl 3.1.5 |
| Veritabanı sürücüsü | pyodbc 5.3.0 |
| Dağıtım | PyInstaller 6.20.0 → `CEO-ERP.exe` |
| Veritabanı | SQL Server (WIN-3FATBI9RQAA\CEO1, Firma 504) |

---

## Sistem Durumu

| Bileşen | Durum |
|---|---|
| Araç 1 — Mamül Bağlantı | ✅ Çalışıyor |
| Araç 2 — Maliyet Hesaplama | ✅ Çalışıyor |
| BOM Patlaması (tüm seviyeler) | ✅ UretimReceteHatPlaniGirdi |
| LIFO / FIFO / Ağırlıklı Ortalama | ✅ Çalışıyor |
| Excel hiyerarşik rapor | ✅ Seviye + girinti |
| Demo mod | ✅ Kaldırıldı — sadece canlı DB |
| Exe dağıtımı | ✅ dist/CEO-ERP.exe (~44 MB) |
