# CEO ERP Araçları — Proje Kuralları

## Her Değişiklik Döngüsü

1. Kodu değiştir
2. Test et (`python main.py`)
3. Gerekiyorsa exe derle: `build.bat` → sonra `copy config.json dist\config.json`
4. `ERP-OKUMA.md` güncelle
5. `git add -A && git commit && git push`

> **Bakiye/depo mantığına dokunan her değişiklikten sonra**
> `python tools\mutabakat.py` çalıştır; eşleşme oranı düşerse commit etme.

## Dağıtım

- Exe adı: `dist/CEO-ERP-Araclar.exe`
- Her exe derlemesinden sonra `config.json` → `dist/config.json` kopyalanmalı
- Her push'ta `dist/CEO-ERP-Araclar.exe` ve `dist/config.json` birlikte gönderilmeli

## Proje

- **GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac
- **DB:** SQL Server `WIN-3FATBI9RQAA\CEO1`, `DATABASE=504`, kullanıcı `sa`
- **Kural:** CEO ERP'de SADECE OKUMA. Yazma yalnızca stok kartı akışında.
- **Yapı:** 6 sekme — Mamül Ağacı / Maliyet / SW Kodlama / Stok Kartı Aktar / Satış Faturaları / Üretim Eksik Stok

## İzin Gerektiren İşlemler

Kullanıcı komutu olmadan yapılmaz:
- `git push`
- `build.bat` (exe derleme)
- `python main.py` (uygulama testi)
