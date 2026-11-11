import sys, pickle
sys.path.insert(0, r'C:\yeni-erp')
from collections import defaultdict
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import son_alis_fiyati_toplu
d = pickle.load(open(sys.argv[1], 'rb')); OUT = sys.argv[2]
bom, bak, ad, birim = d['bom'], d['bak'], d['ad'], d['birim']
comp_tip = d['comp_tip']
def is_op(k): return comp_tip.get(k) == 'masraf' or k.count(':') == 1
recete = {k for k in bom if k in ad}          # stok kartı olan reçeteler
child = {p: {c: q for c, q in v.items() if not is_op(c)} for p, v in bom.items()}
ops   = {p: {c: q for c, q in v.items() if is_op(c)} for p, v in bom.items()}
used_in = defaultdict(set)
for p, v in child.items():
    for c in v: used_in[c].add(p)

# Low-level code (cycle guard)
llc = defaultdict(int); cyc = []
def walk(k, lvl, path):
    if k in path: cyc.append(path + [k]); return
    if lvl <= llc[k] and lvl > 0: return
    llc[k] = max(llc[k], lvl)
    for c in child.get(k, {}): walk(c, lvl + 1, path + [k])
for k in recete:
    if not used_in[k]: walk(k, 0, [])
for k in recete: llc.setdefault(k, 0)
allk = set(recete) | {c for v in child.values() for c in v}
order = sorted(allk, key=lambda k: llc[k])

dep = defaultdict(float); kaynak = defaultdict(set); prod = {}; link = []
for k in order:
    b = bak.get(k, 0.0)
    if b < -1e-9 and k in recete: kaynak[k].add(k)
    if k in recete:
        p = max(0.0, dep[k] - b)
        prod[k] = p
        if p > 1e-9:
            for c, q in child[k].items():
                dep[c] += q * p; kaynak[c] |= (kaynak[k] or {k})
                link.append((k, c, q, p, q * p))
eksik = {k: max(0.0, dep[k] - bak.get(k, 0.0)) for k in allk | {k for k, v in bak.items() if v < 0}}
for k, v in bak.items():
    if v < -1e-9 and k not in recete and not dep.get(k): kaynak[k].add('(kendi eksi bakiyesi)')

uret = [k for k in recete if prod.get(k, 0) > 1e-9]
alis = [k for k, e in eksik.items() if e > 1e-9 and k not in recete and not is_op(k)]

c = get_connection(**DB_DEFAULTS); cur = c.cursor()
fiyat = son_alis_fiyati_toplu(c, alis, [])
cur.execute("""SELECT sk.Kodu, SUM(ISNULL(g.TalepMiktar,0)) FROM UretimEmri ue
JOIN UretimEmriHatPlani h ON h.UretimEmriId=ue.Id JOIN UretimEmriHatPlaniGirdi g ON g.UretimEmriHatPlaniId=h.Id
JOIN StokKarti sk ON sk.Id=g.KartId WHERE ue.DurumId=3 AND h.HatTipi IN (1,2) AND g.TalepMiktar>0 GROUP BY sk.Kodu""")
acik_talep = {k: float(v) for k, v in cur.fetchall()}
acik_urun = defaultdict(list)
for r in d['acik']:
    if r[3] == '1' and r[4]: acik_urun[r[4]].append(r[0])

# eksik bileşeni olan (bloke) reçeteler: alt ağaçta satınalma eksiği var mı
def alt_eksik(k, seen=None):
    seen = seen or set(); out = set()
    for cc in child.get(k, {}):
        if cc in seen: continue
        seen.add(cc)
        if cc in recete:
            if prod.get(cc, 0) > 1e-9: out |= alt_eksik(cc, seen)
        elif eksik.get(cc, 0) > 1e-9: out.add(cc)
    return out

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
wb = openpyxl.Workbook()
H = Font(bold=True, color='FFFFFF'); HF = PatternFill('solid', fgColor='305496')
def sheet(name, cols, rows, widths=None):
    ws = wb.create_sheet(name); ws.append(cols)
    for cell in ws[1]: cell.font = H; cell.fill = HF; cell.alignment = Alignment(wrap_text=True, vertical='center')
    for r in rows: ws.append(list(r))
    ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
    for i, w in enumerate(widths or [], 1): ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    return ws
