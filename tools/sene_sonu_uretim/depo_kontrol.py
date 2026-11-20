"""Açık sene sonu emirlerinin girdilerini DEPO BAZINDA kontrol eder (CEO kapanışta girdi deposunda 'eksik stok' der). Salt okuma.
Kullanım: python depo_kontrol.py <çıktı.xlsx>
Depo bakiyesi: CEO bakiye formülü, depo = COALESCE(detay.DepoKartId, hareket.DepoKartId); k23 (depolar arası) kaynak depodan düşer,
KarsiDepoKartId'ye girer. Emirler fatura (emir) tarihi sırasıyla işlenir; önceki emirlerin tüketimi/üretimi sonrakine aktarılır (ATP).
Her satır iki kez kontrol edilir: emir tarihindeki depo bakiyesi ve bugünkü depo bakiyesi."""
import sys, io
from collections import defaultdict
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from openpyxl.styles import Font, PatternFill
from config import DB_DEFAULTS
from db.baglanti import get_connection

GIRIS = (1, 4, 5, 8, 15, 16, 20, 22, 26, 29)
CIKIS = (2, 3, 6, 7, 17, 18, 19, 21, 24, 28)
EK_EMIRLER = ['ŞİRKET.1092026-3']
OUT = sys.argv[1]
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
cur.execute("SELECT Id, Adi FROM StokDepoKarti"); depo_ad = {r[0]: r[1].strip() for r in cur.fetchall()}

cur.execute(f"""SELECT ue.Id, ue.Kodu, ue.UretimEmriTarihi, h.Id, h.HatTipi, hk.Id, hk.Kodu, h.TalepMiktari, h.StokDepoId,
   (SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
 FROM UretimEmri ue JOIN UretimEmriHatPlani h ON h.UretimEmriId=ue.Id JOIN StokKarti hk ON hk.Id=h.KartId
 WHERE ue.DurumId=3 AND (ue.SurecDipnot LIKE 'Fatura:%' OR ue.Kodu IN ({','.join('?'*len(EK_EMIRLER))}))
 ORDER BY ue.UretimEmriTarihi, ue.Kodu, h.HatTipi DESC, h.sira""", *EK_EMIRLER)
hatlar = [h for h in cur.fetchall() if not h[9]]
girdiler = {}
kartlar = set()
for h in hatlar:
    cur.execute("""SELECT sk.Id, sk.Kodu, LEFT(sk.Adi,45), g.TalepMiktar, g.StokDepoId FROM UretimEmriHatPlaniGirdi g
      JOIN StokKarti sk ON sk.Id=g.KartId WHERE g.UretimEmriHatPlaniId=? AND g.Tipi<>2 AND (g.Yazilmasin IS NULL OR g.Yazilmasin=0)""", h[3])
    girdiler[h[3]] = cur.fetchall(); kartlar |= {g[0] for g in girdiler[h[3]]}; kartlar.add(h[5])
kartlar = list(kartlar)

# Kart+depo bazında tarihli hareketler (net)
hareket = defaultdict(list)   # (kart, depo) -> [(tarih, miktar)]
for i in range(0, len(kartlar), 500):
    p = kartlar[i:i+500]; yer = ','.join('?'*len(p))
    cur.execute(f"""SELECT shd.IslemKartId, sh.IslemKodu, COALESCE(shd.DepoKartId, sh.DepoKartId), COALESCE(shd.KarsiDepoKartId, sh.KarsiDepoKartId),
         sh.BelgeTarihi, shd.Miktar - ISNULL(f.Miktar,0)
      FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId LEFT JOIN StokHareketDetay f ON f.Id=shd.FaturaDetayId
      WHERE shd.IslemKartId IN ({yer}) AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL
        AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27)""", *p)
    for kid, ik, d, kd, t, m in cur.fetchall():
        t = t.date()
        m = float(m or 0)
        if ik == 23:
            hareket[(kid, d)].append((t, -m))
            if kd: hareket[(kid, kd)].append((t, m))
        elif ik in GIRIS: hareket[(kid, d)].append((t, m))
        elif ik in CIKIS: hareket[(kid, d)].append((t, -m))

def bakiye(kid, depo, tarih=None):
    return sum(m for t, m in hareket.get((kid, depo), []) if tarih is None or t <= tarih)
def depolar(kid):
    out = {}
    for (k, d), hs in hareket.items():
        if k == kid:
            b = sum(m for _, m in hs)
            if abs(b) > 1e-6: out[d] = b
    return out

oncesi = defaultdict(float)   # (kart, depo) -> önceki emirlerin net etkisi (üretim +, tüketim -)
satir = []
for ueid, ek, et, hid, htip, hkid, hkod, htalep, hdepo, _ in hatlar:
    for kid, kod, ad, talep, gdepo in girdiler[hid]:
        talep = float(talep or 0); d = gdepo or 2
        b_et = bakiye(kid, d, et.date()) + oncesi[(kid, d)]
        b_bg = bakiye(kid, d) + oncesi[(kid, d)]
        if b_et - talep < -1e-6 or b_bg - talep < -1e-6:
            diger = {depo_ad.get(x, x): round(v, 3) for x, v in depolar(kid).items() if x != d and v > 0}
            satir.append([ek, f'{et:%d.%m.%Y}', hkod, 'Ana' if htip == 1 else 'YM', kod, ad, depo_ad.get(d, d), talep,
                          round(b_et, 3), round(b_bg, 3), round(min(b_et, b_bg) - talep, 3),
                          ', '.join(f'{k}: {v:g}' for k, v in diger.items())])
        oncesi[(kid, d)] -= talep
    oncesi[(hkid, hdepo or 2)] += float(htalep or 0)

wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Depo Eksikleri'
ws.append(['Emir', 'Emir Tarihi', 'Hat', 'Hat Tipi', 'Stok Kodu', 'Stok Adı', 'Girdi Deposu', 'İhtiyaç',
           'Depo Bakiye (emir tarihi, önceki emirler sonrası)', 'Depo Bakiye (bugün, önceki emirler sonrası)', 'Eksik', 'Diğer Depolardaki Stok'])
for cell in ws[1]: cell.font = Font(bold=True, color='FFFFFF'); cell.fill = PatternFill('solid', fgColor='C00000')
for s in satir: ws.append(s)
for col, w in zip('ABCDEFGHIJKL', [20, 11, 18, 7, 22, 40, 12, 9, 14, 14, 10, 50]): ws.column_dimensions[col].width = w
ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
wb.save(OUT)

print('kontrol edilen hat:', len(hatlar), 'eksik satır:', len(satir))
emir_say = defaultdict(int); kart = {}
for s in satir: emir_say[s[0]] += 1; kart.setdefault(s[4], s)
for e, n in emir_say.items(): print('  ', e, n)
print('tekil kart:', len(kart))
for k, s in kart.items(): print(f'   {k:22s} {s[5][:35]:35s} depo={s[6]} eksik={s[10]:g} | diğer: {s[11]}')
