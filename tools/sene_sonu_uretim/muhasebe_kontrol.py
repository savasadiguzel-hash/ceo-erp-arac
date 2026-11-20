"""Muhasebeye gönderilen eksi listesi (kullanıcının düzenlediği Excel) ile bugünkü durumu karşılaştırır. Salt okuma.
Kullanım: python muhasebe_kontrol.py "<gönderilen liste.xlsx>" <çıktı.xlsx> [gönderim tarihi YYYY-MM-DD, vars. 2026-11-11]
- Her kalem için: gönderimdeki bakiye, bugünkü bakiye, aradaki giriş/çıkış hareketleri (CreationTime >= gönderim),
  emirler tamamlandıktan sonraki bakiye (bugünkü bakiye + hat üretimi - girdi tüketimi, tamamlanmamış hatlar).
- Girişlerin BelgeTarihi ilgili en erken emir tarihinden SONRA ise uyarı (kapanışta maliyet riski)."""
import sys, io
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import stok_guncel_bakiyeleri

GIRIS = (1, 4, 5, 8, 15, 16, 20, 22, 26, 29)
CIKIS = (2, 3, 6, 7, 17, 18, 19, 21, 24, 28)
ISLEM_AD = {1: 'Alış Faturası', 4: 'Satış İade', 5: 'Alış İrsaliyesi', 8: 'Sayım Fazlası/Giriş', 15: 'Devir/Giriş', 16: 'Üretimden Giriş',
            20: 'Giriş', 22: 'Giriş', 26: 'Giriş', 29: 'Giriş', 2: 'Satış Faturası', 3: 'Alış İade', 6: 'Satış İrsaliyesi',
            7: 'Çıkış', 17: 'Üretime Çıkış', 18: 'Çıkış', 19: 'Çıkış', 21: 'Çıkış', 24: 'Çıkış', 28: 'Çıkış'}
EK_EMIRLER = ['ŞİRKET.1092026-3']
LISTE, OUT = sys.argv[1], sys.argv[2]
GONDERIM = sys.argv[3] if len(sys.argv) > 3 else '2026-11-11'

wb_in = openpyxl.load_workbook(LISTE, read_only=True, data_only=True)
ws_in = wb_in['Eksiye Düşen Malzemeler']
rows = list(ws_in.iter_rows(values_only=True)); hdr = rows[0]
ix = {h: i for i, h in enumerate(hdr)}
liste = []
for r in rows[1:]:
    if not r or not r[ix['Stok Kodu']]: continue
    liste.append({h: r[i] for h, i in ix.items()})
kodlar = [x['Stok Kodu'] for x in liste]

c = get_connection(**DB_DEFAULTS); cur = c.cursor()
bugun = stok_guncel_bakiyeleri(c, kodlar)
# Emirler sonrası: tamamlanmamış hatların üretim/tüketimi
cur.execute(f"""SELECT ue.Kodu, ue.UretimEmriTarihi, h.Id, sk.Kodu, h.TalepMiktari,
   (SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
 FROM UretimEmri ue JOIN UretimEmriHatPlani h ON h.UretimEmriId=ue.Id JOIN StokKarti sk ON sk.Id=h.KartId
 WHERE ue.DurumId=3 AND (ue.SurecDipnot LIKE 'Fatura:%' OR ue.Kodu IN ({','.join('?'*len(EK_EMIRLER))}))""", *EK_EMIRLER)
uretim = defaultdict(float); tuketim = defaultdict(float); ilk_emir = {}
for ek, et, hid, hkod, htalep, hhar in cur.fetchall():
    if hhar: continue
    uretim[hkod] += float(htalep or 0)
    cur.execute("""SELECT sk.Kodu, SUM(g.TalepMiktar) FROM UretimEmriHatPlaniGirdi g JOIN StokKarti sk ON sk.Id=g.KartId
      WHERE g.UretimEmriHatPlaniId=? AND g.Tipi<>2 GROUP BY sk.Kodu""", hid)
    for k, t in cur.fetchall():
        tuketim[k] += float(t or 0)
        if k not in ilk_emir or et < ilk_emir[k]: ilk_emir[k] = et

# Gönderimden sonra kaydedilen hareketler
yer = ','.join('?' * len(kodlar))
cur.execute(f"""SELECT sk.Kodu, sh.IslemKodu, sh.BelgeTarihi, sh.CreationTime, sh.BelgeSeriNo, sh.BelgeSiraNo, sh.FaturaId,
     shd.Miktar - ISNULL(shd_f.Miktar,0), shd.BirimFiyat, shd.Tutar, sh.Notlar
 FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId
 LEFT JOIN StokHareketDetay shd_f ON shd_f.Id=shd.FaturaDetayId
 JOIN StokKarti sk ON sk.Id=shd.IslemKartId
 WHERE sk.Kodu IN ({yer}) AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1
   AND sh.CreationTime >= ? ORDER BY sk.Kodu, sh.CreationTime""", *kodlar, GONDERIM)
hareket = defaultdict(list)
for row in cur.fetchall(): hareket[row[0]].append(row)

