# CEO ERP — Mamül Ağacı Bağlantı ve Maliyet Hesaplama Aracı

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Son güncelleme:** 2026-06-03  
**Dağıtım:** `dist/CEO-ERP.exe` (PyInstaller, tek dosya, ~43 MB)

---

## Proje Amaçları

### Araç 1 — Mamül Ağacı Bağlantı Aracı
CEO ERP sisteminde **maliyeti olan ama hiçbir mamül ağacına veya reçeteye bağlı olmayan stok kalemleri** tespit edilerek doğru mamül ağacına atanması.

Bu stoklar, ürün maliyet hesabında "boşta görünen maliyet" olarak kalmakta ve ürün bazlı maliyet analizini bozmaktadır.

### Araç 2 — Maliyet Hesaplama
Tüm reçete ve mamül ağaçları taranarak **LIFO, FIFO veya Ağırlıklı Ortalama** yöntemiyle seçilen tarih aralığında ürün bazında maliyet raporu oluşturulması.

Tüm işler dışarıya yaptırıldığından (montaj hariç) tüm faturalar toplanarak doğru bir ürün maliyeti elde edilebilir. İşçilik tutarı mamül bazında manuel girilir.

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

**Neden kesişim?**
- Sadece reçetesiz stok: faturası yoksa maliyeti sıfır → sorun değil
- Sadece faturası olan stok: reçetedeyse zaten doğru yerde
- İkisi birden → gerçek "boşta maliyet" = düzeltilmesi gereken kayıt

---

## Uygulama Akışı

### Ana Menü (Sayfa 0)
İki araç kartı — kullanıcı hangisini kullanacağını seçer.

### Araç 1: ① Bağlantı → ② Tarama → ③ Eşleştirme → ④ Rapor
### Araç 2: Tek sayfa (parametreler + mamül listesi + Excel çıktısı)

---

## Tarih Aralığı Girişi (Her İki Araçta Ortak Kurallar)

Her iki araçtaki tarih kutucukları aynı kurallara göre çalışır:

| Durum | Davranış |
|---|---|
| `26052025` (8 rakam, noktalarsız) | Otomatik `26.05.2025` olarak tanınır |
| `35.02.2025` (geçersiz gün) | Kutu temizlenir |
| `10.15.2026` (geçersiz ay) | Kutu temizlenir |
| Bugünden sonraki tarih | Kutu temizlenir |
| Başlangıç > Bitiş | Bitiş otomatik başlangıca eşitlenir |
| Bitiş < Başlangıç | Bitiş otomatik başlangıca eşitlenir |
| **Ctrl+N** (bitiş kutusunda) | Bugünün tarihi otomatik gelir |

Kutular **boş açılır** — her iki tarih girilmeden tarama/hesaplama başlamaz.

---

## Dosya Yapısı (Refactor Sonrası)

```
C:\yeni-erp\
├── main.py              ← Giriş noktası (7 satır)
├── config.py            ← USE_DEMO bayrağı + DB varsayılanları
├── requirements.txt     ← PyQt5, openpyxl, pyodbc
├── ERP-OKUMA.md         ← Bu dosya
├── talimat.txt          ← İlk fikir notu
│
├── db/
│   ├── demo_data.py     ← Tüm demo sabitler (DEMO_BOM, DEMO_STOKLAR vb.)
│   ├── baglanti.py      ← get_connection(), test_baglanti()
│   └── sorgular.py      ← Veri erişim katmanı (USE_DEMO'ya göre demo↔gerçek)
│
├── logic/
│   ├── maliyet.py       ← birim_maliyet(), mamul_maliyet_hesapla()
│   └── excel.py         ← maliyet_excel_kaydet(), baglama_excel_kaydet()
│
└── ui/
    ├── stil.py          ← STIL sabiti + etiket/buton/ayrac yardımcıları
    ├── ana_menu.py      ← Sayfa 0: Ana menü kartları
    ├── baglanti.py      ← Sayfa 1: DB bağlantı formu
    ├── tarama.py        ← Sayfa 2: Animasyonlu tarama + TaramaThread
    ├── eslestirme.py    ← Sayfa 3: Stok–mamül eşleştirme
    ├── rapor.py         ← Sayfa 4: Özet + Excel kaydet
    ├── maliyet.py       ← Sayfa 5: Maliyet parametreleri + hesaplama
    └── ana_pencere.py   ← QMainWindow, sayfa yönetimi, adım çubuğu
```

