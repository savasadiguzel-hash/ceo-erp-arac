# CEO ERP Araçları

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe` (~54 MB)  
**Son güncelleme:** 2026-06-05 (3)

---

## Uygulama

Tek PyQt5 penceresi, 4 sekme:

| Sekme | Açıklama |
|---|---|
| 🔗 Mamül Ağacı | Reçeteye bağlı olmayan + faturası olan stokları tespit et, mamüle bağla |
| 💰 Maliyet | LIFO / FIFO / Ağırlıklı Ortalama ile ürün bazında maliyet raporu (Excel); **"Bağlan ve Mamülleri Yükle"** butonu ile canlı mamül listesi yüklenir |
| ⚙ SW Kodlama | SolidWorks montaj → AI sınıflandırma → GEM/YMB kodu → kopya üret |
| 📦 Stok Kartı Aktar | SW çalışması sonrası CEO ERP'ye stok kartı aç (firma 504) |

---

## Kurulum

```
git clone https://github.com/savasadiguzel-hash/ceo-erp-arac
cd ceo-erp-arac
pip install -r requirements.txt
```

**Gerekli `.env` (SW Kodlama + Stok Kartı için):**
```
GEMINI_API_KEY=...
CEO_SQL_CONN=DRIVER={SQL Server};SERVER=WIN-3FATBI9RQAA\CEO1;UID=sa;PWD=...
```

**Çalıştırma:**
```
python main.py          # kaynak koddan
dist\CEO-ERP-Araclar.exe  # derlenmiş exe
```

**Derleme:**
```
build.bat
```

---

## Veritabanı

- **Sunucu:** `WIN-3FATBI9RQAA\CEO1`  
- **Firma:** 504 — veritabanı `[504]`  
- **Auth:** SQL Server auth, `config.json`'dan okunur  
- **Kural:** CEO ERP'de **SADECE OKUMA** (`talimat.txt`). Yazma yalnızca stok kartı açma akışında, kullanıcı onayıyla.

---

## Klasör Yapısı

```
main.py / config.py / config.json / requirements.txt / build.bat
db/          → SQL bağlantısı (baglanti.py, sorgular.py)
logic/       → maliyet hesaplama, Excel çıktısı
sw/          → SolidWorks modülleri (models, sw_reader, classifier,
               excel_handler, renamer, vision_handler, erp_handler, pipeline)
ui/          → PyQt5 arayüz (ana_pencere, 4 sekme widget'ı, yardımcı sayfalar)
dist/        → CEO-ERP-Araclar.exe + config.json
```

---

## Sıradaki Geliştirmeler

1. **BOM / Ürün Ağacı** — SW çalışması sonrası `UrunAgaci + UrunAgaciDetay` otomatik oluşturma  
2. **PDF gömme** — teknik resim PDF'lerini `StokKarti.DokumanPath`'e bağlama  
3. **Canlı SW testi** — SW Kodlama sekmesini is makinesinde SolidWorks 2019 ile doğrulama
