"""Muhasebeye giden sayım fazlası listesindeki FİYATSIZ kalemlere önerilen fiyat (salt okuma).
Kaynak sırası: (1) kalemin kendi üretim giriş maliyeti, (2) kendi :XX operasyon alışlarının toplamı,
(3) ERP'deki benzer kalemin son alışı, (4) internet fiyatı / tahmin. ERP'deki TL fiyatlar kur farkıyla
bugüne taşınır: TL ÷ alış günü USD × bugünkü USD (GunlukKur.Kur1). İnternet fiyatı EUR × bugünkü EUR.
Kullanım: python fiyatsiz_tamamla.py <muhasebe_eklenecek_kalemler.xlsx> <çıktı.xlsx>"""
import sys, io, datetime as dt
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from config import DB_DEFAULTS
from db.baglanti import get_connection

GIRDI, CIKTI = sys.argv[1], sys.argv[2]
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
DOVIZ = {"USD": "93F5D195-1632-4957-AB52-464DC431A79A", "EUR": "6F454FBD-D5F5-4D8B-A27C-C4FC40FF4A33"}
BUGUN = dt.datetime.combine(dt.date.today(), dt.time())
_kc = {}
def kur(d, t):
    if (d, t) not in _kc:
        cur.execute("SELECT TOP 1 Kur1 FROM GunlukKur WHERE DovizBirimId=? AND Tarih<=? AND Kur1>0 ORDER BY Tarih DESC", DOVIZ[d], t)
        _kc[(d, t)] = float(cur.fetchone()[0])
    return _kc[(d, t)]
USD, EUR = kur("USD", BUGUN), kur("EUR", BUGUN)
T = lambda s: dt.datetime.strptime(s, "%d.%m.%Y")

