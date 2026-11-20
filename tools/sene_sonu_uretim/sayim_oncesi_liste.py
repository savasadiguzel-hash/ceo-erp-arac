"""Sayım öncesi muhasebe + üretim listesi (salt okuma). Basit, 3 sayfalık Excel üretir:
  1-Sayım Fazlası Girişi : muhasebenin tek fişle gireceği eksik kalemler (üretimi kapatmak için)
  2-Sayım Eksiği Çıkışı  : ERP'de fazla görünen kalemler (230016 iki kat düzeltmesi + SYM202600003 çakışması)
  3-Yapılacak Üretimler  : faturası kesilmiş ama ERP'de üretimi eksik olanlar + açık satış siparişlerine göre üretimler
Kullanım: python sayim_oncesi_liste.py <muhasebe_eksik_giris.xlsx> <recete_ikikat_yedek.json> <çıktı.xlsx>"""
import sys, io, json
from collections import defaultdict
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import stok_guncel_bakiyeleri, son_alis_fiyati_toplu

EKSIK_XLSX, IKIKAT_JSON, CIKTI = sys.argv[1], sys.argv[2], sys.argv[3]
SYM_HAREKET_ID = 744507          # SYM202600003 (muhasebenin 19.01.2026 tarihli sayım fazlası fişi)
c = get_connection(**DB_DEFAULTS); cur = c.cursor()

def kart_bilgi(kodlar):
    kodlar = list(kodlar)
    if not kodlar: return {}
    out = {}
    for i in range(0, len(kodlar), 500):
        p = kodlar[i:i + 500]
        cur.execute(f"""SELECT sk.Kodu, sk.Adi, b.StokBirimAciklama FROM StokKarti sk LEFT JOIN [CeoCommon].dbo.StokBirim b ON b.StokBirimID=sk.StokBirim
                        WHERE sk.Kodu IN ({','.join('?' * len(p))})""", *p)
        out.update({r[0]: ((r[1] or '').replace('\r', ' ').replace('\n', ' ').strip(), r[2] or '') for r in cur.fetchall()})
    return out

# ---------------- 1) Sayım fazlası girişi (eksik listeden, koda göre toplanmış) ----------------
wb_in = openpyxl.load_workbook(EKSIK_XLSX, data_only=True); ws_in = wb_in.worksheets[0]
giris = {}
for r in ws_in.iter_rows(min_row=2, values_only=True):
    if not r[3]: continue
    emir, _, mamul, kod, ad, birim, mik, _, fiyat = r[:9]
    emir = emir.replace('ŞİRKET.', '') if emir.startswith('ŞİRKET.') else '230093 (FAEM ×50)'
    g = giris.setdefault(kod, dict(ad=(ad or '').replace('\n', ' ').strip(), birim=birim, mik=0.0, fiyat=fiyat, emir=[]))
    g['mik'] += float(mik)
    if emir not in g['emir']: g['emir'].append(emir)
print(f'1) Sayım fazlası: {len(giris)} kalem')

# ---------------- 2) Sayım eksiği çıkışı (ERP'de fazla görünen) ----------------
yedek = json.load(open(IKIKAT_JSON, encoding='utf-8'))
iade = defaultdict(float)
for d in yedek['detay']: iade[d['IslemKartId']] += float(d['Miktar'])
cur.execute("SELECT d.IslemKartId, SUM(d.Miktar), MAX(d.BirimFiyat) FROM StokHareketDetay d WHERE d.HareketId=? AND d.Turu=1 GROUP BY d.IslemKartId", SYM_HAREKET_ID)
sym = {r[0]: (float(r[1]), float(r[2] or 0)) for r in cur.fetchall()}
ortak = [i for i in iade if i in sym]
cur.execute(f"SELECT Id, Kodu FROM StokKarti WHERE Id IN ({','.join(map(str, ortak))})")
id2kod = dict(cur.fetchall())
fazla_kodlar = [id2kod[i] for i in ortak]
fb = kart_bilgi(fazla_kodlar); fbak = stok_guncel_bakiyeleri(c, fazla_kodlar, '2099-12-31')
fazla = []
for i in ortak:
    k = id2kod[i]; dus = min(iade[i], sym[i][0])
    fazla.append(dict(kod=k, ad=fb[k][0], birim=fb[k][1], bak=fbak.get(k, 0), dus=dus, fiyat=sym[i][1]))
