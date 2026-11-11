import sys, io, pickle, re
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from collections import defaultdict
from config import DB_DEFAULTS
from db.baglanti import get_connection
d = pickle.load(open(sys.argv[1], 'rb')); OUT = sys.argv[2]
bak, ad, birim, bom, comp_tip = d['bak'], d['ad'], d['birim'], d['bom'], d['comp_tip']
def is_op(k): return comp_tip.get(k) == 'masraf' or k.count(':') == 1
recete = {k for k in bom if k in ad}
child = {p: {c: q for c, q in v.items() if not is_op(c)} for p, v in bom.items()}
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
GIR = {1,4,5,8,15,16,20,22,26,29}; CIK = {2,3,6,7,17,18,19,21,24,28}

def hareketler(kod):
    cur.execute("""
    SELECT sh.IslemKodu, sh.BelgeTarihi, ISNULL(sh.BelgeSeriNo,'')+ISNULL(CAST(sh.BelgeSiraNo AS VARCHAR(20)),''),
           ISNULL(cmk.Unvani,''), shd.Miktar-ISNULL(shd_f.Miktar,0), ISNULL(shd.Tutar,0), sh.Id
    FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId
    LEFT JOIN StokHareketDetay shd_f ON shd_f.Id=shd.FaturaDetayId
    JOIN StokKarti sk ON sk.Id=shd.IslemKartId LEFT JOIN CariMusteriKarti cmk ON cmk.Id=sh.MusteriKartId
    WHERE sk.Kodu=? AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL
      AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
    ORDER BY sh.BelgeTarihi, CASE WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29) THEN 0 ELSE 1 END, sh.Id""", kod)
    return [dict(ik=r[0], t=r[1], belge=r[2], cari=r[3], m=float(r[4] or 0), tutar=float(r[5] or 0), hid=r[6]) for r in cur.fetchall()]

# ── A) Geçmiş düzen: 2026 üretim emri tarihi vs aynı ürünün fatura tarihi (aynı cari kelimesi + miktar) ──
cur.execute("""SELECT ue.Kodu, ue.Aciklama, ue.UretimEmriTarihi, sk.Kodu, uehp.TalepMiktari, ue.DurumId
FROM UretimEmri ue JOIN UretimEmriHatPlani uehp ON uehp.UretimEmriId=ue.Id AND uehp.HatTipi=1
JOIN StokKarti sk ON sk.Id=uehp.KartId WHERE ue.UretimEmriTarihi>='2026-01-01'""")
emirler = cur.fetchall()
hcache = {}
desen = []
for ek, acik, et, uk, tm, dur in emirler:
    hs = hcache.setdefault(uk, hareketler(uk))
    satis = [h for h in hs if h['ik'] in (2, 6)]
    kel = [w for w in re.findall(r'\w{4,}', (acik or '').upper()) if w not in ad.get(uk, '').upper()]
    aday = [s for s in satis if abs(s['m'] - float(tm or 0)) < 1e-6 and any(w in s['cari'].upper() for w in kel)]
    aday.sort(key=lambda s: abs((s['t'] - et).days))
    uretim = [h for h in hs if h['ik'] == 16 and abs(h['m'] - float(tm or 0)) < 1e-6]
    uretim.sort(key=lambda s: abs((s['t'] - et).days))
    f = aday[0] if aday else None; u = uretim[0] if uretim else None
    desen.append((ek, acik, et.strftime('%d.%m.%Y'), uk, float(tm or 0), {3: 'Devam Ediyor', 5: 'Kapalı'}.get(dur, dur),
                  f['belge'] if f else '', f['t'].strftime('%d.%m.%Y') if f else '', (et - f['t']).days if f else None,
                  u['t'].strftime('%d.%m.%Y') if u else '', (u['t'] - f['t']).days if (u and f) else None))
fark = [x[8] for x in desen if x[8] is not None]; ufark = [x[10] for x in desen if x[10] is not None]
print('Eşleşen emir-fatura:', len(fark), '/', len(desen), ' emir-fatura gün farkı:', sorted(fark))
print('Üretim girişi - fatura gün farkı:', sorted(ufark))

# ── B) Eksi mamullerde eksiğin faturalara FIFO dağıtımı ──
neg_mamul = sorted([k for k, v in bak.items() if v < -1e-9 and (k in recete or k.startswith('GMP-101'))])
acik_satir = []   # karşılanmamış fatura satırları
for k in neg_mamul:
    hs = hcache.setdefault(k, hareketler(k))
    avail = 0.0; kuyruk = []   # [satış hareketi, karşılanmamış miktar]
    for h in hs:
        if h['ik'] in GIR:
            q = h['m']
            while q > 1e-9 and kuyruk:
                take = min(q, kuyruk[0][1]); kuyruk[0][1] -= take; q -= take
                if kuyruk[0][1] <= 1e-9: kuyruk.pop(0)
            avail += q
        elif h['ik'] in CIK:
            use = min(avail, h['m']); avail -= use
            if h['m'] - use > 1e-9: kuyruk.append([h, h['m'] - use])
    toplam = sum(q for _, q in kuyruk)
    assert abs(toplam + bak[k]) < 1e-6, (k, toplam, bak[k])
    for h, q in kuyruk:
        acik_satir.append(dict(kod=k, h=h, q=q))

# fatura (belge) bazında grupla → önerilen iş emri
emir_plan = defaultdict(list)
for s in acik_satir:
    emir_plan[(s['h']['belge'], s['h']['t'], s['h']['cari'], s['h']['ik'])].append(s)
plan_sirali = sorted(emir_plan.items(), key=lambda kv: kv[0][1])

