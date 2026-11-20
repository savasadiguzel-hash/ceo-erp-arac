"""2026 satış faturaları (reçeteli mamuller) ↔ üretim emirleri (Devam Ediyor=3 / Tamamlandı=5) uyum kontrolü. Salt okuma.
Kullanım: python fatura_emir_uyum.py <çıktı.xlsx> [başlangıç YYYYMMDD, vars. 20260101]
Eşleştirme sırası:
  1) Emrin SurecDipnot'unda fatura no geçiyor                                  → 'Fatura no ile'
  2) Aynı ürün + emir açıklamasında cari adı + emir tarihi [fatura−90g, fatura+15g]
     + miktar tek faturaya ya da aynı carinin ardışık faturalarının toplamına eşit → 'Cari + miktar'
     miktar farklıysa                                                           → 'Cari, miktar farklı'
  3) Cari adı yok ama aynı ürün + aynı miktar + tarih penceresi                 → 'Olası (cari adı yok)'
Kalanlar: 'EMİR YOK' (fatura) / 'FATURASIZ EMİR' (emir)."""
import sys, io, re
from collections import defaultdict
from datetime import timedelta
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from config import DB_DEFAULTS
from db.baglanti import get_connection

OUT = sys.argv[1]; BAS = sys.argv[2] if len(sys.argv) > 2 else '20260101'
GERI, ILERI = 90, 15
c = get_connection(**DB_DEFAULTS); cur = c.cursor()

TR = str.maketrans('ıiğüşöçİĞÜŞÖÇ', 'IIGUSOCIGUSOC')
def norm(s): return re.sub(r'[^A-Z0-9 ]', ' ', (s or '').upper().translate(TR))
STOP = set('LTD STI SAN TIC AS A S VE ELEKTRONIK ELEKTRIK BELEDIYE BELEDIYESI BASKANLIGI SIRKETI LIMITED ANONIM SIST SISTEMLERI '
           'INS OTOM TI IC DIS VE TAAHHUT TEKNOLOJI TEKNOLOJILERI URUNLERI GUVENLIK BILGISAYAR MUH MUHENDISLIK SAVUNMA SANAYI TICARET'.split())
def tokenler(unvan):
    return [w for w in norm(unvan).split() if len(w) >= 3 and w not in STOP][:3]

cur.execute("SELECT DISTINCT Kodu FROM UretimRecete WHERE KullanimDisi IS NULL OR KullanimDisi=0")
receteli = {r[0] for r in cur.fetchall()}

# Faturalar (satır = fatura+ürün)
cur.execute("""SELECT sh.Id, RTRIM(ISNULL(sh.BelgeSeriNo,''))+CAST(sh.BelgeSiraNo AS varchar), sh.IslemKodu, sh.BelgeTarihi, m.Unvani, sk.Id, sk.Kodu, LEFT(sk.Adi,45),
       SUM(shd.Miktar-ISNULL(f.Miktar,0)), SUM(shd.Tutar)
 FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId LEFT JOIN StokHareketDetay f ON f.Id=shd.FaturaDetayId
 JOIN StokKarti sk ON sk.Id=shd.IslemKartId LEFT JOIN CariMusteriKarti m ON m.Id=sh.MusteriKartId
 WHERE shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND (sh.IslemKodu=2 OR (sh.IslemKodu=6 AND sh.FaturaId IS NULL)) AND sh.BelgeTarihi>=?
 GROUP BY sh.Id, sh.BelgeSeriNo, sh.BelgeSiraNo, sh.IslemKodu, sh.BelgeTarihi, m.Unvani, sk.Id, sk.Kodu, sk.Adi""", BAS)
tum = cur.fetchall()
fat = [dict(hid=r[0], no=r[1], tur='Fatura' if r[2] == 2 else 'İrsaliye', tarih=r[3], cari=(r[4] or '').strip(), kid=r[5], kod=r[6], ad=(r[7] or '').strip(),
            miktar=float(r[8] or 0), tutar=float(r[9] or 0), esles=None, emir=None, not_='') for r in tum if r[6] in receteli]
receteSiz = defaultdict(float)
for r in tum:
    if r[6] not in receteli: receteSiz[(r[6], (r[7] or '').strip())] += float(r[8] or 0)

# Emirler (satır = emir+ana ürün)
bas_emir = BAS   # yalnız 2026 emirleri (kullanıcı: 2025 kapsam dışı)
cur.execute("""SELECT ue.Id, ue.Kodu, ue.Aciklama, ue.UretimEmriTarihi, ue.DurumId, ISNULL(ue.SurecDipnot,''), hk.Id, hk.Kodu, SUM(h.TalepMiktari),
   (SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x JOIN UretimEmriHatPlani hh ON hh.Id=x.UretimEmriHatPlaniId WHERE hh.UretimEmriId=ue.Id)
 FROM UretimEmri ue JOIN UretimEmriHatPlani h ON h.UretimEmriId=ue.Id JOIN StokKarti hk ON hk.Id=h.KartId
 WHERE ue.DurumId IN (3,5) AND h.HatTipi=1 AND ue.UretimEmriTarihi>=?
 GROUP BY ue.Id, ue.Kodu, ue.Aciklama, ue.UretimEmriTarihi, ue.DurumId, ue.SurecDipnot, hk.Id, hk.Kodu""", bas_emir)