fazla.sort(key=lambda x: x['kod'])
print(f'2) Sayım eksiği: {len(fazla)} kalem')

# ---------------- 3) Yapılacak üretimler ----------------
cur.execute("SELECT DISTINCT Kodu FROM UretimRecete WHERE KullanimDisi IS NULL OR KullanimDisi=0")
receteli = {r[0] for r in cur.fetchall()}
cur.execute("""SELECT s.SiparisNo, s.SiparisTarihi, s.MusteriKartId, LTRIM(RTRIM(m.Unvani)), sk.Id, sk.Kodu, sd.Miktar, sd.KalanMiktar
 FROM StokSiparis s JOIN StokSiparisDetay sd ON sd.StokSiparisId=s.Id JOIN StokKarti sk ON sk.Id=sd.KartId AND sd.Turu='Stok'
 LEFT JOIN CariMusteriKarti m ON m.Id=s.MusteriKartId LEFT JOIN StokSiparisDurum d ON d.Id=s.SiparisDurumuId
 WHERE s.Turu='1' AND s.SiparisTarihi>='20260101' AND d.Aciklama=N'DEVAM EDİYOR' ORDER BY s.SiparisTarihi, s.SiparisNo""")
sip = cur.fetchall()
talep = defaultdict(list)          # ürün -> [(sipariş, tarih, müşteri, açık miktar)]
for no, tar, mid, unv, kid, kod, mik, kalan in sip:
    mik, kalan = float(mik), float(kalan if kalan is not None else mik)
    if kalan < mik - 1e-9: acik = kalan                        # sipariş faturaya bağlanmış, kalan güncel
    else:
        cur.execute("""SELECT SUM(shd.Miktar-ISNULL(f.Miktar,0)) FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId
          LEFT JOIN StokHareketDetay f ON f.Id=shd.FaturaDetayId WHERE shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1
          AND (sh.IslemKodu=2 OR (sh.IslemKodu=6 AND sh.FaturaId IS NULL)) AND sh.MusteriKartId=? AND shd.IslemKartId=? AND sh.BelgeTarihi>=?""", mid, kid, tar)
        acik = max(0.0, mik - float(cur.fetchone()[0] or 0))
    if acik > 1e-9: talep[kod].append((no, tar, unv or '', acik))

# Faturası kesilmiş, üretimi ERP'de eksik olanlar (önce bunlar) + üretim sonrası bakiyeye etkisi
FATURALI = [  # (emir/iş, müşteri, fatura, ürün, miktar, emir tarihi, durum, muhasebe girişi gerekir mi)
    ('ŞİRKET.1862026-10 (mevcut emir)', 'RSTEK', 'GEF2026000000029 (08.06.2026)', 'GMP-101-230030', 1, '07.06.2026', 'Muhasebe girişinden sonra kapatılacak', True),
    ('ŞİRKET.1862026-7 (mevcut emir)', 'RSTEK', 'GEF2026000000029 (08.06.2026)', 'GMP-101-230044', 1, '08.06.2026', 'Muhasebe girişinden sonra kapatılacak', True),
    ('ŞİRKET.1862026-8 (mevcut emir)', 'Unirobotics', 'GEF2026000000028 (04.06.2026)', 'GMP-101-230035', 5, '18.06.2026', 'Muhasebe girişinden sonra kapatılacak', True),
    ('Yeni emir açılacak', 'Ford Otomotiv', 'GEF2026000000070 (10.11.2026)', 'HAV-HPB0001', 43, '09.11.2026', 'HAZIR: malzeme yeterli, hemen açılıp kapatılabilir', False),
    ('Yeni emir açılacak', 'FAEM', 'GEF2026000000073 (13.11.2026)', 'GMP-101-230093', 50, '12.11.2026', 'Muhasebe girişinden sonra (7 sarf kalemi)', True),
]
uretim_sonrasi = defaultdict(float)
for x in FATURALI: uretim_sonrasi[x[3]] += x[4]

