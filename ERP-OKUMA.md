# CEO ERP Araçları — Birleşik Uygulama

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Son güncelleme:** 2026-06-04 (oturum 3 — SW-ERP-Agent birleştirildi)  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe` (PyInstaller, tek dosya)

## Birleşik Mimari (Oturum 3)

SW-ERP-Agent (sw-erp-agent repo) bu projeye entegre edildi.
Tek PyQt5 uygulaması, 4 sekme:

| Sekme | Kaynak | Durum |
|---|---|---|
| 🔗 Mamül Ağacı | CEO ERP aracı (orijinal) | ✅ |
| 💰 Maliyet | CEO ERP aracı (orijinal) | ✅ |
| ⚙ SW Kodlama | SW-ERP-Agent v3.6 (PyQt5'e taşındı) | ✅ |
| 📦 Stok Kartı Aktar | erp_handler.py (yeni sekme) | ✅ |

### Yeni Klasör Yapısı

```
sw/               ← SW-ERP-Agent modülleri (models, sw_reader, classifier,
                     excel_handler, renamer, vision_handler, erp_handler, pipeline)
ui/tab_sw.py      ← SW Kodlama sekmesi (PyQt5, queue+QTimer mimarisi)
ui/tab_erp_aktar.py ← Stok Kartı Aktar sekmesi
ui/mamul_agaci_tab.py ← Mevcut wizard'ı saran yeni tab widget
ui/ana_pencere.py ← QTabWidget ile yeniden yazıldı
```

---

## Proje Amaçları

### Araç 1 — Mamül Ağacı Bağlantı Aracı
CEO ERP sisteminde **maliyeti olan ama hiçbir mamül ağacına veya reçeteye bağlı olmayan stok kalemleri** tespit edilerek doğru mamül ağacına atanması.

Bu stoklar, ürün maliyet hesabında "boşta görünen maliyet" olarak kalmakta ve ürün bazlı maliyet analizini bozmaktadır.

### Araç 2 — Maliyet Hesaplama
Tüm reçete ve mamül ağaçları taranarak **LIFO, FIFO veya Ağırlıklı Ortalama** yöntemiyle seçilen tarih aralığında ürün bazında maliyet raporu oluşturulması.

İşçilik tutarı mamül bazında manuel girilir. Hesaplama arka planda (`QThread`) çalışır; UI kilitlenmez.

---

## Tespit Mantığı — Araç 1 (İki Filtreli Kesişim)

```
Tüm Stok Kodları
    │
    ├─ FİLTRE 1: Herhangi bir reçetede VEYA mamül ağacında yer ALMAYAN stoklar
    │
    └─ FİLTRE 2: Bu stoklar için en az 1 alış/masraf/hizmet/ithalat faturası girilmiş olanlar
                        │
                        ▼
              KESİŞİM KÜMESİ
              → Ekranda gösterilir, kullanıcı her biri için mamül ağacı seçer
