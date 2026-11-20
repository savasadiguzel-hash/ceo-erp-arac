"""2026 fatura ↔ üretim farkı, ürün bazında (salt okuma).
Açılış (01.01.2026) + 2026 üretimi − 2026 satışı ± diğer hareketler = bugünkü bakiye.
"Bekleyen üretim" = muhasebe girişi / onay bekleyen fatura birebir emirler.
Kullanım: python fatura_uretim_fark.py <fatura_emir_uyum.xlsx> <çıktı.xlsx>"""
import sys, io
from collections import defaultdict
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import stok_guncel_bakiyeleri

UYUM, CIKTI = sys.argv[1], sys.argv[2]
BEKLEYEN = {'GMP-101-230030': (1, '1862026-10 RSTEK (muhasebe girişi bekliyor)'), 'GMP-101-230044': (1, '1862026-7 RSTEK (muhasebe girişi bekliyor)'),
            'GMP-101-230035': (5, '1862026-8 Unirobotics (muhasebe girişi bekliyor)'), 'HAV-HPB0001': (43, 'Ford ×43 (hazır, onay bekliyor)'),
            'GMP-101-230093': (50, 'FAEM ×50 (muhasebe girişi bekliyor)')}
c = get_connection(**DB_DEFAULTS); cur = c.cursor()

cur.execute("SELECT DISTINCT Kodu FROM UretimRecete WHERE KullanimDisi IS NULL OR KullanimDisi=0")
receteli = {r[0] for r in cur.fetchall()}
# 2026 satışları (fatura + faturasız irsaliye, irsaliyesi faturalanan satır mükerrer sayılmaz)
cur.execute("""SELECT sk.Kodu, LEFT(sk.Adi,60), SUM(shd.Miktar-ISNULL(f.Miktar,0)), COUNT(DISTINCT sh.Id)
 FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId LEFT JOIN StokHareketDetay f ON f.Id=shd.FaturaDetayId
 JOIN StokKarti sk ON sk.Id=shd.IslemKartId
 WHERE shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND (sh.IslemKodu=2 OR (sh.IslemKodu=6 AND sh.FaturaId IS NULL)) AND sh.BelgeTarihi>='20260101'
 GROUP BY sk.Kodu, sk.Adi""")
satis = {r[0]: (r[1].strip(), float(r[2]), r[3]) for r in cur.fetchall() if r[0] in receteli}
# 2026 üretim girişleri (16 fişi)
cur.execute("""SELECT sk.Kodu, SUM(shd.Miktar), COUNT(DISTINCT sh.Id) FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId
 JOIN StokKarti sk ON sk.Id=shd.IslemKartId WHERE shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.IslemKodu=16 AND sh.BelgeTarihi>='20260101'
 GROUP BY sk.Kodu""")
uretim = {r[0]: (float(r[1]), r[2]) for r in cur.fetchall()}
kodlar = sorted(satis)
acilis = stok_guncel_bakiyeleri(c, kodlar, '2025-12-31')
bugun = stok_guncel_bakiyeleri(c, kodlar, '2099-12-31')

satirlar = []
for k in kodlar:
    ad, sm, fs = satis[k]; um, es = uretim.get(k, (0.0, 0))
    a, b = acilis.get(k, 0.0), bugun.get(k, 0.0)
    diger = b - (a + um - sm)
    bek, bek_not = BEKLEYEN.get(k, (0, ''))
    sonra = b + bek
    fark = um + bek - sm
    if sonra < -1e-6: durum = 'EKSİ KALIYOR'
    elif fark < -1e-6: durum = 'Satış > üretim, fark açılış stoğundan karşılandı'
    elif fark > 1e-6: durum = 'Üretim > satış, fazlası stokta / başka üründe kullanıldı'
    else: durum = 'Birebir'
    satirlar.append([k, ad, a, um, es, sm, fs, diger, b, bek, bek_not, sonra, fark, durum])
satirlar.sort(key=lambda r: (r[11] >= -1e-6, r[12]))

# Faturası olup kendi emri olmayan satırlar (uyum çıktısından)
wb_u = openpyxl.load_workbook(UYUM, data_only=True)
fat = [list(r) for r in wb_u['Faturalar'].iter_rows(min_row=2, values_only=True) if r[0]]
emirs = [list(r) for r in wb_u['Emirler'].iter_rows(min_row=2, values_only=True) if r[0]]

wb = openpyxl.Workbook()
BAS = Font(bold=True, color='FFFFFF'); BASF = PatternFill('solid', fgColor='305496')
ince = Side(style='thin', color='BFBFBF'); KENAR = Border(left=ince, right=ince, top=ince, bottom=ince)
YESIL = PatternFill('solid', fgColor='E2EFDA'); SARI = PatternFill('solid', fgColor='FFF2CC'); KIRMIZI = PatternFill('solid', fgColor='F8CBAD'); MAVI = PatternFill('solid', fgColor='DDEBF7')