tum_urun = set(talep) | {x[3] for x in FATURALI} | {'GMP-101-230107'}
bak = stok_guncel_bakiyeleri(c, sorted(tum_urun), '2099-12-31')
kb = kart_bilgi(tum_urun)

# Reçete patlatma (çok seviyeli; YM önce stoktan, eksiği kendi reçetesinden üretilir), malzeme sırayla düşülür
_rec_cache = {}
def recete_girdileri(kod):
    if kod not in _rec_cache:
        cur.execute("""SELECT gk.Kodu, g.Miktar, h.Miktar FROM UretimRecete r JOIN UretimReceteHatPlani h ON h.UretimReceteId=r.Id AND h.Tipi=1
          JOIN StokKarti hk ON hk.Id=h.KartId AND hk.Kodu=r.Kodu JOIN UretimReceteHatPlaniGirdi g ON g.UretimReceteHatPlaniId=h.Id AND g.Tipi=1
          JOIN StokKarti gk ON gk.Id=g.KartId WHERE r.Kodu=? AND (r.KullanimDisi IS NULL OR r.KullanimDisi=0)""", kod)
        rows = cur.fetchall(); grup = defaultdict(list)
        for gk, gm, hm in rows: grup[(gk, float(gm))].append(float(hm or 1))
        out = defaultdict(float)
        for (gk, gm), lst in grup.items():
            n = len(lst)
            if kod == 'GMP-101-230107' and n % 2 == 0: n //= 2          # 230107 reçetesi iki kat yazılmış
            out[gk] += gm * n / lst[0]
        _rec_cache[kod] = dict(out)
    return _rec_cache[kod]

stok = {}
def bakiye(kod):
    if kod not in stok: stok[kod] = stok_guncel_bakiyeleri(c, [kod], '2099-12-31').get(kod, 0.0)
    return stok[kod]

def ihtiyac(kod, mik, eksik, derinlik=0):
    for gk, gm in recete_girdileri(kod).items():
        lazim = gm * mik; var = max(bakiye(gk), 0.0); kullan = min(var, lazim)
        stok[gk] = bakiye(gk) - kullan; kalan = lazim - kullan
        if kalan > 1e-9:
            if gk in receteli and derinlik < 4 and recete_girdileri(gk): ihtiyac(gk, kalan, eksik, derinlik + 1)
            else: eksik[gk] += kalan

# muhasebenin gireceği kalemler stokta varsayılır (1. sayfa)
for k, g in giris.items(): stok[k] = bakiye(k) + g['mik']
# önce faturalı işler (mevcut emirlerin girdileri muhasebe girişiyle karşılanıyor; yeni emirler reçeteden düşülür)
for x in FATURALI:
    if x[0].startswith('Yeni'): ihtiyac(x[3], x[4], defaultdict(float))

uretimler = []
for x in FATURALI:
    k = x[3]
    uretimler.append(dict(grup='A', is_=x[0], musteri=x[1], belge=x[2], kod=k, ad=kb.get(k, ('', ''))[0], mik=x[4], tarih=x[5],
                          bak=bak.get(k, 0), sonra=None, durum=x[6]))
sonra_ara = {}
for u in uretimler:
    sonra_ara[u['kod']] = sonra_ara.get(u['kod'], u['bak']) + u['mik']; u['sonra'] = sonra_ara[u['kod']]

# B) açık siparişler: ürün bazında toplam açık talep − (üretim sonrası) bakiye
oneri = []
for kod, lst in talep.items():
    if kod not in receteli: continue
    acik = sum(t[3] for t in lst)
    mevcut = bak.get(kod, 0) + uretim_sonrasi.get(kod, 0)
    if kod == 'GMP-101-230107': mevcut += 45          # 2082026-1 ×45 kapanınca
    uret = max(0.0, acik - max(mevcut, 0.0))
    if uret <= 1e-9: continue
    oneri.append((min(t[1] for t in lst), kod, lst, acik, mevcut, uret))
