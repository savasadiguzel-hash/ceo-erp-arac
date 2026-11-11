import sys, io, pickle
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from collections import defaultdict
from config import DB_DEFAULTS
from db.baglanti import get_connection
d = pickle.load(open(sys.argv[1], 'rb')); OUT = sys.argv[2]
bak, ad, birim, bom = d['bak'], d['ad'], d['birim'], d['bom']
recete = {k for k in bom if k in ad}
c = get_connection(**DB_DEFAULTS); cur = c.cursor()

GIR = {1,4,5,8,15,16,20,22,26,29}; CIK = {2,3,6,7,17,18,19,21,24,28}
# Satılan ürünler (tüm zamanlar) — sayılan satış: 2 + faturalaşmamış 6
cur.execute("""SELECT DISTINCT sk.Kodu FROM StokHareket sh JOIN StokHareketDetay shd ON shd.HareketId=sh.Id
 JOIN StokKarti sk ON sk.Id=shd.IslemKartId
 WHERE sh.Aktif=1 AND shd.Aktif=1 AND shd.Turu=1 AND (sh.IslemKodu=2 OR (sh.IslemKodu=6 AND sh.FaturaId IS NULL))
   AND sh.BelgeTarihi >= '2026-01-01'""")
sold26 = {r[0] for r in cur.fetchall()}
kapsam = sorted(sold26 | {k for k, v in bak.items() if v < -1e-9})
print('kapsam', len(kapsam), '2026 satilan', len(sold26))

# Tüm hareketler (kapsam ürünleri) — bakiye formülüyle birebir
hareket = defaultdict(list)
for i in range(0, len(kapsam), 400):
    p = kapsam[i:i+400]; yer = ','.join('?'*len(p))
    cur.execute(f"""
    SELECT sk.Kodu, sh.Id, sh.IslemKodu, sh.BelgeTarihi, ISNULL(sh.BelgeSeriNo,'')+ISNULL(CAST(sh.BelgeSiraNo AS VARCHAR(20)),''),
           ISNULL(cmk.Unvani,''), shd.Miktar-ISNULL(shd_f.Miktar,0), ISNULL(shd.Tutar,0), sh.MusteriKartId
    FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId
    LEFT JOIN StokHareketDetay shd_f ON shd_f.Id=shd.FaturaDetayId
    JOIN StokKarti sk ON sk.Id=shd.IslemKartId
    LEFT JOIN CariMusteriKarti cmk ON cmk.Id=sh.MusteriKartId
    WHERE sk.Kodu IN ({yer}) AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL
      AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
    ORDER BY sk.Kodu, sh.BelgeTarihi, CASE WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29) THEN 0 ELSE 1 END, sh.Id""", *p)
    for r in cur.fetchall():
        hareket[r[0]].append(dict(id=r[1], ik=r[2], t=r[3], belge=r[4], cari=r[5], m=float(r[6] or 0), tutar=float(r[7] or 0), cid=r[8]))

# Mükerrer şüphesi: faturalaşmamış satış irsaliyesi (6, FaturaId NULL) + aynı cari/ürün/miktar ile satış faturası (2)
def mukerrer(hs):
    out = []
    fat = [h for h in hs if h['ik'] == 2]
    for h in hs:
        if h['ik'] != 6: continue
        for f in fat:
            if f['cid'] == h['cid'] and abs(f['m'] - h['m']) < 1e-6 and abs((f['t'] - h['t']).days) <= 60:
                out.append((h, f)); break
    return out