---

## Demo / Gerçek Mod Ayrımı

`config.py` dosyasındaki tek satırla geçiş yapılır:

```python
USE_DEMO = True   # demo verisiyle çalışır, DB gerekmez
USE_DEMO = False  # db/sorgular.py gerçek SQL çalıştırır
```

`db/sorgular.py` içindeki her fonksiyon bu bayrağa göre ya demo datayı döner ya da gerçek sorguyu çalıştırır.

---

## Düzeltilen Hata

**`mamul_maliyet_hesapla` return tipi tutarsızlığı** (`logic/maliyet.py`):

```python
# Eskiden — mamül bulunamazsa list döner, çağıran tuple bekler:
if not mamul:
    return []

# Şimdi — her zaman (list, float) tuple döner:
if not mamul:
    return [], 0.0
```

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

| Sütun | Açıklama |
|---|---|
| Stok Kodu / Adı | |
| Fatura Türleri | Alış / Masraf / Hizmet / İthalat |
| Fatura Sayısı / Toplam Tutar | |
| İlk Fatura / Son Fatura | |
| Tedarikçi | |
| Mamül Kodu / Adı | Kullanıcının atadığı |
| İşlem | Bağlandı (yeşil) / Atlandı (sarı) |

### Araç 2 — Maliyet Raporu
Her mamül için 4 satır tipi (renkli):

| Renk | Tip | İçerik |
|---|---|---|
| Koyu mavi | MAMÜL | Hammadde toplamı, işçilik, genel toplam |
| Açık gri | BİLEŞEN | Stok kodu/adı, BOM miktarı, birim maliyet |
| Turuncu | İŞÇİLİK | Manuel girilen işçilik tutarı |
| Yeşil | TOPLAM | Hammadde + işçilik |

Üst bilgi satırı: yöntem, dönem, oluşturma tarihi. Otomatik filtre açık.

---

## Teknik Yığın

| Bileşen | Teknoloji |
|---|---|
| Dil | Python 3.14 |
| Arayüz | PyQt5 5.15.11 (Fusion teması) |
| Excel çıktı | openpyxl 3.1.5 |
| Veritabanı sürücüsü | pyodbc 5.3.0 (kurulu ✓) |
| Dağıtım | PyInstaller 6.20.0 → `CEO-ERP.exe` ✓ |

---

## Yapılacaklar (Sonraki Oturum)

### ⏳ Önce Cevaplanması Gereken Sorular

1. **Bağlantı yöntemi:** SQL Authentication (kullanıcı/şifre) mi, Windows Authentication mi?
2. **Sunucu konumu:** Bu bilgisayar (localhost) mı, ağdaki başka sunucu mu?
3. **Sunucu adı / IP:** Örn: `192.168.1.10\CEOERP` veya `localhost\SQLEXPRESS`
4. **Veritabanı adı:** CEO ERP'nin kullandığı DB adı
5. **Kullanıcı adı / şifre:** (SQL Auth ise)

Sorular cevaplanınca bağlantı kurulur, CEO ERP tablo yapısı keşfedilir ve `db/sorgular.py` içindeki stub'lar gerçek SQL ile doldurulur.

### Bağlantı Kurulduktan Sonra

**Araç 1:**
- [ ] CEO ERP tablo yapısının incelenmesi (stok, reçete, mamül ağacı, fatura satırları)
- [ ] `recetesiz_faturali_stoklar()` için gerçek SQL yazılması
- [ ] `mamul_agaci_listesi()` için gerçek SQL yazılması
- [ ] `stoku_mamule_bagla()` için INSERT/UPDATE yazılması

**Araç 2:**
- [ ] `bom_listesi()` için gerçek SQL yazılması
- [ ] `stok_fiyat_gecmisi()` için gerçek SQL yazılması
- [ ] Çok seviyeli BOM özyinelemeli hesaplama testi

**Ortak:**
- [x] PyInstaller ile tek `.exe` çıktısı → `dist/CEO-ERP.exe`