# kaynak: 'U' üretim maliyeti, 'O' kendi operasyonları, 'B' benzer kalem, 'I' internet/tahmin, 'K' karar gerekli
# parca: [(etiket, tarih, TL)] → her parça kendi alış günü kuruyla bugüne taşınır;  eur: internet EUR fiyatı
P = {
 'GMP-200-230607': ('U', [('Üretim girişi (16)', '30.10.2026', 456.633333)], None),
 'GMP-200-230609': ('U', [('Üretim girişi (16)', '30.10.2026', 97.930833)], None),
 'GMP-200-230615': ('U', [('Üretim girişi (16)', '30.10.2026', 262.60)], None),
 'GMP-200-230616': ('U', [('Üretim girişi (16)', '30.10.2026', 214.50)], None),
 'GMP-200-230246': ('O', [(':20 freze', '25.07.2023', 80.0)], 'Yalnız freze alışı var; malzeme/torna yok. Karşılaştırma: V3 yaylı pim (230609) üretim maliyeti 97,93 ₺.'),
 'GMP-200-240440': ('O', [(':20 freze', '28.10.2025', 3540.0), (':110 çapak', '21.10.2025', 8.0), (':120 polisaj', '17.10.2025', 200.0)],
                    'Kaplama (:60, 105 ₺) dahil edilmedi; listede ayrı satır GMP-200-24044060 olarak var.'),
 'GMP-200-24044060': ('O', [('240440:60 kaplama', '24.10.2025', 105.0)], '12x gövde kaplaması = GMP-200-240440:60 alışı.'),
 'GMP-200-240441': ('O', [(':20 freze', '28.10.2025', 710.0), (':60 kaplama', '24.10.2025', 25.0), (':110 çapak', '21.10.2025', 1.5)], None),
 'GMP-200-240442': ('O', [(':20 freze', '28.10.2025', 1420.0), (':110 çapak', '21.10.2025', 3.166667)], None),
 'GMP-200-240443': ('O', [(':20 freze', '28.10.2025', 710.0), (':60 kaplama', '24.10.2025', 25.0), (':110 çapak', '21.10.2025', 1.5)], None),
 'GMP-200-240444': ('O', [(':20 freze', '28.10.2025', 710.0), (':110 çapak', '21.10.2025', 1.5)], None),
 'GMP-101-230044:10': ('B', [('Diğer namlu adaptörleri (12,7–35 mm) torna', '13.03.2025', 1500.0)],
                    '120 mm adaptörün torna alışı yok. 13.03.2025 toplu alışta tüm büyük çaplar 1.500 ₺ (40,92 $). Son 7,62 mm alışı 750 ₺.'),
 'GMP-200-240250': ('B', [('GMP-200-240245:90 mil sıkıştırma taşlama', '21.11.2025', 444.444443), ('GMP-200-240245:115 parlatma', '26.06.2025', 50.0)],
                    'Aynı adlı GMP-200-240245 operasyonları. Parçanın kendi talaş/malzeme bedeli yok → düşük kalabilir.'),
 'GMP-200-240254': ('B', [('GMP-200-240247:90 yay pimi taşlama', '21.11.2025', 444.444443)], 'Benzer yay pimi (240247) taşlama alışı.'),
 'GMP-200-240660': ('B', [('GMP-200-240658 Boresight L kılavuz', '02.06.2026', 26.999983)], 'Aynı matbaa işi; V kameralı kılavuz 51 ₺.'),
 'HM.BMB.İMB.018': ('B', [('HM.BMB.İMB.012 M5x8 ISO 7380 bombe', '18.09.2025', 1.6)], None),
 'HM.CIV.PSL.534': ('B', [('HM.BMB.İMB.012 M5x8 ISO 7380 bombe', '18.09.2025', 1.6)], 'M5x16 için M5x8 fiyatı esas alındı (boy farkı ihmal).'),
 'HM.CIV.PSL.528': ('B', [('HMVİDA0026 M2,5x5 DIN965 havşa', '07.10.2026', 1.999976)], 'Aynı kod 500 firmasında 07.01.2025: 1,25 ₺.'),
 'HM.CVT.İMB.044': ('B', [('HMCIVATA37 M5x10 havşa inox', '19.09.2026', 1.530021)], None),
 'HM.CVT.İMB.045': ('B', [('HMCIVATA37 M5x10 havşa inox', '19.09.2026', 1.530021)], 'M5x12 torx havşa (HM.VİD.TRK.001) 31.07.2025: 5,50 ₺.'),
 'HMÇLKISH007': ('B', [('HMÇLKSOĞ010 Ø20 1.2379 (₺/kg)', '31.10.2026', 234.424282)], 'Islah (sertleştirilmiş) çubuk biraz pahalı olabilir.'),
 'SPORTAKS004': ('C', None, 'MÜKERRER: SP aksesuar grubu (SPORTAKS001 reçetesi: çanta, flama, kılavuz, mendil, etiket, koli); emir çanta GMP-110-230004, flama 240011, kılavuz 240660 ve mendili zaten ayrı tüketiyor. Emirden çıkarılacak.'),
 'SKF6195': ('I', None, (13.0, 'RS Online: 619/5-2Z ≈ 12,98 € (KDV hariç); açık tip RS UK 10\'lu paket 182 £. Türkiye fiyatı bulunamadı.')),
 'GMP-200-240606': ('I', None, (10.0, 'Tahmin: küçük eksenel bilyalı rulman (51100 sınıfı) RS ≈ 10 €. Ölçü belirsiz ("111730"); teyit gerekli.')),
 'B27.8M-3DM1-16': ('I', [('Tahmin: Ø16 dış segman paslanmaz', '23.11.2026', 10.0)], 'ERP\'de segmanlar 0,35–0,70 ₺ (2023–24). İnternette fiyat bulunamadı; tahmin.'),
 'GMP-200-240607': ('I', [('Tahmin: Ø5 rulman/yönlendirme pimi', '23.11.2026', 15.0)], 'ERP\'de benzeri yok; tahmin.'),
 'YMB-V00-R00-23001': ('C', None, 'MÜKERRER: Emir 1862026-10 tek hatta lens grubunun parçalarını (HMCOMLNS075, 240442, 240443…) zaten ayrı tüketiyor. Emirden çıkarılacak.'),
 'YMB-V00-R00-23002': ('C', None, 'MÜKERRER: Reçetesindeki 11 girdinin hepsi (230611, 230615, 230616, 230630, lensler, O-ringler, vida) emirde ayrıca tüketiliyor. Emirden çıkarılacak.'),
 'YMB-V00-R00-23008': ('K', None, 'Reçete/alış yok. 120 mm çene (240248) aynı emirde ayrı üretiliyor; montajın içeriği ürün sorumlusuna sorulmalı. Fikir: çene torna son alışı 4.160 ₺ (29.10.2025).'),
}
KAYNAK_AD = {'C': 'Listeden çıkarıldı (mükerrer)', 'U': 'ERP – kendi üretim maliyeti', 'O': 'ERP – kendi operasyon alışları', 'B': 'ERP – benzer kalem',
             'I': 'İnternet / tahmin', 'K': 'Karar gerekli'}
RENK = {'C': 'D9D9D9', 'U': 'C6EFCE', 'O': 'C6EFCE', 'B': 'FFEB9C', 'I': 'F8CBAD', 'K': 'FF9999'}

def hesapla(kod):
    tip, parca, ek = P[kod]
    if tip in ('K', 'C'):
        return dict(tip=tip, alis=None, guncel=None, dayanak='', yontem='', notu=ek)
    if parca is None:  # internet EUR
        eur, notu = ek
        return dict(tip=tip, alis=None, guncel=eur * EUR, dayanak=f'{eur:g} € × {EUR:.4f}', yontem='EUR × bugünkü EUR', notu=notu)
    alis = sum(p[2] for p in parca)
    guncel = sum(p[2] / kur('USD', T(p[1])) * USD for p in parca)
    dayanak = ' + '.join(f'{p[0]} {p[2]:,.2f} ₺ ({p[1]}, USD {kur("USD", T(p[1])):.2f})' for p in parca)
    return dict(tip=tip, alis=alis, guncel=guncel, dayanak=dayanak, yontem='TL ÷ alış günü USD × bugünkü USD', notu=ek or '')