ozet = []; neg_detay = []; muk_rows = []
for k in kapsam:
    hs = hareket.get(k, [])
    s = defaultdict(float)
    for h in hs:
        y = h['t'].year
        if h['ik'] in (2, 6):
            s['satis_tum'] += h['m']; s['tutar_tum'] += h['tutar']
            if y == 2026: s['satis26'] += h['m']; s['tutar26'] += h['tutar']
        elif h['ik'] == 16:
            s['uret_tum'] += h['m']
            if y == 2026: s['uret26'] += h['m']
        elif h['ik'] in (1, 5):
            s['alis_tum'] += h['m']
            if y == 2026: s['alis26'] += h['m']
        elif h['ik'] == 17: s['uretime_cikis'] += h['m']
        elif h['ik'] == 20 and y == 2026 and h['t'].month == 1 and h['t'].day == 1: s['devir26'] += h['m']
    # running balance → son kez >=0 olduğu an, eksiye düşüren belge
    bal = 0.0; son_poz_idx = -1; ilk_dusus = None
    for i, h in enumerate(hs):
        bal += h['m'] if h['ik'] in GIR else (-h['m'] if h['ik'] in CIK else 0)
        if bal >= -1e-9: son_poz_idx = i; ilk_dusus = None
        elif ilk_dusus is None: ilk_dusus = h
    b = bak.get(k, 0.0)
    muk = mukerrer(hs)
    for h, f in muk:
        muk_rows.append((k, ad.get(k), h['cari'], h['belge'], h['t'].strftime('%d.%m.%Y'), h['m'], f['belge'], f['t'].strftime('%d.%m.%Y'), round(b, 2)))
    tur = 'Reçeteli' if k in recete else ('Mamul kodu, reçetesiz' if k.startswith('GMP-101') else 'Reçetesiz')
    # Yorum
    if b < -1e-9:
        if muk and sum(h['m'] for h, _ in muk) >= -b - 1e-6: yorum = 'Muhtemel mükerrer irsaliye+fatura — gerçek eksik olmayabilir'
        elif s['uret_tum'] == 0 and tur != 'Reçetesiz': yorum = 'Satılmış, hiç üretim girişi yok — üretim kaydı eksik'
        elif tur != 'Reçetesiz': yorum = 'Satış, üretim girişini aşmış — üretim kaydı eksik'
        else: yorum = 'Alış/sayım kaydı eksik veya fazla tüketim'
    else:
        yorum = ''
    ozet.append((k, ad.get(k), tur, birim.get(k), round(s['satis26'], 2), round(s['tutar26'], 2), round(s['uret26'], 2), round(s['alis26'], 2),
                 round(s['satis_tum'], 2), round(s['uret_tum'], 2), round(s['alis_tum'], 2), round(s['uretime_cikis'], 2), round(b, 2),
                 'EKSİ' if b < -1e-9 else '', round(max(0, -b), 2),
                 d['son_uretim'].get(k, ('',))[0] if k in d['son_uretim'] else '',
                 ilk_dusus['t'].strftime('%d.%m.%Y') if (b < -1e-9 and ilk_dusus) else '', len(muk), yorum))
    if b < -1e-9:
        for h in hs[son_poz_idx + 1:]:
            yon = 'Giriş' if h['ik'] in GIR else 'Çıkış'
            neg_detay.append((k, ad.get(k), h['t'].strftime('%d.%m.%Y'), h['ik'], {1:'Alış Fat',2:'Satış Fat',5:'Alış İrs',6:'Satış İrs',16:'Üretimden Giriş',17:'Üretime Çıkış'}.get(h['ik'], f'Kod {h["ik"]}'),
                              h['belge'], h['cari'], yon, h['m'] if yon == 'Giriş' else -h['m']))

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
wb = openpyxl.load_workbook(OUT)
for n in [s for s in wb.sheetnames if s.startswith(('6-', '7-', '8-'))]: del wb[n]
H = Font(bold=True, color='FFFFFF'); HF = PatternFill('solid', fgColor='833C0B'); RED = PatternFill('solid', fgColor='F8CBAD')
def sheet(name, cols, rows, widths, redcol=None):
    ws = wb.create_sheet(name); ws.append(cols)
    for cell in ws[1]: cell.font = H; cell.fill = HF; cell.alignment = Alignment(wrap_text=True, vertical='center')
    for r in rows:
        ws.append(list(r))
        if redcol is not None and r[redcol]:
            for cell in ws[ws.max_row]: cell.fill = RED
    ws.freeze_panes = 'C2'; ws.auto_filter.ref = ws.dimensions
    for i, w in enumerate(widths, 1): ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
ozet.sort(key=lambda r: (r[13] != 'EKSİ', r[12] if r[13] else -r[4]))
sheet('6-Ürün Bazında Satış-Stok', ['Kod','Ad','Tür','Birim','2026 Satış Miktarı','2026 Satış Tutarı','2026 Üretim Girişi','2026 Alış','Tüm Zaman Satış','Tüm Zaman Üretim','Tüm Zaman Alış','Üretime Çıkış (bileşen olarak)','ERP Bakiye','Durum','Eksik (üretilmesi gereken)','Son Üretim','Eksiye Düştüğü Tarih','Mükerrer Şüphesi (adet)','Değerlendirme'],
      ozet, [18,40,16,7,10,13,10,9,10,10,9,11,10,7,11,11,12,10,50], redcol=13)
sheet('7-Eksiye Düşüren Hareketler', ['Kod','Ad','Tarih','İşlem Kodu','İşlem','Belge No','Cari','Yön','Miktar (+/-)'], neg_detay, [18,35,11,7,15,18,40,7,10])
sheet('8-Mükerrer Şüphesi', ['Kod','Ad','Cari','İrsaliye No (faturalaşmamış)','İrsaliye Tarihi','Miktar','Fatura No','Fatura Tarihi','ERP Bakiye'], muk_rows, [18,35,40,18,11,8,18,11,10])
wb.save(OUT)

neg = [r for r in ozet if r[13]]
print('\nEKSI URUNLER:')
for r in neg: print(f"  {r[0]:16s} {r[2]:22s} sat26={r[4]:g} tut26={r[5]:,.0f} ur26={r[6]:g} satT={r[8]:g} urT={r[9]:g} alT={r[10]:g} bak={r[12]:g} dusus={r[16]} muk={r[17]} | {r[18]}")
pos = [r for r in ozet if not r[13]]
print('\n2026 satilip bakiye>=0 urun:', len(pos), ' recetelilerden 2026 satis > 2026 uretim:',
      sum(1 for r in pos if r[2]=='Reçeteli' and r[4] > r[6]))
print('Toplam 2026 satis tutari (kapsam):', round(sum(r[5] for r in ozet), 2), ' eksi urunlerin 2026 satis tutari:', round(sum(r[5] for r in neg), 2))
print('mukerrer satir', len(muk_rows)); [print('  ', m) for m in muk_rows[:20]]
print('\nNEG DETAY (sadece satislar, ilk 40):')
for x in [x for x in neg_detay if x[3] in (2,6)][:40]: print('  ', x[0], x[2], x[4], x[5], x[6][:35], x[8])