# ── C) Her emir için kronolojik patlatma (eski fatura önce stoğu kullanır) ──
avail = {k: max(0.0, v) for k, v in bak.items()}
def patlat(kod, q, out, lvl):
    for cc, per in child.get(kod, {}).items():
        need = per * q
        use = min(avail.get(cc, 0.0), need); avail[cc] = avail.get(cc, 0.0) - use
        rest = need - use
        if cc in recete:
            if rest > 1e-9:
                out.append(('Yarı Mamul (HatTipi=2)', cc, rest, use, lvl))
                patlat(cc, rest, out, lvl + 1)
        else:
            out.append(('Malzeme', cc, need, use, lvl))

kisa = lambda cari: ' '.join(cari.split()[:3])
baslik_rows = []; satir_rows = []; eksik_tum = defaultdict(float)
for no, ((belge, t, cari, ik), satirlar) in enumerate(plan_sirali, 1):
    eno = f'PLAN-{no:02d}'
    eksik_say = 0; ym_say = 0; recetesiz = []
    for s in satirlar:
        k = s['kod']
        satir_rows.append((eno, belge, 'Mamul (HatTipi=1)', k, ad.get(k), birim.get(k), round(s['q'], 4), None, None, '' if k in recete else 'AKTİF REÇETE YOK'))
        if k not in recete: recetesiz.append(k); continue
        out = []; patlat(k, s['q'], out, 1)
        for tip, cc, need, use, lvl in out:
            if tip.startswith('Yarı'):
                ym_say += 1
                satir_rows.append((eno, belge, tip, cc, ad.get(cc), birim.get(cc), round(need, 4), None, None, f'{k} için'))
            else:
                ek = round(need - use, 4)
                if ek > 1e-9: eksik_say += 1; eksik_tum[cc] += ek
                satir_rows.append((eno, belge, '  Malzeme' + ('' if lvl == 1 else f' (seviye {lvl})'), cc, ad.get(cc), birim.get(cc), round(need, 4), round(use, 4), ek if ek > 1e-9 else None, ''))
    urunler = ', '.join(f"{s['kod']} x{s['q']:g}" for s in satirlar)
    ana_ad = ad.get(satirlar[0]['kod'], '').strip()
    oneri_acik = f"{ana_ad} {kisa(cari)}".upper()
    durum = 'REÇETE AÇILMALI' if recetesiz else ('MALZEME EKSİK' if eksik_say else 'HAZIR — mevcut stokla üretilebilir')
    tutar = sum(s['h']['tutar'] * s['q'] / s['h']['m'] for s in satirlar if s['h']['m'])
    baslik_rows.append((eno, t.strftime('%d.%m.%Y'), {2: 'Satış Faturası', 6: 'Satış İrsaliyesi', 17: 'Üretime Çıkış'}.get(ik, ik), belge, cari, urunler,
                        round(tutar, 2), oneri_acik, ym_say, eksik_say, durum))

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
wb = openpyxl.load_workbook(OUT)
for n in [s for s in wb.sheetnames if s.startswith(('9-', '10-', '11-'))]: del wb[n]
H = Font(bold=True, color='FFFFFF'); HF = PatternFill('solid', fgColor='375623')
FILL = {'HAZIR': 'C6EFCE', 'MALZEME': 'FFEB9C', 'REÇETE': 'F8CBAD'}
def sheet(name, cols, rows, widths, renk=None):
    ws = wb.create_sheet(name); ws.append(cols)
    for cell in ws[1]: cell.font = H; cell.fill = HF; cell.alignment = Alignment(wrap_text=True, vertical='center')
    for r in rows:
        ws.append(list(r))
        if renk:
            f = renk(r)
            if f:
                for cell in ws[ws.max_row]: cell.fill = PatternFill('solid', fgColor=f)
    ws.freeze_panes = 'B2'; ws.auto_filter.ref = ws.dimensions
    for i, w in enumerate(widths, 1): ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
sheet('9-İş Emri Planı (Fatura)', ['Plan No','Fatura Tarihi','Belge Türü','Belge No','Cari','Üretilecek Mamul(ler) x Miktar','Karşılanmamış Satış Tutarı','Önerilen Emir Açıklaması','Yarı Mamul Satırı','Eksik Malzeme Sayısı','Durum'],
      baslik_rows, [9,11,13,18,40,40,14,55,9,9,30], renk=lambda r: FILL[r[10].split()[0].rstrip('—')] if r[10].split()[0] in FILL else None)
sheet('10-İş Emri Satırları', ['Plan No','Belge No','Satır Tipi','Kod','Ad','Birim','İhtiyaç','Stoktan Karşılanan','EKSİK','Not'],
      satir_rows, [9,18,24,18,40,7,10,10,10,25], renk=lambda r: ('F8CBAD' if r[8] else None) if r[2].strip().startswith('Malzeme') else ('DDEBF7' if r[2].startswith('Mamul') else 'E2EFDA'))
sheet('11-Geçmiş Emir-Fatura Düzeni', ['Emir Kodu','Açıklama','Emir Tarihi','Ürün','Talep Miktarı','Durum','Eşleşen Fatura','Fatura Tarihi','Emir − Fatura (gün)','Üretim Girişi Tarihi','Üretim − Fatura (gün)'],
      sorted(desen, key=lambda x: x[2][6:] + x[2][3:5] + x[2][:2]), [18,50,11,16,9,12,18,11,10,12,10])
wb.save(OUT)

print('\nPLAN:')
for r in baslik_rows: print(' ', r[0], r[1], r[3], r[4][:30], '|', r[5], '|', f'{r[6]:,.0f}', '| YM', r[8], 'eksik', r[9], '|', r[10])
print('\nDesen örnek:'); [print(' ', x) for x in desen[:48]]