wb = openpyxl.load_workbook(GIRDI); ws = wb.active
ws.cell(row=2, column=6).value = 'Birim Fiyat'   # artık yalnız son alış değil; önerilenler de burada (renkli)
yeni = ['Fiyat Kaynağı', 'Dayanak Fiyat (₺, alış günü)', 'Dayanak', 'Yöntem', 'Not']
C0 = 9
for i, b in enumerate(yeni):
    h = ws.cell(row=2, column=C0 + i, value=b); h.font = Font(bold=True); h.alignment = Alignment(wrap_text=True, vertical='center')
toplam_eski = toplam_yeni = 0.0; eksik = []; cikar = []
for r in range(3, ws.max_row + 1):
    kod = ws.cell(r, 2).value
    if not kod or ws.cell(r, 1).value is None: continue
    mik = float(ws.cell(r, 5).value or 0); fiyat = ws.cell(r, 6).value
    if fiyat is not None:
        toplam_eski += float(ws.cell(r, 7).value or 0); continue
    if kod not in P: eksik.append(kod); continue
    h = hesapla(kod)
    if h['tip'] == 'C':
        cikar.append(([ws.cell(r, j).value for j in range(2, 9)], h['notu'])); continue
    fill = PatternFill('solid', fgColor=RENK[h['tip']])
    if h['guncel'] is not None:   # önerilen fiyat doğrudan Birim Fiyat / Tutar sütunlarına
        ws.cell(r, 6).value = round(h['guncel'], 4); ws.cell(r, 7).value = round(h['guncel'] * mik, 2)
    for j in (6, 7): ws.cell(r, j).fill = fill; ws.cell(r, j).number_format = '#,##0.00'
    vals = [KAYNAK_AD[h['tip']], round(h['alis'], 4) if h['alis'] is not None else None, h['dayanak'], h['yontem'], h['notu']]
    for i, v in enumerate(vals):
        x = ws.cell(r, C0 + i, value=v); x.fill = fill; x.alignment = Alignment(wrap_text=True, vertical='top')
        if i == 1: x.number_format = '#,##0.00'
    if h['guncel'] is not None: toplam_yeni += h['guncel'] * mik
for r in range(ws.max_row, 2, -1):
    if ws.cell(r, 1).value is not None and P.get(ws.cell(r, 2).value, ('',))[0] == 'C': ws.delete_rows(r)
n = 0
for r in range(3, ws.max_row + 1):
    if isinstance(ws.cell(r, 1).value, int): n += 1; ws.cell(r, 1).value = n
for r in range(ws.max_row, 2, -1):   # eski toplam satırlarını sil (yenisi aşağıda)
    v = ws.cell(r, 3).value
    if isinstance(v, str) and (v.startswith('TOPLAM') or v.startswith('Fiyatı muhasebe')): ws.delete_rows(r)
w2 = wb.create_sheet('Listeden Çıkarılanlar')
w2.append(['Stok Kodu', 'Stok Adı', 'Birim', 'Miktar', 'Birim Fiyat', 'Tutar', 'Kullanılacağı Üretim', 'Neden']);
for c_ in w2[1]: c_.font = Font(bold=True)
for vals, neden in cikar: w2.append(vals + [neden])
for col, w in zip('ABCDEFGH', (22, 30, 8, 8, 10, 10, 18, 90)): w2.column_dimensions[col].width = w
son = ws.max_row + 2
ws.cell(son, 3, f'{n} kalem · fiyatı olan 31 kalem (değişmedi): {toplam_eski:,.2f} ₺').font = Font(bold=True)
ws.cell(son + 1, 3, f'Fiyatsız {n - 31} kalem için önerilen: {toplam_yeni:,.2f} ₺').font = Font(bold=True)
ws.cell(son + 2, 3, f'Genel toplam: {toplam_eski + toplam_yeni:,.2f} ₺').font = Font(bold=True)
ws.cell(son + 3, 3, f'Kur: {BUGUN:%d.%m.%Y} USD {USD:.4f} ₺, EUR {EUR:.4f} ₺ (CEO ERP GunlukKur, döviz alış). '
                    f'{len(cikar)} mükerrer kalem ayrı sayfada. Yeşil: ERP kendi kaydı · Sarı: ERP benzer kalem · Turuncu: internet/tahmin · Kırmızı: karar gerekli.').font = Font(italic=True, size=9)
ws.cell(son + 2, 7, round(toplam_eski + toplam_yeni, 2)).font = Font(bold=True); ws.cell(son + 2, 7).number_format = '#,##0.00'
for col, w in zip('IJKLM', (26, 16, 60, 26, 60)): ws.column_dimensions[col].width = w
wb.save(CIKTI)
print(f'USD {USD:.4f} EUR {EUR:.4f} | eski {toplam_eski:,.2f} | önerilen {toplam_yeni:,.2f} | eşleşmeyen: {eksik}')
for k in P:
    h = hesapla(k); print(f"{k:22} {h['tip']} alış={h['alis'] if h['alis'] is None else round(h['alis'],2)} güncel={h['guncel'] if h['guncel'] is None else round(h['guncel'],2)}")
