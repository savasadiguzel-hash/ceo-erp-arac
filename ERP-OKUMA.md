# CEO ERP Araçları

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe` (~54 MB)  
**Son güncelleme:** 2026-06-05

---

## Sekmeler

| Sekme | Ne yapar |
|---|---|
| 🔗 Mamül Ağacı | Reçetesiz + faturalı stokları tespit eder, mamüle bağlar |
| 💰 Maliyet | LIFO / FIFO / Ağırlıklı Ortalama — Excel maliyet raporu |
| ⚙ SW Kodlama | SolidWorks montaj → AI sınıflandırma → GEM/YMB kodu |
| 📦 Stok Kartı Aktar | SW sonrası CEO ERP'ye otomatik stok kartı açar |

---

## Maliyet Sekmesi — Önemli Notlar

- **Bağlan ve Mamülleri Yükle** butonuna bas → DB bağlantısı arka thread'de kurulur, pencere donmaz
- Yükleme sırasında mavi ilerleme çubuğu görünür; bittikten sonra buton "✅ 545 mamül yüklendi" olur
- Arama kutusuna yazınca liste anlık daralır (kod veya ada göre)
- **Fiyat kaynağı:** Yalnızca `IslemKodu IN (1, 5)` — alış faturası + alış irsaliyesi. Üretimden giriş, sayım, devir vb. hariç tutulur

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
