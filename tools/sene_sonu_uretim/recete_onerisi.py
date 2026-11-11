"""Reçetesi olmayan mamuller için, en son üretim emrinin girdilerinden reçete önerisi (Excel). Salt okuma.
Kullanım: python recete_onerisi.py <çıktı.xlsx> KOD1 KOD2 ..."""
import sys, io
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from openpyxl.styles import Font, PatternFill
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import birimleri_getir, stok_guncel_bakiyeleri
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
bir = {str(g).casefold().strip('{}'): n for n, g in birimleri_getir(c).items()}
OUT, kodlar = sys.argv[1], sys.argv[2:]
wb = openpyxl.Workbook(); wb.remove(wb.active)
for kod in kodlar:
    cur.execute("""SELECT TOP 1 ue.Id, ue.Kodu, CONVERT(varchar(10),ue.UretimEmriTarihi,104), h.Id, h.TalepMiktari
      FROM UretimEmri ue JOIN UretimEmriHatPlani h ON h.UretimEmriId=ue.Id JOIN StokKarti sk ON sk.Id=h.KartId
      WHERE sk.Kodu=? AND h.HatTipi=1 ORDER BY ue.UretimEmriTarihi DESC, ue.Id DESC""", kod)
    e = cur.fetchone()
    ws = wb.create_sheet(kod[-6:])
    if not e:
        ws.append([kod, 'Geçmiş üretim emri yok']); print(kod, 'emir yok'); continue
    cur.execute("""SELECT g.Tipi, COALESCE(sk.Kodu, smk.Kodu), COALESCE(sk.Adi, smk.Adi), g.Miktar, g.TalepMiktar, g.StokBirim, g.SabitMiktar,
        CASE WHEN g.Tipi=2 THEN 1 ELSE sk.Aktif END
      FROM UretimEmriHatPlaniGirdi g LEFT JOIN StokKarti sk ON sk.Id=g.KartId AND g.Tipi<>2
      LEFT JOIN StokMasrafKarti smk ON smk.Id=g.KartId AND g.Tipi=2 WHERE g.UretimEmriHatPlaniId=? ORDER BY g.Id""", e[3])
    rs = cur.fetchall()
    stoklar = [r[1] for r in rs if r[0] != 2]
    bakiye = stok_guncel_bakiyeleri(c, stoklar)
    ws.append([f'{kod} — reçete önerisi', f'Kaynak emir: {e[1]} ({e[2]}), emir miktarı {float(e[4] or 0):g}'])
    ws.append([])
    ws.append(['Tip', 'Kod', 'Ad', 'Birim Başı Miktar', 'Birim', 'Kart Aktif', 'Güncel Bakiye', 'Not'])
    for cell in ws[3]: cell.font = Font(bold=True, color='FFFFFF'); cell.fill = PatternFill('solid', fgColor='305496')
    gorulen = set()
    for tipi, k, a, mik, talep, birim, sabit, aktif in rs:
        notlar = []
        if (tipi, k) in gorulen: notlar.append('MÜKERRER satır')
        gorulen.add((tipi, k))
        if not aktif: notlar.append('KART PASİF')
        ws.append(['Masraf' if tipi == 2 else 'Stok', k, (a or '').strip(), float(mik), bir.get(str(birim or '').casefold().strip('{}'), '?'),
                   'Evet' if aktif else 'HAYIR', None if tipi == 2 else round(bakiye.get(k, 0), 2), ', '.join(notlar)])
    for col, w in zip('ABCDEFGH', [8, 22, 50, 12, 8, 9, 12, 20]): ws.column_dimensions[col].width = w
    print(f'{kod}: kaynak {e[1]} ({e[2]}), {len(rs)} satır, pasif {sum(1 for r in rs if not r[7])}, mükerrer {len(rs)-len({(r[0], r[1]) for r in rs})}')
wb.save(OUT)