```

---

## Uygulama Akışı

### Ana Menü (Sayfa 0)
İki araç kartı — kullanıcı hangisini kullanacağını seçer.

### Araç 1: ① Bağlantı → ② Tarama → ③ Eşleştirme → ④ Rapor
### Araç 2: Tek sayfa (parametreler + mamül listesi + Excel çıktısı)

---

## Tarih Aralığı Girişi (Her İki Araçta Ortak Kurallar)

| Durum | Davranış |
|---|---|
| `26052025` (8 rakam, noktalarsız) | Otomatik `26.05.2025` olarak tanınır |
| `35.02.2025` (geçersiz gün) | Kutu temizlenir |
| `10.15.2026` (geçersiz ay) | Kutu temizlenir |
| Bugünden sonraki tarih | Kutu temizlenir |
| Başlangıç > Bitiş | Bitiş otomatik başlangıca eşitlenir |
| **Ctrl+N** (bitiş kutusunda) | Bugünün tarihi otomatik gelir |

Kutular **boş açılır** — her iki tarih girilmeden tarama/hesaplama başlamaz.

---

## Dosya Yapısı

```
C:\yeni-erp\
├── main.py              ← Giriş noktası; logging.basicConfig burada başlatılır
├── config.py            ← config.json'dan okur; config_kaydet() ile yazar
├── config.json          ← Yerel DB bilgileri (gitignore'da, repoya gitmez)
├── ceo_erp.log          ← Uygulama log dosyası (gitignore'da)
├── requirements.txt     ← PyQt5, openpyxl, pyodbc
├── ERP-OKUMA.md         ← Bu dosya
│
├── db/
│   ├── demo_data.py     ← Eski demo sabitler (artık kullanılmıyor)
│   ├── baglanti.py      ← get_connection() · cursor_ctx() · baglanti_ctx()
│   └── sorgular.py      ← Veri erişim katmanı; gerçek CEO ERP SQL sorguları
│
├── logic/
│   ├── maliyet.py       ← birim_maliyet() · mamul_maliyet_hesapla() + memoization
│   └── excel.py         ← maliyet_excel_kaydet() · baglama_excel_kaydet()
│
└── ui/
    ├── stil.py          ← STIL sabiti + etiket/buton/ayrac yardımcıları
    ├── ana_menu.py      ← Sayfa 0: Ana menü kartları
    ├── baglanti.py      ← Sayfa 1: DB bağlantı formu + tarih doğrulama
    ├── tarama.py        ← Sayfa 2: Animasyonlu tarama + TaramaThread
    ├── eslestirme.py    ← Sayfa 3: Stok–mamül eşleştirme
    ├── rapor.py         ← Sayfa 4: Özet + Excel kaydet
    ├── maliyet.py       ← Sayfa 5: MaliyetHesaplamaThread + UI kilitleme
    └── ana_pencere.py   ← QMainWindow, sayfa yönetimi, adım çubuğu
```

---

## Yapılan Geliştirmeler (Bu Oturum)

### Loglama Altyapısı
- `main.py`: `logging.basicConfig` yerel import'lardan **önce** çağrılır; tüm modüllerin log'ları `ceo_erp.log`'a düşer
- `db/baglanti.py`: `pyodbc.Error` → `logging.error`, beklenmeyen → `logging.critical`
- Format: `%(asctime)s - %(levelname)s - %(module)s - %(message)s`

### Dinamik Yapılandırma (`config.py` + `config.json`)
- DB bilgileri artık kodda sabit değil; `config.json`'dan okunur
- Dosya yoksa varsayılan şablon otomatik oluşturulur
- Şifre **base64** ile gizlenerek `sifre_enc` alanına yazılır
- Başarılı bağlantı sonrası `config_kaydet()` otomatik çağrılır
- PyInstaller exe'siyle çalışırken `config.json` exe'nin yanında aranır
- `config.json` ve `*.log` `.gitignore`'a eklendi

### Kurumsal DB Bağlantı Yönetimi (`db/baglanti.py`)
| Fonksiyon | Açıklama |
|---|---|
| `get_connection()` | Oturum boyunca tekil singleton bağlantı |
| `cursor_ctx(conn)` | `@contextmanager` — cursor `finally`'de kesinlikle kapatılır |
| `baglanti_ctx(...)` | `@contextmanager` — tek seferlik bağlantı, singleton'ı etkilemez |

`test_baglanti()` artık `baglanti_ctx + cursor_ctx` kullanır — cursor sızıntısı yok.

### Gerçek SQL Sorguları (`db/sorgular.py`)
Demo mod ve tüm `NotImplementedError` stub'ları kaldırıldı. Tüm fonksiyonlar CEO ERP tablolarına (`UretimRecete`, `StokKarti`, `StokHareket`, `StokHareketDetay`) yönelik gerçek SQL çalıştırır.

### Memoization + Çok Seviyeli BOM (`logic/maliyet.py`)
- `_cache: dict` — oturum boyunca paylaşılan RAM önbelleği
  - Anahtar: `("birim", stok_kodu, metod, bas, bit)` veya `("mamul", mamul_kodu, ...)`
  - Paylaşılan alt bileşenler tek sorgulanır (ör. STK-022 dört mamülde geçse bile)
- `_visiting: frozenset` — döngüsel BOM referansına karşı sonsuz özyineleme koruması
- Alt bileşen BOM'da mamül olarak tanımlıysa özyinelemeli hesaplanır
- `excel.py` döngüsünden önce tek `cache = {}` oluşturulur; tüm mamüller paylaşır

### Non-Blocking Hesaplama (`ui/maliyet.py`)
```
MaliyetHesaplamaThread(QThread)
  ├── ilerleme(str) → durum_lbl güncellenir (hangi mamül işleniyor)
  ├── bitti(str)    → başarı diyalogu gösterilir
  ├── hata(str)     → hata diyalogu gösterilir
  └── finished()    → buton restore edilir (QTimer spinner durur)
```
- Widget değerleri thread başlamadan `(kod, iscilik_float)` listesine kopyalanır (thread-safe)
- Hesaplama sırasında buton gri + `⏳ Hesaplanıyor.` / `..` / `...` animasyonu

### Excel Sayı Formatları (`logic/excel.py`)
"Metin olarak saklanan sayı" uyarısı tamamen giderildi:

| Alan | Eski | Yeni |
|---|---|---|
| `bom_miktar` (int) | format uygulanmıyordu | `float` + `#,##0.##` |
| `birim_mal` | `round(4)` float, format yoktu | `float` + `#,##0.0000 "₺"` |
| Boş sayısal hücre | `""` (metin uyarısı) | `None` (boş hücre) |
| `fatura_sayisi` | `str(val)` | `int` + `#,##0` |
| `toplam_tutar` | `"37.500,00 ₺"` (metin) | `_para()` → `float` + `#,##0.00 "₺"` |

Excel'de SUM/TOPLA formülleri çalışır; sıralama/filtreleme sayısal davranır.

---

---

## Sayfa Yapısı (Stack Index)

| Index | Sayfa | Araç |
|---|---|---|
| 0 | Ana Menü | — |
| 1 | Veritabanı Bağlantısı | Araç 1 |
| 2 | Tarama (animasyonlu) | Araç 1 |
| 3 | Eşleştirme | Araç 1 |
| 4 | Rapor + Excel | Araç 1 |
| 5 | Maliyet Hesaplama | Araç 2 |

---

## Excel Raporu Yapıları

### Araç 1 — Mamül Bağlama Raporu
Tek sayfa, otomatik filtreli, ilk satır dondurulmuş.

| Sütun | Tip | Format |
|---|---|---|
| Stok Kodu / Adı | Metin | — |
| Fatura Türleri | Metin | — |
| Fatura Sayısı | **int** | `#,##0` |
| Toplam Tutar | **float** | `#,##0.00 "₺"` |
| İlk / Son Fatura | Metin | — |
| Tedarikçi | Metin | — |
| Mamül Kodu / Adı | Metin | — |
| İşlem | Metin | Bağlandı (yeşil) / Atlandı (sarı) |

### Araç 2 — Maliyet Raporu
Her mamül için 4 satır tipi (renkli):

| Renk | Tip | Sayısal Sütunlar |
|---|---|---|
| Koyu mavi | MAMÜL | Hammadde Toplamı, İşçilik, Genel Toplam → `#,##0.00 "₺"` |
| Açık gri | BİLEŞEN | BOM Miktarı `#,##0.##` · Birim Maliyet `#,##0.0000 "₺"` · Satır Maliyeti `#,##0.00 "₺"` |
| Turuncu | İŞÇİLİK | Satır Maliyeti → `#,##0.00 "₺"` |
| Yeşil | TOPLAM | Hammadde + İşçilik + Genel Toplam → `#,##0.00 "₺"` |

---

## Teknik Yığın

| Bileşen | Teknoloji |
|---|---|
| Dil | Python 3.14 |
| Arayüz | PyQt5 5.15.11 (Fusion teması) |
| Excel çıktı | openpyxl 3.1.5 |
| Veritabanı sürücüsü | pyodbc 5.3.0 |
| Dağıtım | PyInstaller 6.20.0 → `CEO-ERP.exe` ✓ |

---

## Sistem Durumu

| Bileşen | Durum |
|---|---|
| Araç 1 — Mamül Bağlantı | ✅ Çalışıyor (canlı DB) |
| Araç 2 — Maliyet Hesaplama | ✅ Çalışıyor (canlı DB) |
| BOM tüm seviye patlaması | ✅ `UretimReceteHatPlaniGirdi` |
| LIFO / FIFO / Ağırlıklı Ortalama | ✅ |
| KOD:XX operasyon genişletme | ✅ |
| Excel hiyerarşik rapor | ✅ Sayısal formatlar düzgün |
| Demo mod | ✅ Tamamen kaldırıldı |
| Demo butonu (Bağlantı ekranı) | ✅ Kaldırıldı |
| Canlı DB bağlantısı | ✅ `WIN-3FATBI9RQAA\CEO1`, Firma 504 |
| Exe dağıtımı | ✅ `dist/CEO-ERP.exe` ~44 MB |
