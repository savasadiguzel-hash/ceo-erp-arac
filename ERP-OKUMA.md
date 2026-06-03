# CEO ERP — Mamül Ağacı Bağlantı Aracı

## Proje Amaçları

### Araç 1 — Mamül Ağacı Bağlantı Aracı
CEO ERP sisteminde **maliyeti olan ama hiçbir mamül ağacına veya reçeteye bağlı olmayan stok kalemleri** tespit edilerek doğru mamül ağacına atanması.

Bu stoklar, ürün maliyet hesabında "boşta görünen maliyet" olarak kalmakta ve ürün bazlı maliyet analizini bozmaktadır.

### Araç 2 — Maliyet Hesaplama
Tüm reçete ve mamül ağaçları taranarak **LIFO, FIFO veya Ağırlıklı Ortalama** yöntemiyle seçilen tarih aralığında ürün bazında maliyet raporu oluşturulması.

Tüm işler dışarıya yaptırıldığından (montaj hariç) tüm faturalar toplanarak doğru bir ürün maliyeti elde edilebilir. İşçilik tutarı mamül bazında manuel girilir.

---

## Tespit Mantığı (İki Filtreli Kesişim)

```
Tüm Stok Kodları
    │
    ├─ FİLTRE 1: Herhangi bir reçetede VEYA mamül ağacında yer ALMAYAN stoklar
    │
    └─ FİLTRE 2: Bu stoklar için en az 1 alış/masraf/hizmet/ithalat faturası girilmiş olanlar
                        │
                        ▼
              KESİŞİM KÜMESİ
              → Bunlar ekranda gösterilir, kullanıcı her biri için mamül ağacı seçer
```

**Neden kesişim?**
- Sadece reçetesiz stok: faturası yoksa maliyeti sıfır, sorun değil
- Sadece faturası olan stok: reçetedeyse zaten doğru yerde
- İkisi birden → gerçek "boşta maliyet" = düzeltilmesi gereken kayıt

---

## Uygulama Akışı

### Ana Menü (Sayfa 0)
İki araç kartı gösterilir, kullanıcı hangisini kullanacağını seçer.

---

## Araç 1 Akışı (4 Aşama)

### ① Bağlantı Sayfası
- SQL Server bağlantı bilgileri (sunucu, veritabanı, kullanıcı, şifre)
- Hangi fatura türlerinin taranacağı seçilir:
  - Alış Faturası
  - Masraf Faturası
  - Hizmet Faturası
  - İthalat Faturası
- "Demo Modunda Çalıştır" seçeneği (gerçek DB olmadan test için)

### ② Tarama Sayfası
Animasyonlu ilerleme çubuğuyla şu adımlar sırayla çalışır:
1. Tüm stok kodları listelenir
2. Reçeteler kontrol edilir
3. Mamül ağaçları kontrol edilir
4. Reçete/ağaç dışı stoklar filtrelenir
5. Bu stoklar için alış faturaları kontrol edilir
6. Kesişim kümesi hesaplanır

Tarama sonunda özet gösterilir:
- Toplam stok sayısı
- Reçete/mamül ağacında olmayan stok sayısı
- Bunlardan faturası olan (işlenecek) stok sayısı

### ③ Eşleştirme Sayfası
Her stok için iki panelli ekran:

**Sol Panel — Stok Detayları:**
| Alan | Açıklama |
|---|---|
| Stok Kodu | Kırmızı/kalın — sorunlu stok |
| Stok Adı | |
| Fatura Türleri | Hangi tür faturalarla gelmiş |
| Fatura Sayısı | Toplam kaç fatura girilmiş |
| Toplam Tutar | Bu stoğun yarattığı toplam maliyet |
| İlk / Son Fatura | Tarih aralığı |
| Tedarikçi | |

**Sağ Panel — Mamül Ağacı Seçimi:**
- Arama kutusu: kod veya ada göre filtreler
- Tıklanınca seçilen mamül yeşil kutuya düşer
- İşlem geçmişi (bu oturumda yapılanlar)

**Alt Butonlar:**
- `← Geri` — önceki stoğa dön, işlemi iptal et
- `⊘ Şimdilik Atla` — bu stoğu atla, ileride tekrar bak
- `✓ Mamüle Bağla ve İleri` — seçilen mamüle bağla, kaydet, ilerle

### ④ Rapor Sayfası
- Oturum özeti (kaç bağlandı, kaç atlandı)
- Excel çıktısı alma
- Yeni tarama başlatma

---

---

