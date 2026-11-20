"""Açık sene sonu emirlerinin masraf (Tipi=2) girdilerine Tutar yazar. CEO masraf maliyetini bu alandan alır, boşsa 0 sayar.
Kullanım: python masraf_doldur.py <ön_izleme.xlsx> [--commit] [--emir "ŞİRKET.x"]   (--commit yoksa rollback = deneme)
Kural (her satır için, yalnız Tutar=0 olanlar):
  1) Emir tarihine kadar son masraf alışı (db.sorgular.uretim_emri_masraf_maliyet_onizle ile aynı kaynak)
  2) yoksa aynı kodlu StokKarti'nin emir tarihine kadar son alışı (IslemKodu 1 / faturalaşmamış 5, BirimFiyat>0)
  3) aynı kod aynı hatta stok girdisi (Tipi<>2) olarak da varsa ATLANIR (mükerrer maliyet olmasın)
  Tutar = TalepMiktar × birim fiyat. Eski değerler masraf_doldur_yedek_<tarih>.json'a yazılır."""
import sys, io, json
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from openpyxl.styles import Font, PatternFill
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import uretim_emri_masraf_maliyet_onizle

args = [a for a in sys.argv[1:] if not a.startswith('--')]
OUT = args[0]; COMMIT = '--commit' in sys.argv
TEK = sys.argv[sys.argv.index('--emir') + 1] if '--emir' in sys.argv else None
if TEK: args = [a for a in args if a != TEK]
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()

if TEK: emirler = [TEK]
else:
    cur.execute("SELECT Kodu FROM UretimEmri WHERE DurumId=3 AND (SurecDipnot LIKE 'Fatura:%' OR Kodu='ŞİRKET.1092026-3') ORDER BY UretimEmriTarihi")
    emirler = [r[0] for r in cur.fetchall()]

satir = []
for ek in emirler:
    o = uretim_emri_masraf_maliyet_onizle(c, ek)
    if not o['satirlar']: continue
    et = datetime.strptime(o['emir']['tarih'], '%d.%m.%Y')
    gids = [s['girdi_id'] for s in o['satirlar']]
    cur.execute(f"""SELECT g.Id, h.Id, hk.Kodu, (SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
      FROM UretimEmriHatPlaniGirdi g JOIN UretimEmriHatPlani h ON h.Id=g.UretimEmriHatPlaniId JOIN StokKarti hk ON hk.Id=h.KartId
      WHERE g.Id IN ({','.join('?'*len(gids))})""", *gids)
    hat = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}
    stok_kod = defaultdict(set)
    for hid in {v[0] for v in hat.values()}:
        cur.execute("SELECT sk.Kodu FROM UretimEmriHatPlaniGirdi g JOIN StokKarti sk ON sk.Id=g.KartId WHERE g.UretimEmriHatPlaniId=? AND g.Tipi<>2", hid)
        stok_kod[hid] = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT hk.Kodu FROM UretimEmriHatPlani h JOIN StokKarti hk ON hk.Id=h.KartId JOIN UretimEmri ue ON ue.Id=h.UretimEmriId WHERE ue.Kodu=?", ek)
    hat_urun = {r[0] for r in cur.fetchall()}
    fiyatli = {}
    def parca_fiyatli(p):
        if p not in fiyatli:
            cur.execute("""SELECT TOP 1 1 FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId JOIN StokKarti sk ON sk.Id=shd.IslemKartId
              WHERE sk.Kodu=? AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.IslemKodu IN (1,5,8,15,16,20) AND shd.BirimFiyat>0 AND sh.BelgeTarihi<?""",
                        p, et.replace(hour=23, minute=59))
            fiyatli[p] = cur.fetchone() is not None
        return fiyatli[p]
    for s in o['satirlar']:
        hid, hkod, kapali = hat[s['girdi_id']]
        parca = s['kod'].split(':')[0]
        r = dict(emir=ek, emir_tarih=o['emir']['tarih'], hat=hkod, girdi_id=s['girdi_id'], kod=s['kod'], ad=s['ad'], talep=s['talep_miktari'],
                 eski=s['eski_tutar'], kaynak='', kaynak_tarih='', fiyat=None, yeni=None, durum='')
        if kapali: r['durum'] = 'hat kapalı'
        elif s['durum'] == 'zaten_dolu': r['durum'] = 'zaten dolu'
        elif s['kod'] in stok_kod[hid]: r['durum'] = 'atlandı: aynı kod hatta stok girdisi'
        elif parca != hkod and parca in hat_urun: r['durum'] = 'atlandı: parça başka hatta üretiliyor'
        elif parca != hkod and parca in stok_kod[hid] and parca_fiyatli(parca): r['durum'] = 'atlandı: parça stoktan, maliyeti parçada'
        elif s['durum'] == 'uygulanabilir':
            r.update(kaynak='masraf alışı', kaynak_tarih=s['kaynak_tarihi'], fiyat=s['birim_fiyat'], yeni=round(s['yeni_tutar'], 6), durum='YAZILACAK')
        else:
            cur.execute("""SELECT TOP 1 sh.BelgeTarihi, shd.BirimFiyat FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId JOIN StokKarti sk ON sk.Id=shd.IslemKartId
              WHERE sk.Kodu=? AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND (sh.IslemKodu=1 OR (sh.IslemKodu=5 AND sh.FaturaId IS NULL))
                AND shd.BirimFiyat>0 AND shd.Miktar>0 AND sh.BelgeTarihi<? ORDER BY sh.BelgeTarihi DESC, sh.Id DESC""", s['kod'], et.replace(hour=23, minute=59))
            f = cur.fetchone()
            if f:
                r.update(kaynak='stok kartı alışı', kaynak_tarih=f[0].strftime('%d.%m.%Y'), fiyat=float(f[1]), yeni=round(float(f[1]) * s['talep_miktari'], 6), durum='YAZILACAK')
            else: r['durum'] = 'FİYAT YOK'
        satir.append(r)

