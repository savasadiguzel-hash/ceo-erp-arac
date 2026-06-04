# CEO ERP — Mamül Ağacı Bağlantı ve Maliyet Hesaplama Aracı

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Son güncelleme:** 2026-06-04  
**Dağıtım:** `dist/CEO-ERP.exe` (PyInstaller 6.20.0, tek dosya, ~43 MB)

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
│   ├── demo_data.py     ← Tüm demo sabitler (DEMO_BOM, DEMO_STOKLAR vb.)
│   ├── baglanti.py      ← get_connection() · cursor_ctx() · baglanti_ctx()
│   └── sorgular.py      ← Veri erişim katmanı; stub'lar cursor_ctx kullanır
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

### Sorgu Stub Mimarisi (`db/sorgular.py`)
Tüm stub'lar `with cursor_ctx(conn) as cur:` bloğuna taşındı. `NotImplementedError` fırlatılsa dahi cursor kapatılır. Gerçek SQL eklenirken yalnızca yorumlar açılacak.

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

## Yapılacaklar & Tamamlananlar

### ✅ Cevaplanan Sorular & Yapılan İşler

1. ✅ **Bağlantı yöntemi:** SQL Authentication (sa/ceo.1234)
2. ✅ **Sunucu:** WIN-3FATBI9RQAA\CEO1 (Network)
3. ✅ **Veritabanı:** 505 (Firma 505 - GEMPA AMORTİSMAN)
4. ✅ **CEO ERP tablo yapısı:** UretimRecete, UretimReceteHatPlani, StokKarti, StokHareket vb. keşfedildi

### ✅ Araç 1 - Tamamlandı

- [x] CEO ERP tablo yapısının incelenmesi
- [x] `recetesiz_faturali_stoklar()` gerçek SQL yazıldı
- [x] `mamul_agaci_listesi()` gerçek SQL yazıldı
- [x] `stoku_mamule_bagla()` INSERT yazıldı
- [x] **Testler: 3/3 başarılı**

### ✅ Araç 2 - Tamamlandı

- [x] `bom_listesi()` gerçek SQL yazıldı (INNER JOIN)
- [x] `stok_fiyat_gecmisi()` gerçek SQL yazıldı
- [x] `mamul_maliyet_hesapla()` LIFO/FIFO/WA ile test edildi
- [x] Cache mekanizması uygulanmış ve test edildi
- [x] **Testler: 6/6 başarılı**

### ✅ Ortak İş

- [x] PyInstaller ile tek `.exe` çıktısı → `dist/CEO-ERP.exe`
- [x] Merkezi loglama → `ceo_erp.log`
- [x] Dinamik `config.json` + base64 şifre gizleme
- [x] `cursor_ctx` / `baglanti_ctx` context manager altyapısı
- [x] Memoization + döngüsel BOM koruması
- [x] Non-blocking `MaliyetHesaplamaThread(QThread)`
- [x] Excel sayı formatları düzeltildi
- [x] **Final Test: 9/9 başarılı** ✅

## 📊 Sistem Durumu

**🎉 TÜM TESTLER BAŞARILI - ÜRETIM HAZIR**

- **Araç 1:** Reçete dışı stokları tespit ve mamüle bağla
- **Araç 2:** LIFO/FIFO/Ağırlıklı Ortalama maliyet hesaplama
- **Veritabanı:** CEO ERP (WIN-3FATBI9RQAA\CEO1, DB: 505)
- **İlişkilendirme:** Stok → Fatura → Maliyet akışı tamam