def tur(k): return 'Mamul' if not used_in[k] else 'Yarı Mamul'
# 1 Üretilecek
rows = []
for k in sorted(uret, key=lambda k: (-llc[k], k)):
    ae = alt_eksik(k)
    rows.append((llc[k], k, ad.get(k), tur(k), birim.get(k), round(bak.get(k,0),2), round(max(0,-bak.get(k,0)),2),
                 round(dep[k],2), round(prod[k],2), len(child[k]), len(ops[k]), len(ae),
                 'EVET' if not ae else 'HAYIR — eksik bileşen', ', '.join(sorted(ae))[:300],
                 ', '.join(sorted(kaynak[k] - {k})), d['son_uretim'].get(k, ('',))[0], ', '.join(acik_urun.get(k, []))))
sheet('1-Üretilecek Reçeteler', ['Seviye (büyük=önce üret)','Kod','Ad','Tür','Birim','ERP Bakiye','Kendi Eksisi','Üst Ürün Talebi','ÜRETİLECEK MİKTAR','Stok Bileşen Sayısı','Operasyon/Masraf Sayısı','Eksik Hammadde Sayısı (alt ağaç)','Mevcut Stokla Üretilebilir mi','Eksik Hammaddeler','Talebi Doğuran Üst Ürün(ler)','Son Üretim Tarihi','Açık Üretim Emri'], rows,
      [9,18,40,11,7,10,10,11,12,9,9,10,18,50,35,12,20])
NOT = {}
for k in ['GMP-101-230093','GMP-101-230094','GMP-101-230111']:
    NOT[k] = 'SATILAN MAMUL - AKTIF RECETESI YOK; once recete acilmali, sonra uretilmeli'
for k in ['GMP-200-260041','GMP-200-230290','GMP-200-240509','GMP-200-240506','GMP-200-240677']:
    NOT[k] = 'Ic imalat parcasi (:XX operasyon karti var) ama recetesi yok - recete/hammadde tanimlanmali'
for k in ['GMP-200-240570','GMP-200-240602','GMP-110-230030','GMP-110-230031']:
    NOT[k] = 'Hic hareketi yok, recetesi yok - kaynagi (alis/imalat) netlestirilmeli'
for k in ['HMPUL00001','AKTRMİK0011','HMGMDDAL003','HMGMTRAKÜ09','GMP-200-240293']:
    NOT[k] = 'Uretimle ilgisiz eksi bakiye - alis kaydi eksik veya sayim duzeltmesi'
# 2 Satınalma eksikleri
rows = []; top = 0
for k in sorted(alis, key=lambda k: -eksik[k]):
    f = fiyat.get(k); tut = round(f['fiyat']*eksik[k], 2) if f else None; top += tut or 0
    rows.append((k, ad.get(k), birim.get(k), round(bak.get(k,0),2), round(dep.get(k,0),2), round(eksik[k],2),
                 'Kendi eksi bakiyesi' if not dep.get(k) else ('Eksi bakiye + üretim ihtiyacı' if bak.get(k,0)<0 else 'Üretim ihtiyacı'),
                 f['fiyat'] if f else None, f['tarih'] if f else 'alış yok', tut, round(acik_talep.get(k,0),2) or None,
                 ', '.join(sorted(kaynak[k]))[:300], NOT.get(k, '')))
sheet('2-Eksik Hammadde-Parça', ['Kod','Ad','Birim','ERP Bakiye','Üretim İçin İhtiyaç','EKSİK MİKTAR','Eksiğin Sebebi','Son Alış Fiyatı','Son Alış Tarihi','Tahmini Tutar','Açık Emir Talebi (ek)','Hangi Ürün(ler) İçin','Not'], rows,
      [18,40,7,10,11,11,24,11,11,12,11,50,45])