emr = [dict(id=r[0], kodu=r[1], acik=(r[2] or '').strip(), tarih=r[3], durum={3: 'Devam Ediyor', 5: 'Tamamlandı'}[r[4]], dipnot=r[5], kid=r[6], kod=r[7],
            miktar=float(r[8] or 0), hareket=r[9], kalan=float(r[8] or 0), faturalar=[]) for r in cur.fetchall()]

def bagla(f, e, tip, miktar):
    f['esles'] = tip; f['emir'] = e; e['kalan'] -= miktar; e['faturalar'].append((f['no'], miktar, tip))

# 1) Fatura no ile
for e in emr:
    for f in fat:
        if f['esles'] is None and f['kid'] == e['kid'] and f['no'] and f['no'] in e['dipnot']:
            bagla(f, e, 'Fatura no ile', f['miktar'])

def pencere(f, e): return f['tarih'] - timedelta(days=GERI) <= e['tarih'] <= f['tarih'] + timedelta(days=ILERI)
def cari_uyar(f, e):
    a = norm(e['acik']); return any(t in a.split() or (len(t) >= 5 and t in a) for t in tokenler(f['cari']))

# 2a) Cari + tek fatura miktarı birebir
for f in sorted(fat, key=lambda x: x['tarih']):
    if f['esles']: continue
    ad = [e for e in emr if e['kid'] == f['kid'] and not e['faturalar'] and abs(e['kalan'] - f['miktar']) < 1e-6 and pencere(f, e) and cari_uyar(f, e)]
    if ad: bagla(f, min(ad, key=lambda e: abs((f['tarih'] - e['tarih']).days)), 'Cari + miktar', f['miktar'])
# 2b) Cari + ardışık faturaların toplamı = emir miktarı
for e in sorted(emr, key=lambda x: x['tarih']):
    if e['faturalar']: continue
    ad = sorted([f for f in fat if f['esles'] is None and f['kid'] == e['kid'] and pencere(f, e) and cari_uyar(f, e) and f['tarih'] >= e['tarih'] - timedelta(days=5)],
                key=lambda f: f['tarih'])
    for i in range(len(ad)):
        s = 0
        for j in range(i, len(ad)):
            s += ad[j]['miktar']
            if abs(s - e['miktar']) < 1e-6 and j > i:
                for f in ad[i:j+1]: bagla(f, e, 'Cari + miktar (çok fatura)', f['miktar'])
                break
            if s > e['miktar']: break
        if e['faturalar']: break
# 2c) Cari tutuyor, miktar farklı
for f in sorted(fat, key=lambda x: x['tarih']):
    if f['esles']: continue
    ad = [e for e in emr if e['kid'] == f['kid'] and not e['faturalar'] and pencere(f, e) and cari_uyar(f, e)]
    if ad:
        e = min(ad, key=lambda e: abs((f['tarih'] - e['tarih']).days)); bagla(f, e, 'Cari, miktar farklı', f['miktar'])
        f['not_'] = f"emir {e['miktar']:g} / fatura {f['miktar']:g}"
# 3) Olası: cari adı yok, ürün + miktar + pencere
for f in sorted(fat, key=lambda x: x['tarih']):
    if f['esles']: continue
    ad = [e for e in emr if e['kid'] == f['kid'] and not e['faturalar'] and abs(e['miktar'] - f['miktar']) < 1e-6 and pencere(f, e)]
    if ad: bagla(f, min(ad, key=lambda e: abs((f['tarih'] - e['tarih']).days)), 'Olası (cari adı yok)', f['miktar'])
for f in fat:
    if not f['esles']: f['esles'] = 'EMİR YOK'

# Rapor
RENK = {'Fatura no ile': 'C6EFCE', 'Cari + miktar': 'C6EFCE', 'Cari + miktar (çok fatura)': 'C6EFCE', 'Cari, miktar farklı': 'FFEB9C',
        'Olası (cari adı yok)': 'FFEB9C', 'EMİR YOK': 'FFC7CE', 'FATURASIZ EMİR': 'FFC7CE'}
wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Faturalar'
H = ['Fatura Tarihi', 'Belge No', 'Tür', 'Cari', 'Stok Kodu', 'Stok Adı', 'Miktar', 'Tutar', 'EŞLEŞME', 'Emir', 'Emir Tarihi', 'Emir Durumu',
     'Emir Miktarı', 'Emir Açıklaması', 'Not']