yaz = [r for r in satir if r['durum'] == 'YAZILACAK']
for r in yaz: cur.execute("UPDATE UretimEmriHatPlaniGirdi SET Tutar=? WHERE Id=? AND ISNULL(Tutar,0)=0", r['yeni'], r['girdi_id'])
n = sum(1 for _ in yaz)

wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Masraf Satırları'
H = ['Emir', 'Emir Tarihi', 'Hat', 'Masraf Kodu', 'Ad', 'Talep', 'Eski Tutar', 'Kaynak', 'Kaynak Tarihi', 'Birim Fiyat', 'Yeni Tutar', 'Durum']
ws.append(H)
for cl in ws[1]: cl.font = Font(bold=True, color='FFFFFF'); cl.fill = PatternFill('solid', fgColor='1F4E78')
R = {'YAZILACAK': 'C6EFCE', 'FİYAT YOK': 'FFC7CE'}
for r in satir:
    ws.append([r['emir'], r['emir_tarih'], r['hat'], r['kod'], r['ad'], r['talep'], r['eski'], r['kaynak'], r['kaynak_tarih'], r['fiyat'], r['yeni'], r['durum']])
    if r['durum'] in R: ws.cell(ws.max_row, 12).fill = PatternFill('solid', fgColor=R[r['durum']])
for col, w in zip('ABCDEFGHIJKL', [20, 11, 18, 22, 40, 7, 10, 16, 11, 11, 11, 34]): ws.column_dimensions[col].width = w
ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
ws2 = wb.create_sheet('Özet'); ws2.append(['Emir', 'Yazılacak', 'Tutar', 'Fiyat yok', 'Atlandı (mükerrer)', 'Zaten dolu'])
oz = defaultdict(lambda: [0, 0.0, 0, 0, 0])
for r in satir:
    o_ = oz[r['emir']]
    if r['durum'] == 'YAZILACAK': o_[0] += 1; o_[1] += r['yeni']
    elif r['durum'] == 'FİYAT YOK': o_[2] += 1
    elif r['durum'].startswith('atlandı'): o_[3] += 1
    elif r['durum'] == 'zaten dolu': o_[4] += 1
for e, v in oz.items(): ws2.append([e, v[0], round(v[1], 2), v[2], v[3], v[4]])
wb.save(OUT)

print(f"{'Emir':20s} yazılacak    tutar      fiyatyok atlandı dolu")
for e, v in oz.items(): print(f'{e:20s} {v[0]:>8} {v[1]:>12,.2f} {v[2]:>8} {v[3]:>7} {v[4]:>4}')
print(f'TOPLAM yazılacak {n} satır, {sum(r["yeni"] for r in yaz):,.2f} TL')
if COMMIT:
    c.commit()
    fn = rf'C:\yeni-erp\masraf_doldur_yedek_{datetime.now():%Y%m%d_%H%M%S}.json'
    json.dump([{'girdi_id': r['girdi_id'], 'emir': r['emir'], 'kod': r['kod'], 'eski_tutar': r['eski'], 'yeni_tutar': r['yeni']} for r in yaz],
              open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('COMMIT edildi. Yedek:', fn)
else: c.rollback(); print('ROLLBACK (deneme)')