def sayfa(ws, basliklar, notlar, veri, gen, sayi=()):
    for i, n in enumerate(notlar, 1): ws.cell(i, 1, n).font = Font(bold=(i == 1), size=13 if i == 1 else 11)
    r0 = len(notlar) + 2
    for j, h in enumerate(basliklar, 1):
        x = ws.cell(r0, j, h); x.font = BAS; x.fill = BASF; x.border = KENAR; x.alignment = Alignment(wrap_text=True, vertical='center')
    for i, v in enumerate(veri, 1):
        for j, x in enumerate(v, 1):
            if hasattr(x, 'strftime'): x = x.strftime('%d.%m.%Y')
            cl = ws.cell(r0 + i, j, x); cl.border = KENAR; cl.alignment = Alignment(wrap_text=True, vertical='top')
            if j in sayi: cl.number_format = '#,##0.##'
    for j, w in enumerate(gen, 1): ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(r0 + 1, 3); ws.auto_filter.ref = f'A{r0}:{get_column_letter(len(basliklar))}{r0 + len(veri)}'
    return r0

ws = wb.active; ws.title = 'Ürün Bazında Fark'
r0 = sayfa(ws, ['Stok Kodu', 'Ürün Adı', 'Açılış 01.01.2026', '2026 Üretim', 'Üretim Fişi', '2026 Satış', 'Fatura/İrs.', 'Diğer Hareket (YM kullanımı, sayım, iade…)',
                'Bugünkü Bakiye', 'Bekleyen Üretim', 'Bekleyen İş', 'İşler Bitince Bakiye', 'FARK (Üretim+Bekleyen − Satış)', 'Durum'],
           ['2026 FATURA ↔ ÜRETİM FARKI (reçeteli ürünler, ürün bazında)',
            'Formül: Açılış + Üretim − Satış + Diğer = Bugünkü Bakiye.  FARK eksi ise satışın bir kısmı açılış stoğundan (2025 üretimi) karşılanmıştır, sorun değildir.',
            'Önemli olan "İşler Bitince Bakiye" sütunu: eksi kalan ürün olmamalı.'],
           satirlar, [18, 40, 11, 10, 8, 10, 8, 14, 10, 10, 30, 11, 13, 40], sayi=(3, 4, 6, 8, 9, 10, 12, 13))
for i, v in enumerate(satirlar, 1):
    ws.cell(r0 + i, 14).fill = KIRMIZI if v[13].startswith('EKSİ') else (YESIL if v[13] == 'Birebir' else (SARI if v[12] < 0 else MAVI))
    if v[9]: ws.cell(r0 + i, 11).fill = SARI
son = r0 + len(satirlar) + 2
ws.cell(son, 2, 'TOPLAM').font = Font(bold=True)
for j in (4, 6, 10, 13):
    t = ws.cell(son, j, sum(v[j - 1] for v in satirlar)); t.font = Font(bold=True); t.number_format = '#,##0.##'

ws = wb.create_sheet('Fatura Satırları')
fat_v = [[r[0], r[1], r[3], r[4], r[5], r[6], r[8], r[9], r[10], r[12]] for r in fat]
r0 = sayfa(ws, ['Fatura Tarihi', 'Belge No', 'Cari', 'Stok Kodu', 'Ürün', 'Fatura Miktarı', 'Eşleşme', 'Üretim Emri', 'Emir Tarihi', 'Emir Miktarı'],
           ['2026 FATURA SATIRLARI ve KARŞILIK GELEN ÜRETİM EMRİ',
            '"EMİR YOK" = bu faturaya özel emir yok; ürün stoktan (toplu üretim veya 2025 stoğu) satılmış. "Cari, miktar farklı" = emir var ama miktar/cari tutmuyor.'],
           fat_v, [12, 20, 34, 18, 34, 10, 18, 20, 12, 10], sayi=(6, 10))
for i, v in enumerate(fat_v, 1):
    e = str(v[6] or '')
    ws.cell(r0 + i, 7).fill = SARI if 'EMİR YOK' in e.upper() else (KIRMIZI if 'farklı' in e else YESIL)

ws = wb.create_sheet('Faturasız Emirler')
fe = [[r[0], r[1], r[2], r[3], r[4], r[8], r[10]] for r in emirs if r[5] in (None, 0, '0', '') or 'FATURASIZ' in str(r[10] or '').upper()]
sayfa(ws, ['Emir', 'Emir Tarihi', 'Durum', 'Stok Kodu', 'Miktar', 'Açıklama', 'Sonuç'],
      ['FATURASI OLMAYAN 2026 ÜRETİM EMİRLERİ', 'Stoğa yapılan üretimler; satışları başka faturalarda stoktan yapılmış olabilir.'],
      fe, [20, 12, 14, 18, 8, 50, 30], sayi=(5,))
wb.save(CIKTI)
print('Kaydedildi:', CIKTI, '| ürün', len(satirlar), '| fatura satırı', len(fat_v), '| faturasız emir', len(fe))
for v in satirlar: print(f'{v[0]:18s} açılış {v[2]:6g} üretim {v[3]:6g} satış {v[5]:6g} diğer {v[7]:7g} bugün {v[8]:6g} bekleyen {v[9]:4g} sonra {v[11]:6g} fark {v[12]:6g} | {v[13]}')