## Araç 2 — Maliyet Hesaplama

### Parametreler (tek sayfa)
| Alan | Açıklama |
|---|---|
| Veritabanı | Sunucu, DB adı, kullanıcı, şifre |
| Tarih Aralığı | Başlangıç – Bitiş (takvim seçici) |
| Maliyet Yöntemi | Ağırlıklı Ortalama / FIFO / LIFO |
| Mamül Listesi | Tüm reçete/mamül ağaçları, her biri seçilebilir |
| İşçilik Tutarı | Her mamül için ayrı alan — kullanıcı manuel girer |

### Hesaplama Mantığı
- **Ağırlıklı Ortalama:** Dönem içi faturalar → Σ(qty×fiyat) / Σ(qty)
- **FIFO:** Dönem içinde en eski fatura fiyatı
- **LIFO:** Dönem içinde en yeni fatura fiyatı
- **Çok seviyeli BOM:** Yarı mamüller özyinelemeli olarak hesaplanır

### Excel Çıktısı (Maliyet Raporu)

Her mamül için 4 farklı satır tipi (renkli):

| Renk | Tip | İçerik |
|---|---|---|
| Koyu mavi | MAMÜL | Mamül kodu, adı, hammadde toplamı, işçilik, genel toplam |
| Açık gri | BİLEŞEN | Stok kodu, adı, BOM miktarı, birim maliyet, satır maliyeti |
| Turuncu | İŞÇİLİK | Manuel girilen işçilik tutarı |
| Yeşil | TOPLAM | Hammadde + işçilik = genel toplam |

Üst bilgi satırı: yöntem, dönem, oluşturma tarihi.

---

## Araç 1 — Excel Raporu Yapısı

Tek sayfa, otomatik filtreli, ilk satır dondurulmuş:

| Sütun | Açıklama |
|---|---|
| Stok Kodu | |
| Stok Adı | |
| Fatura Türleri | Alış / Masraf / Hizmet / İthalat |
| Fatura Sayısı | |
| Toplam Tutar | |
| İlk Fatura | |
| Son Fatura | |
| Tedarikçi | |
| Mamül Kodu | Kullanıcının atadığı |
| Mamül Adı | |
| İşlem | Bağlandı / Atlandı |

**Renk Kodlaması:**
- Yeşil satır → Mamül ağacına bağlandı
- Sarı satır → Atlandı / ileride işlenecek

---

## Teknik Yığın

| Bileşen | Teknoloji |
|---|---|
| Dil | Python 3.14 |
| Arayüz | PyQt5 (Fusion teması) |
| Excel çıktı | openpyxl |
| Veritabanı (planlanan) | Microsoft SQL Server (pyodbc) |
| Dağıtım (planlanan) | PyInstaller → .exe |

---

## Mevcut Dosyalar

```
C:\yeni-erp\
├── main.py        ← Uygulamanın tamamı (GUI + demo verisi)
├── ERP-OKUMA.md   ← Bu dosya
└── talimat.txt    ← İlk fikir notu
```

---

## Sayfa Yapısı (Stack)

| Sayfa | İçerik | Araç |
|---|---|---|
| 0 | Ana Menü — araç seçimi | — |
| 1 | Veritabanı Bağlantısı | Araç 1 |
| 2 | Tarama (animasyonlu) | Araç 1 |
| 3 | Eşleştirme | Araç 1 |
| 4 | Rapor + Excel | Araç 1 |
| 5 | Maliyet Parametreleri + Excel | Araç 2 |

## Yapılacaklar (Sonraki Oturum)

**Araç 1:**
- [ ] `pyodbc` ile gerçek SQL Server bağlantısı
- [ ] CEO ERP tablo yapısının incelenmesi (stok, reçete, mamül ağacı, fatura satırları)
- [ ] Kesişim kümesini döndüren SQL sorgusunun yazılması
- [ ] Mamül ağacı listesini veritabanından çeken sorgu
- [ ] "Mamüle Bağla" butonunun veritabanına yazma işlemi

**Araç 2:**
- [ ] Reçete/mamül ağacı listesini veritabanından çeken sorgu
- [ ] Stok bazlı fatura fiyat geçmişini çeken sorgu (tarih + birim fiyat + miktar)
- [ ] Çok seviyeli BOM için özyinelemeli hesaplama (yarı mamül → mamül)
- [ ] Veritabanı bağlantısı gerçek veriye bağlanınca LIFO/FIFO/WA testleri

**Ortak:**
- [ ] PyInstaller ile tek .exe çıktısı