oneri.sort()
# 230107: mevcut açık emir 2082026-1 ile karşılanıyor → ayrı satır
lst107 = talep.get('GMP-101-230107', [])
if lst107:
    eksik = defaultdict(float); ihtiyac('GMP-101-230107', 45, eksik)
    uretimler.append(dict(grup='B', is_='ŞİRKET.2082026-1 (mevcut emir)', musteri=', '.join(sorted({t[2][:30] for t in lst107})),
        belge='Sipariş ' + ', '.join(str(t[0]) for t in lst107) + ' (fatura kesilecek)', kod='GMP-101-230107', ad=kb['GMP-101-230107'][0], mik=45,
        tarih='fatura tarihinden 1 gün önce', bak=bak.get('GMP-101-230107', 0), sonra=bak.get('GMP-101-230107', 0) + 45,
        durum=('Malzeme yeterli' if not eksik else f'{len(eksik)} kalem eksik') + '. Önce reçetedeki iki kat girdiler düzeltilmeli', eksik=eksik))
for tar, kod, lst, acik, mevcut, uret in oneri:
    eksik = defaultdict(float); ihtiyac(kod, uret, eksik)
    eski = any((t[1].year, t[1].month) < (2026, 9) for t in lst)
    uretimler.append(dict(grup='B', is_='Fatura kesilince emir açılacak', musteri=', '.join(sorted({t[2][:30] for t in lst})),
        belge='Sipariş ' + ', '.join(f'{t[0]} ({t[1]:%d.%m.%Y}, {t[3]:g})' for t in lst), kod=kod, ad=kb.get(kod, ('', ''))[0], mik=uret,
        tarih='fatura tarihinden 1 gün önce', bak=bak.get(kod, 0), sonra=mevcut + uret,
        durum=('Malzeme yeterli' if not eksik else f'{len(eksik)} kalem eksik') + ('. Eski sipariş: hâlâ geçerli mi teyit edin' if eski else ''), eksik=eksik))
receteisiz = [(kod, lst) for kod, lst in talep.items() if kod not in receteli and sum(t[3] for t in lst) > max(bak.get(kod, 0), 0)]
print(f'3) Üretim: {len(uretimler)} satır; reçetesiz yetersiz: {[k for k, _ in receteisiz]}')

# ---------------- Excel ----------------
wb = openpyxl.Workbook()
BAS = Font(bold=True, color='FFFFFF'); BASF = PatternFill('solid', fgColor='305496')
KALIN = Font(bold=True); BUYUK = Font(bold=True, size=13)
ince = Side(style='thin', color='BFBFBF'); KENAR = Border(left=ince, right=ince, top=ince, bottom=ince)
SARI = PatternFill('solid', fgColor='FFF2CC'); YESIL = PatternFill('solid', fgColor='E2EFDA'); KIRMIZI = PatternFill('solid', fgColor='FCE4D6')

def baslik_blok(ws, satirlar):
    for i, s in enumerate(satirlar, 1):
        ws.cell(i, 1, s).font = BUYUK if i == 1 else Font(size=11)
    return len(satirlar) + 2

def tablo(ws, r0, basliklar, veriler, genislik, sayi_kol=(), para_kol=()):
    for j, b in enumerate(basliklar, 1):
        h = ws.cell(r0, j, b); h.font = BAS; h.fill = BASF; h.alignment = Alignment(wrap_text=True, vertical='center'); h.border = KENAR
    for i, v in enumerate(veriler, 1):
        for j, x in enumerate(v, 1):
            cl = ws.cell(r0 + i, j, x); cl.border = KENAR; cl.alignment = Alignment(wrap_text=True, vertical='top')
            if j in sayi_kol: cl.number_format = '#,##0.##'
            if j in para_kol: cl.number_format = '#,##0.00 ₺'
    for j, w in enumerate(genislik, 1): ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    return r0 + len(veriler)