def baslik(ws, H, renk='1F4E78'):
    ws.append(H)
    for cl in ws[1]: cl.font = Font(bold=True, color='FFFFFF'); cl.fill = PatternFill('solid', fgColor=renk); cl.alignment = Alignment(wrap_text=True)
baslik(ws, H)
for f in sorted(fat, key=lambda x: (x['tarih'], x['no'])):
    e = f['emir']
    ws.append([f['tarih'].strftime('%d.%m.%Y'), f['no'], f['tur'], f['cari'], f['kod'], f['ad'], f['miktar'], round(f['tutar'], 2), f['esles'],
               e['kodu'] if e else '', e['tarih'].strftime('%d.%m.%Y') if e else '', e['durum'] if e else '', e['miktar'] if e else '', e['acik'][:70] if e else '', f['not_']])
    ws.cell(ws.max_row, 9).fill = PatternFill('solid', fgColor=RENK[f['esles']])
for col, w in zip('ABCDEFGHIJKLMNO', [11, 18, 8, 38, 18, 38, 8, 12, 24, 20, 11, 13, 8, 50, 22]): ws.column_dimensions[col].width = w
ws.freeze_panes = 'C2'; ws.auto_filter.ref = ws.dimensions

ws2 = wb.create_sheet('Emirler')
baslik(ws2, ['Emir', 'Emir Tarihi', 'Durum', 'Stok Kodu', 'Emir Miktarı', 'Faturalarla Eşleşen', 'Fark', 'Hareket Var', 'Açıklama', 'Eşleşen Faturalar', 'SONUÇ'])
faturasiz = []
for e in sorted(emr, key=lambda x: x['tarih']):
    es = sum(m for _, m, _ in e['faturalar']); fark = round(e['miktar'] - es, 4)
    sonuc = 'FATURASIZ EMİR' if not e['faturalar'] else ('Uyumlu' if abs(fark) < 1e-6 else 'Miktar farklı')
    if sonuc == 'FATURASIZ EMİR': faturasiz.append(e)
    ws2.append([e['kodu'], e['tarih'].strftime('%d.%m.%Y'), e['durum'], e['kod'], e['miktar'], es, fark, 'Evet' if e['hareket'] else '',
                e['acik'][:80], '; '.join(f'{n} ({m:g}, {t})' for n, m, t in e['faturalar']), sonuc])
    ws2.cell(ws2.max_row, 11).fill = PatternFill('solid', fgColor={'Uyumlu': 'C6EFCE', 'Miktar farklı': 'FFEB9C', 'FATURASIZ EMİR': 'FFC7CE'}[sonuc])
for col, w in zip('ABCDEFGHIJK', [20, 11, 13, 18, 8, 8, 7, 8, 55, 60, 16]): ws2.column_dimensions[col].width = w
ws2.freeze_panes = 'B2'; ws2.auto_filter.ref = ws2.dimensions

ws3 = wb.create_sheet('Reçetesiz Satışlar')
baslik(ws3, ['Stok Kodu', 'Stok Adı', '2026 Satış Miktarı'])
for (k, a), m in sorted(receteSiz.items()): ws3.append([k, a, m])
for col, w in zip('ABC', [22, 50, 12]): ws3.column_dimensions[col].width = w
wb.save(OUT)

say = defaultdict(int)
for f in fat: say[f['esles']] += 1
print(f'fatura satırı (reçeteli): {len(fat)}  | emir satırı: {len(emr)}')
for k, v in sorted(say.items(), key=lambda x: -x[1]): print(f'  {k}: {v}')
print('\nEMİR YOK:')
for f in sorted(fat, key=lambda x: x['tarih']):
    if f['esles'] == 'EMİR YOK': print(f"  {f['tarih']:%d.%m.%Y} {f['no']:18s} {f['cari'][:32]:32s} {f['kod']:16s} {f['miktar']:g}")
print('\nSARI (kontrol):')
for f in sorted(fat, key=lambda x: x['tarih']):
    if f['esles'] in ('Cari, miktar farklı', 'Olası (cari adı yok)'):
        print(f"  {f['tarih']:%d.%m.%Y} {f['no']:18s} {f['cari'][:28]:28s} {f['kod']:16s} {f['miktar']:g} ↔ {f['emir']['kodu']} {f['emir']['miktar']:g} [{f['esles']}] {f['emir']['acik'][:40]}")
print('\nFATURASIZ EMİR:')
for e in faturasiz: print(f"  {e['kodu']:20s} {e['tarih']:%d.%m.%Y} {e['durum']:12s} {e['kod']:16s} {e['miktar']:g} | {e['acik'][:60]}")
print('\nreçetesiz satılan kalem:', len(receteSiz))