def net(h):
    k, ik, bt, ct, sn, sno, fid, m = h[:8]
    if fid is not None: return 0.0
    m = float(m or 0)
    return m if ik in GIRIS else (-m if ik in CIKIS else 0.0)

wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Kontrol'
cols = ['Sınıf', 'Stok Kodu', 'Stok Adı', 'Birim', 'Düzeltilecek (gönderilen)', 'Bakiye (gönderimde)', 'Gönderim sonrası giriş',
        'Gönderim sonrası çıkış', 'Bakiye (bugün)', 'Emirlerle Tüketim', 'Emirlerle Üretim', 'Emirler Sonrası Bakiye (bugün)',
        'DURUM', 'Kalan Eksik', 'Girişin Belge Tarihi', 'En Erken Emir Tarihi', 'Tarih Uyarısı', 'Giriş Belgeleri']
ws.append(cols)
for cell in ws[1]: cell.font = Font(bold=True, color='FFFFFF'); cell.fill = PatternFill('solid', fgColor='1F4E78'); cell.alignment = Alignment(wrap_text=True)
YESIL, SARI, KIRMIZI = PatternFill('solid', fgColor='C6EFCE'), PatternFill('solid', fgColor='FFEB9C'), PatternFill('solid', fgColor='FFC7CE')
say = defaultdict(int); tarih_uyari = 0; detay = []
for x in liste:
    k = x['Stok Kodu']; hs = hareket.get(k, [])
    gir = sum(net(h) for h in hs if net(h) > 0); cik = -sum(net(h) for h in hs if net(h) < 0)
    son = bugun.get(k, 0) + uretim[k] - tuketim[k]
    if son >= -1e-6: durum = 'Düzeldi'
    elif gir > 1e-6: durum = 'Kısmen düzeldi'
    else: durum = 'Giriş yok'
    say[durum] += 1
    giris_tarih = sorted({h[2].date() for h in hs if net(h) > 0})
    ee = ilk_emir.get(k)
    uyari = ''
    if giris_tarih and ee and max(giris_tarih) > ee.date():
        uyari = 'Giriş emir tarihinden sonra'; tarih_uyari += 1
    belgeler = '; '.join(f"{ISLEM_AD.get(h[1], h[1])} {(h[4] or '').strip()}{h[5] or ''} {h[2]:%d.%m.%Y} ({float(h[7] or 0):g})" for h in hs if net(h) != 0)
    ws.append([x.get('Sınıf'), k, x.get('Stok Adı'), x.get('Birim'), x.get('DÜZELTİLECEK MİKTAR'), x.get('Bugünkü ERP Bakiye'),
               round(gir, 4), round(cik, 4), round(bugun.get(k, 0), 4), round(tuketim[k], 4), round(uretim[k], 4), round(son, 4),
               durum, round(-son, 4) if son < -1e-6 else 0, ', '.join(f'{d:%d.%m.%Y}' for d in giris_tarih),
               f'{ee:%d.%m.%Y}' if ee else '', uyari, belgeler])
    ws.cell(ws.max_row, 13).fill = {'Düzeldi': YESIL, 'Kısmen düzeldi': SARI, 'Giriş yok': KIRMIZI}[durum]
    if uyari: ws.cell(ws.max_row, 17).fill = SARI
    for h in hs: detay.append(h)
for col, w in zip('ABCDEFGHIJKLMNOPQR', [24, 22, 40, 7, 11, 11, 10, 10, 10, 10, 10, 12, 14, 10, 14, 12, 22, 70]):
    ws.column_dimensions[col].width = w
ws.freeze_panes = 'C2'; ws.auto_filter.ref = ws.dimensions

ws2 = wb.create_sheet('Gönderim Sonrası Hareketler')
ws2.append(['Stok Kodu', 'İşlem', 'Belge Tarihi', 'Kayıt Zamanı', 'Belge No', 'Faturalaşmış İrs.', 'Miktar', 'Birim Fiyat', 'Tutar', 'Not'])
for cell in ws2[1]: cell.font = Font(bold=True)
for h in detay:
    ws2.append([h[0], ISLEM_AD.get(h[1], h[1]), h[2].strftime('%d.%m.%Y'), h[3].strftime('%d.%m.%Y %H:%M'), f"{(h[4] or '').strip()}{h[5] or ''}",
                'Evet' if h[6] else '', float(h[7] or 0), float(h[8] or 0), float(h[9] or 0), (h[10] or '')[:100]])
wb.save(OUT)

print('liste kalemi:', len(liste))
for d in ('Düzeldi', 'Kısmen düzeldi', 'Giriş yok'): print(f'  {d}: {say[d]}')
print('emir tarihinden sonra girişli kalem:', tarih_uyari)
print('gönderim sonrası hareket satırı:', len(detay))
bt = defaultdict(int)
for h in detay: bt[(ISLEM_AD.get(h[1], h[1]), h[2].strftime('%d.%m.%Y'), h[3].strftime('%d.%m.%Y'), f"{(h[4] or '').strip()}{h[5] or ''}")] += 1
print('belge özetleri (işlem, belge tarihi, kayıt tarihi, no -> satır):')
for kk, v in sorted(bt.items(), key=lambda t: t[0][2]): print('  ', kk, v)