# 3 Patlatma detay
sheet('3-Patlatma Detayı', ['Üst Kod','Üst Ad','Alt Kod','Alt Ad','Birim Miktar','Üst Üretim','Alt İhtiyaç','Alt Bakiye','Alt Reçeteli mi'],
      [(p, ad.get(p), cc, ad.get(cc), q, round(pp,2), round(n,2), round(bak.get(cc,0),2), 'EVET' if cc in recete else '') for p, cc, q, pp, n in link],
      [18,35,18,35,9,9,10,10,9])
# 4 Negatif kartlar
ISL = {1:'Alış Fat',2:'Satış Fat',4:'Sayım Fazlası',5:'Alış İrs',6:'Satış İrs',7:'Sayım Eksiği',16:'Üretimden Giriş',17:'Üretime Çıkış'}
rows = []
for k in sorted([k for k,v in bak.items() if v < -1e-9], key=lambda k: bak[k]):
    oz = d['islem_ozet'].get(k, {})
    rows.append((k, ad.get(k), birim.get(k), round(bak[k],2), 'REÇETELİ' if k in recete else ('Operasyon' if is_op(k) else 'Reçetesiz'),
                 len(used_in[k]), d['son_hareket'].get(k), '; '.join(f"{ISL.get(int(i), 'Kod '+str(i))}: {round(m,2):g}" for i, m in sorted(oz.items()))))
sheet('4-Tüm Eksi Bakiyeli Kartlar', ['Kod','Ad','Birim','ERP Bakiye','Tür','Kaç Reçetede Bileşen','Son Hareket','Hareket Özeti (işlem kodu: miktar)'], rows, [18,40,7,10,11,9,11,90])
# 5 Açık emirler
sheet('5-Açık Üretim Emirleri', ['Emir Kodu','Açıklama','Tarih','HatTipi','Kart','Kart Adı','Miktar'],
      [(r[0], r[1], r[2][:10], r[3], r[4], ad.get(r[4]), r[5]) for r in d['acik']], [18,40,11,7,18,40,8])
# 0 Özet
ws = wb['Sheet']; ws.title = 'Ozet'
neg_rec = [k for k,v in bak.items() if v<0 and k in recete]
ozet = [('Analiz tarihi', '2026-11-11 (ERP canli, salt okuma)'),
 ('Aktif recete sayisi (stok kartli)', len(recete)), ('Eksi bakiyeli toplam kart', sum(1 for v in bak.values() if v<-1e-9)),
 ('  - receteli (dogrudan uretilecek)', len(neg_rec)),
 ('Uretilmesi gereken toplam recete (kademeli, yari mamul dahil)', len(uret)),
 ('  - mamul', sum(1 for k in uret if not used_in[k])), ('  - yari mamul', sum(1 for k in uret if used_in[k])),
 ('  - mevcut stokla hemen uretilebilir', sum(1 for k in uret if not alt_eksik(k))),
 ('Eksik hammadde/parca kalemi', len(alis)), ('  - fiyati bulunamayan', sum(1 for k in alis if k not in fiyat)),
 ('Tahmini satinalma tutari (son alis fiyati, doviz ayrimi yok)', round(top, 2)),
 ('BOM dongusu', len(cyc))]
for r in ozet: ws.append(r)
ws.column_dimensions['A'].width = 62; ws.column_dimensions['B'].width = 40
for cell in ws['A']: cell.font = Font(bold=True)
wb.save(OUT)
import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
for r in ozet: print(r)
print('cycles', cyc[:3])
print('\nURET:')
for k in sorted(uret, key=lambda k:(-llc[k],k)):
    print(' ', llc[k], k, round(prod[k],2), tur(k), round(bak.get(k,0),2), 'eksik_alt:', len(alt_eksik(k)), (ad.get(k) or '')[:40], '| kaynak', sorted(kaynak[k]-{k}))
print('\nALIS:')
for k in sorted(alis, key=lambda k:-eksik[k]):
    print(' ', k, round(eksik[k],2), birim.get(k), 'bak', round(bak.get(k,0),2), 'dep', round(dep.get(k,0),2), fiyat.get(k), (ad.get(k) or '')[:40], '|', sorted(kaynak[k])[:4])
