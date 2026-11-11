"""Açılan emirler tamamlandığında stok bakiyelerinin ne olacağını hesaplar; eksiye düşen alt malzemeleri muhasebe için Excel'e döker.
Salt okuma. Kullanım: python muhasebe_eksi_liste.py <çıktı.xlsx>
Kapsam: SurecDipnot'unda 'Fatura:' geçen (bu çalışmayla açılan) Devam Ediyor emirler + EK_EMIRLER (fatura için düzeltilen yerel emir)."""
import sys, io
from collections import defaultdict
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import stok_guncel_bakiyeleri, son_alis_fiyati_toplu, birimleri_getir
EK_EMIRLER = ['ŞİRKET.1092026-3']
OUT = sys.argv[1]
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
bir = {str(g).casefold().strip('{}'): n for n, g in birimleri_getir(c).items()}

cur.execute(f"""SELECT ue.Kodu, ue.Aciklama, CONVERT(varchar(10),ue.UretimEmriTarihi,104), h.Id, h.HatTipi, sk.Kodu, h.TalepMiktari,
   (SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
 FROM UretimEmri ue JOIN UretimEmriHatPlani h ON h.UretimEmriId=ue.Id JOIN StokKarti sk ON sk.Id=h.KartId
 WHERE ue.DurumId=3 AND (ue.SurecDipnot LIKE 'Fatura:%' OR ue.Kodu IN ({','.join('?'*len(EK_EMIRLER))}))""", *EK_EMIRLER)
hatlar = cur.fetchall()
emirler = sorted({h[0] for h in hatlar})
uretim = defaultdict(float); tuketim = defaultdict(float); kaynak = defaultdict(set); ad = {}
for ek, eac, et, hid, htip, hkod, htalep, hhar in hatlar:
    if hhar: continue                       # zaten tamamlanmış hat (stoğa yansımış)
    uretim[hkod] += float(htalep or 0)
    cur.execute("""SELECT sk.Kodu, sk.Adi, SUM(g.TalepMiktar) FROM UretimEmriHatPlaniGirdi g JOIN StokKarti sk ON sk.Id=g.KartId
      WHERE g.UretimEmriHatPlaniId=? AND g.Tipi<>2 GROUP BY sk.Kodu, sk.Adi""", hid)
    for k, a, t in cur.fetchall():
        tuketim[k] += float(t or 0); kaynak[k].add(ek); ad[k] = (a or '').strip()
kodlar = sorted(set(uretim) | set(tuketim))
bakiye = stok_guncel_bakiyeleri(c, kodlar)
cur.execute(f"SELECT Kodu, Adi, StokBirim FROM StokKarti WHERE Kodu IN ({','.join('?'*len(kodlar))})", *kodlar)
birim = {}
for k, a, b in cur.fetchall(): ad.setdefault(k, (a or '').strip()); birim[k] = bir.get(str(b or '').casefold().strip('{}'), '?')
sonuc = {k: bakiye.get(k, 0) + uretim[k] - tuketim[k] for k in kodlar}
eksi = [k for k in kodlar if sonuc[k] < -1e-6]
fiyat = son_alis_fiyati_toplu(c, eksi, [])
cur.execute("SELECT DISTINCT sk.Kodu FROM UretimRecete ur JOIN StokKarti sk ON sk.Kodu=ur.Kodu WHERE (ur.KullanimDisi IS NULL OR ur.KullanimDisi=0)")
receteli = {r[0] for r in cur.fetchall()}
cur.execute("""SELECT LEFT(Kodu, CHARINDEX(':', Kodu)-1) FROM StokKarti WHERE Aktif=1 AND Kodu LIKE '%:%' AND Kodu NOT LIKE '%:%:%'
 UNION SELECT LEFT(Kodu, CHARINDEX(':', Kodu)-1) FROM StokMasrafKarti WHERE Kodu LIKE '%:%' AND Kodu NOT LIKE '%:%:%'""")
op_parca = {r[0] for r in cur.fetchall()}

def sinif(k):
    if k.count(':') == 1: return 'Operasyon kartı (fason/işçilik)'
    if k in receteli: return 'Yarı mamul (reçeteli)'
    if k in op_parca: return 'İç imalat parçası (reçetesiz)'
    return 'Hammadde / satın alma'
SIRA = ['Hammadde / satın alma', 'İç imalat parçası (reçetesiz)', 'Yarı mamul (reçeteli)', 'Operasyon kartı (fason/işçilik)']

wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Eksiye Düşen Malzemeler'
cols = ['Sınıf', 'Stok Kodu', 'Stok Adı', 'Birim', 'Bugünkü ERP Bakiye', 'Emirlerle Tüketim', 'Emirlerle Üretim', 'Emirler Sonrası Bakiye',
        'DÜZELTİLECEK MİKTAR', 'Son Alış Fiyatı', 'Son Alış Tarihi', 'Tahmini Tutar', 'Bugün de eksi mi', 'İlgili Emirler']
ws.append(cols)
for cell in ws[1]: cell.font = Font(bold=True, color='FFFFFF'); cell.fill = PatternFill('solid', fgColor='C00000'); cell.alignment = Alignment(wrap_text=True)
top = defaultdict(float); say = defaultdict(int)
for k in sorted(eksi, key=lambda k: (SIRA.index(sinif(k)), k)):
    f = fiyat.get(k); duz = round(-sonuc[k], 4); tut = round(f['fiyat'] * duz, 2) if f else None
    s = sinif(k); say[s] += 1; top[s] += tut or 0
    ws.append([s, k, ad.get(k), birim.get(k), round(bakiye.get(k, 0), 4), round(tuketim[k], 4), round(uretim[k], 4), round(sonuc[k], 4), duz,
               f['fiyat'] if f else None, f['tarih'] if f else 'alış yok', tut, 'Evet' if bakiye.get(k, 0) < -1e-6 else '', ', '.join(sorted(kaynak[k]))])
for col, w in zip('ABCDEFGHIJKLMN', [26, 22, 45, 7, 11, 11, 11, 11, 12, 11, 11, 12, 9, 60]): ws.column_dimensions[col].width = w
ws.freeze_panes = 'C2'; ws.auto_filter.ref = ws.dimensions

ws2 = wb.create_sheet('Emirler')
ws2.append(['Emir', 'Açıklama', 'Emir Tarihi', 'HatTipi', 'Kart', 'Miktar', 'Not'])
for cell in ws2[1]: cell.font = Font(bold=True)
for ek, eac, et, hid, htip, hkod, htalep, hhar in sorted(hatlar, key=lambda h: (h[0], h[4])):
    ws2.append([ek, eac, et, htip, hkod, float(htalep or 0), 'hat zaten tamamlanmış (hesaba katılmadı)' if hhar else ''])
for col, w in zip('ABCDEFG', [20, 55, 11, 7, 20, 8, 35]): ws2.column_dimensions[col].width = w
wb.save(OUT)

print('emir sayısı', len(emirler), emirler)
print('eksiye düşen kalem:', len(eksi))
for s in SIRA: print(f'  {s}: {say[s]} kalem, ~{top[s]:,.2f} TL')
for k in sorted(eksi, key=lambda k: (SIRA.index(sinif(k)), sonuc[k]))[:40]:
    print(f'   {sinif(k)[:12]:12s} {k:24s} {sonuc[k]:>10.2f} {birim.get(k,""):6s} bugün {bakiye.get(k,0):>9.2f} | {ad.get(k,"")[:40]}')
