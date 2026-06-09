# CEO ERP Araçları — Proje Kuralları

## Her Değişiklik Döngüsü

1. Kodu değiştir
2. Test et (`python main.py`)
3. Gerekiyorsa exe derle: `build.bat` → sonra `copy config.json dist\config.json`
4. `ERP-OKUMA.md` güncelle
5. `git add -A && git commit && git push`

## Dağıtım

- Exe adı: `dist/CEO-ERP-Araclar.exe`
- Her exe derlemesinden sonra `config.json` → `dist/config.json` kopyalanmalı
- Her push'ta `dist/CEO-ERP-Araclar.exe` ve `dist/config.json` birlikte gönderilmeli

## Proje

- **GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac
- **DB:** SQL Server `WIN-3FATBI9RQAA\CEO1`, Firma 504
- **Kural:** CEO ERP'de SADECE OKUMA (`talimat.txt`). Yazma yalnızca stok kartı akışında.
- **Yapı:** 5 sekme — Mamül Ağacı / Maliyet / SW Kodlama / Stok Kartı Aktar / Satış Faturaları