# Sayfa 1
ws = wb.active; ws.title = '1-Sayım Fazlası Girişi'
r0 = baslik_blok(ws, ['FİŞ 1: SAYIM FAZLASI (GİRİŞ) — tek fiş',
                      'Depo: MERKEZ (2)   |   Fiş tarihi: 06.06.2026 veya öncesi (en erken üretim emri 07.06.2026)',
                      'Neden: Bu malzemeler üretimde kullanıldı ama ERP\'ye girişi yapılmadı. Giriş olmadan üretim kayıtları kapanmıyor.',
                      'Birim fiyatı boş olan satırların ERP\'de alış kaydı yok; fiyatı muhasebe belirleyecek.'])
veri = []; top = 0.0
for n, (k, g) in enumerate(sorted(giris.items()), 1):
    tut = g['mik'] * g['fiyat'] if g['fiyat'] else None; top += tut or 0
    veri.append([n, k, g['ad'], g['birim'], g['mik'], round(g['fiyat'], 4) if g['fiyat'] else None, round(tut, 2) if tut else None, ', '.join(g['emir'])])
son = tablo(ws, r0, ['Sıra', 'Stok Kodu', 'Stok Adı', 'Birim', 'Miktar', 'Birim Fiyat (son alış)', 'Tutar', 'Kullanılacağı Üretim'], veri,
            [6, 22, 48, 8, 10, 14, 14, 26], sayi_kol=(5,), para_kol=(6, 7))
for i, v in enumerate(veri, 1):
    if v[5] is None: ws.cell(r0 + i, 6).fill = SARI; ws.cell(r0 + i, 7).fill = SARI
ws.cell(son + 2, 3, f'TOPLAM ({len(veri)} kalem, fiyatı olanlar)').font = KALIN
t = ws.cell(son + 2, 7, round(top, 2)); t.font = KALIN; t.number_format = '#,##0.00 ₺'
ws.cell(son + 3, 3, f'Fiyatı muhasebe tarafından belirlenecek: {sum(1 for v in veri if v[5] is None)} kalem (sarı)')

# Sayfa 2
ws = wb.create_sheet('2-Sayım Eksiği Çıkışı')
r0 = baslik_blok(ws, ['FİŞ 2: SAYIM EKSİĞİ (ÇIKIŞ) — tek fiş',
                      'Depo: MERKEZ (2)   |   Fiş tarihi: bugün veya sayımdan (30.11.2026) önce',
                      'Neden: Boresighter SP (230016) reçetesinde her girdi iki kez yazılıydı; 2026 üretimleri bu kalemleri iki kat tüketmişti.',
                      'Bu eksiyi kapatmak için SYM202600003 (19.01.2026) fişiyle giriş yapıldı. Reçete düzeltilince tüketim yarıya indi; bu kalemler artık ERP\'de fazla görünüyor.'])
veri = [[n, f['kod'], f['ad'], f['birim'], f['bak'], f['dus'], f['bak'] - f['dus'], round(f['fiyat'], 4), round(f['dus'] * f['fiyat'], 2)] for n, f in enumerate(fazla, 1)]
son = tablo(ws, r0, ['Sıra', 'Stok Kodu', 'Stok Adı', 'Birim', 'Bugünkü ERP Bakiyesi', 'Düşülecek Miktar', 'Düşüldükten Sonra', 'Birim Fiyat (SYM fişindeki)', 'Tutar'],
            veri, [6, 22, 48, 8, 12, 12, 12, 14, 14], sayi_kol=(5, 6, 7), para_kol=(8, 9))
ws.cell(son + 2, 3, f'TOPLAM ({len(veri)} kalem)').font = KALIN
t = ws.cell(son + 2, 9, round(sum(v[8] for v in veri), 2)); t.font = KALIN; t.number_format = '#,##0.00 ₺'
ws.cell(son + 3, 3, 'Not: Sayımda bu kalemlerin fiziki miktarı ayrıca doğrulanmalı. ":20" freze, ":60" kaplama operasyon kartlarıdır.')

