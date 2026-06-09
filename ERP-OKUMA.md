# CEO ERP Araçları

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe` (~54 MB)  
**Son güncelleme:** 2026-06-09

---

## Sekmeler

| Sekme | Ne yapar |
|---|---|
| 🔗 Mamül Ağacı | Reçetesiz + faturalı stokları tespit eder, mamüle bağlar |
| 💰 Maliyet | LIFO / FIFO / Ağırlıklı Ortalama — Excel maliyet raporu |
| ⚙ SW Kodlama | SolidWorks montaj → AI sınıflandırma → GEM/YMB kodu |
| 📦 Stok Kartı Aktar | SW sonrası CEO ERP'ye otomatik stok kartı açar |
| 🧾 Satış Faturaları | Tarih aralığına göre satış fatura/irsaliye listesi + Excel çıktısı |

---

## Mamül Ağacı Sekmesi — Önemli Notlar

İki alt sayfa vardır:

**Tarama Sayfası** — Reçetesiz + faturalı stokları tespit eder (kesişim kümesi).
- Sorguda `UretimReceteHatPlaniGirdi.KartId NOT IN` filtresi uygulanır; hat girdisi (bileşen/operasyon alt kodu) olarak kayıtlı stoklar kesişime dahil edilmez.
- StokHareketDetay JOIN'i `sk.Id` üzerinden yapılır; aksi takdirde 2 milyon+ Kartezyen çarpım kaydı dönebilir.
- `shd.Turu = 1` filtresi zorunludur: Turu=3 satırları kur farkı faturası veya masraf/sarf referansı olabilir; bu satırlarda `IslemKartId` alınan stoğu değil muhasebe referansını gösterir. Turu=1 olmadan faturası olmayan stoklar raporda sahte olarak çıkar (örn. AKAKDEV0007/OPTO PULSER-PWG vakası).
- Tarama tamamlandığında **Excel'e Aktar** butonu belirir → `logic/excel.py:kesisim_excel_kaydet` ile 8 sütunlu (tarih + stok bilgileri) xlsx üretilir.

**Eşleştirme Sayfası** — Tespit edilen stokları mamüle bağlar.
- Stok detay etiketleri fare ile seçilebilir (kopyalama/arama kolaylığı).

---

## Maliyet Sekmesi — Önemli Notlar

- **Bağlan ve Mamülleri Yükle** butonuna bas → DB bağlantısı arka thread'de kurulur, pencere donmaz
- Yükleme sırasında mavi ilerleme çubuğu görünür; bittikten sonra buton "✅ 545 mamül yüklendi" olur
- Arama kutusuna yazınca liste anlık daralır (kod veya ada göre)
- **Fiyat kaynağı:** Yalnızca `IslemKodu IN (1, 5)` — alış faturası + alış irsaliyesi. Üretimden giriş, sayım, devir vb. hariç tutulur
- **Performans:** `stok_fiyatlari_toplu()` ile N bileşen için tek SQL sorgusu; 20 bileşenli mamülde 42 DB round-trip → 4'e düştü. BOM listesi özyinelemeli hesaplamada tekrar sorgulanmaz.

---

## Satış Faturaları Sekmesi — Önemli Notlar

- **Bağlan** butonuyla DB bağlantısı arka thread'de kurulur
- Tarih girildikten sonra **Faturaları Getir** → `satis_faturalari()` sorgusu çalışır
- `IslemKodu IN (2, 6)` — satış faturası + satış irsaliyesi; `shd.Turu = 1` ürün satırlarını filtreler
- 9 kolonlu tablo: Tarih / Belge Türü / Belge No / Müşteri / Stok Kodu / Stok Adı / Miktar / Birim Fiyat / Tutar
- Arama kutusuna yazınca satırlar anlık filtrelenir (müşteri, stok kodu, belge no)
- **Excel'e Aktar** → openpyxl ile biçimlendirilmiş xlsx, son satırda toplam tutar
- `shd.Turu = 1` filtresinden kayıt dönmüyorsa bu değer ERP versiyonuna göre farklı olabilir; `sorgular.py:satis_faturalari()` içinde ayarlanabilir

---

## Veritabanı

- **Sunucu:** `WIN-3FATBI9RQAA\CEO1`  
- **Firma:** 504  
- **Auth:** SQL Server (`sa`), şifre `config.json`'da base64 ile saklanır  
- **Kural:** CEO ERP'de **SADECE OKUMA**. Yazma yalnızca Stok Kartı Aktar akışında, kullanıcı onayıyla.

---

## Kurulum & Çalıştırma

```
git clone https://github.com/savasadiguzel-hash/ceo-erp-arac
cd ceo-erp-arac
pip install -r requirements.txt
python main.py
```

Gerekli `.env` (SW Kodlama + Stok Kartı için):
```
GEMINI_API_KEY=...
CEO_SQL_CONN=DRIVER={SQL Server};SERVER=WIN-3FATBI9RQAA\CEO1;UID=sa;PWD=...
```

Derleme: `build.bat` → `dist/CEO-ERP-Araclar.exe` + `dist/config.json`

---

## Klasör Yapısı

```
main.py / config.py / config.json / build.bat
db/      → baglanti.py, sorgular.py
logic/   → maliyet.py, excel.py
ui/      → ana_pencere.py, maliyet.py, mamul_agaci_tab.py, ...
sw/      → SW Kodlama modülleri
dist/    → CEO-ERP-Araclar.exe, config.json
```

---

## Sıradaki Geliştirmeler

1. **BOM otomasyonu** — SW çalışması sonrası `UrunAgaci + UrunAgaciDetay` otomatik oluşturma  
2. **PDF gömme** — teknik resim PDF'lerini `StokKarti.DokumanPath`'e bağlama  
3. **Canlı SW testi** — SW Kodlama sekmesini iş makinesinde SolidWorks 2019 ile doğrulama