# Sayfa 3
ws = wb.create_sheet('3-Yapılacak Üretimler')
r0 = baslik_blok(ws, ['YAPILACAK ÜRETİMLER — 27.11.2026\'ya kadar CEO\'da',
                      'A: Faturası kesilmiş ama üretim kaydı eksik olanlar (önce bunlar).  B: Açık satış siparişlerine göre, fatura kesilince yapılacaklar.',
                      'B grubundaki miktar = açık sipariş − mevcut stok. Emir, fatura tarihinden 1 gün önce tarihli açılır (fatura birebir).'])
veri = []
for n, u in enumerate(uretimler, 1):
    veri.append([n, u['grup'], u['is_'], u['musteri'], u['belge'], u['kod'], u['ad'], u['mik'], u['tarih'], u['bak'], u['sonra'], u['durum']])
son = tablo(ws, r0, ['Sıra', 'Grup', 'İş', 'Müşteri', 'Fatura / Sipariş', 'Ürün Kodu', 'Ürün Adı', 'Üretilecek', 'Emir Tarihi',
                     'Bugünkü Bakiye', 'Üretim Sonrası Bakiye', 'Durum'], veri, [6, 6, 26, 24, 34, 18, 34, 10, 14, 10, 12, 40], sayi_kol=(8, 10, 11))
for i, u in enumerate(uretimler, 1):
    fill = YESIL if ('HAZIR' in u['durum'] or u['durum'].startswith('Malzeme yeterli')) else (KIRMIZI if 'eksik' in u['durum'] else SARI)
    ws.cell(r0 + i, 12).fill = fill
r = son + 2
if receteisiz:
    ws.cell(r, 3, 'Reçetesi olmayan, stoğu yetmeyen sipariş kalemleri (üretim emri açılamaz, reçete gerekli):').font = KALIN; r += 1
    for kod, lst in receteisiz:
        ws.cell(r, 3, f"{kod} — {kart_bilgi([kod]).get(kod, ('',''))[0]} | sipariş {', '.join(f'{t[0]} {t[2][:25]} ×{t[3]:g}' for t in lst)} | bakiye {bak.get(kod, stok_guncel_bakiyeleri(c, [kod], '2099-12-31').get(kod, 0)):g}"); r += 1

# Eksik malzeme detayı (B grubu)
eks_veri = []
for u in uretimler:
    for gk, m in sorted(u.get('eksik', {}).items()): eks_veri.append([u['kod'], u['mik'], gk, m])
if eks_veri:
    ws2 = wb.create_sheet('3a-Üretim Eksik Malzeme')
    kb2 = kart_bilgi({v[2] for v in eks_veri})
    fiyat = son_alis_fiyati_toplu(c, sorted({v[2] for v in eks_veri}), [])
    r0 = baslik_blok(ws2, ['B grubu üretimler için eksik malzeme (satın alma / giriş gerekir)',
                           'Malzemeler üretim sırasıyla stoktan düşülerek hesaplandı; yarı mamulün eksiği kendi reçetesinden patlatıldı.'])
    rows = []
    for n, (urun, um, gk, m) in enumerate(eks_veri, 1):
        f = (fiyat.get(gk) or {}).get('fiyat')
        rows.append([n, urun, um, gk, kb2.get(gk, ('', ''))[0], kb2.get(gk, ('', ''))[1], round(m, 4), f, round(m * f, 2) if f else None])
    tablo(ws2, r0, ['Sıra', 'Ürün', 'Üretilecek', 'Eksik Malzeme Kodu', 'Malzeme Adı', 'Birim', 'Eksik Miktar', 'Son Alış Fiyatı', 'Tahmini Tutar'],
          rows, [6, 18, 10, 22, 46, 8, 12, 14, 14], sayi_kol=(3, 7), para_kol=(8, 9))
wb.save(CIKTI)
print('Kaydedildi:', CIKTI)
for u in uretimler: print(f"  {u['grup']} {u['kod']:16s} ×{u['mik']:g}  bak {u['bak']:g} → {u['sonra']:g} | {u['durum']} | {u['belge'][:70]}")
