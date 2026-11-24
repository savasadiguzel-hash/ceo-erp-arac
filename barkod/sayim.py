"""Barkodlu sayım oturumu — CEO ERP'ye YAZMAZ.

Her okutmada oturum JSON dosyasına atomik olarak yazılır (elektrik/çökme
durumunda kaldığı yerden devam). Bitince Excel: sayılan / sistem / fark +
depoda bakiyesi olup hiç okutulmayan kartlar.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


def sayim_dizini() -> Path:
    from config import CONFIG_PATH
    d = Path(CONFIG_PATH).parent / 'barkod_sayim'
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class SayimSatir:
    kart_id: int
    kodu: str
    adi: str
    birim: str
    miktar: float = 0.0
    son_okutma: str = ''


@dataclass
class SayimOturumu:
    depo_id: int
    depo_adi: str
    sayan: str = ''
    baslangic: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    bitis: str = ''
    satirlar: dict = field(default_factory=dict)   # {str(kart_id): SayimSatir-dict}
    log: list = field(default_factory=list)        # [[zaman, kart_id, degisim, yeni_miktar]]
    dosya: str = ''

    # ── kayıt ──
    @classmethod
    def yeni(cls, depo_id: int, depo_adi: str, sayan: str = '') -> 'SayimOturumu':
        o = cls(depo_id, depo_adi, sayan)
        o.dosya = str(sayim_dizini() / f"sayim_{depo_id}_{datetime.now():%Y%m%d_%H%M%S}.json")
        o.kaydet()
        return o

    @classmethod
    def yukle(cls, yol: str | Path) -> 'SayimOturumu':
        with open(yol, encoding='utf-8') as f:
            d = json.load(f)
        d['dosya'] = str(yol)
        return cls(**d)

    def kaydet(self) -> None:
        tmp = self.dosya + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=1, default=str)
        os.replace(tmp, self.dosya)

    # ── işlem ──
    def ekle(self, kart_id: int, kodu: str, adi: str, birim: str, miktar: float = 1.0,
             mutlak: bool = False) -> dict:
        """Okutma: miktar kadar artır (mutlak=True ise değeri doğrudan ata)."""
        k = str(kart_id)
        s = self.satirlar.get(k) or asdict(SayimSatir(kart_id, kodu, adi, birim))
        eski = float(s['miktar'])
        s['miktar'] = round(float(miktar) if mutlak else eski + float(miktar), 6)
        s['son_okutma'] = datetime.now().strftime('%H:%M:%S')
        self.satirlar[k] = s
        self.log.append([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), kart_id,
                         round(s['miktar'] - eski, 6), s['miktar']])
        self.kaydet()
        return s

    def sil(self, kart_id: int) -> None:
        s = self.satirlar.pop(str(kart_id), None)
        if s:
            self.log.append([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), kart_id, -s['miktar'], 0])
            self.kaydet()

    def bitir(self) -> None:
        self.bitis = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.kaydet()


def oturumlar(yalniz_acik: bool = False) -> list[dict]:
    """Kayıtlı sayım oturumları (en yeni önce). yalniz_acik=True ise bitmemişler.

    Her öğe: {yol, baslangic, depo_adi, kalem, sayan, bitti}.
    """
    sonuc = []
    for p in sorted(sayim_dizini().glob('sayim_*.json'), reverse=True):
        try:
            with open(p, encoding='utf-8') as f:
                d = json.load(f)
        except Exception:
            continue
        if yalniz_acik and d.get('bitis'):
            continue
        sonuc.append({'yol': p, 'baslangic': d.get('baslangic', ''), 'depo_adi': d.get('depo_adi', ''),
                      'kalem': len(d.get('satirlar', {})), 'sayan': d.get('sayan', ''),
                      'bitti': bool(d.get('bitis'))})
    return sonuc


def acik_oturumlar() -> list[Path]:
    """Geriye dönük: bitirilmemiş oturum dosyaları."""
    return [o['yol'] for o in oturumlar(yalniz_acik=True)]


def excel_yaz(conn, oturum: SayimOturumu, yol: str | Path, sayilmayanlari_ekle: bool = True) -> Path:
    """Sayım sonucu Excel'i. Sistem bakiyesi = depo bazlı, bugün itibarıyla."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    from barkod.sorgu import depo_bakiyeleri, kart_ozetleri

    sistem = {kid: m for (kid, _), m in depo_bakiyeleri(conn, depo_id=oturum.depo_id).items()}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Sayım'
    baslik = ['Barkod', 'Stok Kodu', 'Stok Adı', 'Birim', 'Sayılan', 'Sistem', 'Fark', 'Son okutma']
    ws.append([f'Depo: {oturum.depo_adi}', f'Sayan: {oturum.sayan}',
               f'Başlangıç: {oturum.baslangic}', f'Bitiş: {oturum.bitis or "-"}'])
    ws.append(baslik)
    kalin = Font(bold=True)
    for c in ws[2]:
        c.font = kalin
    kirmizi = PatternFill('solid', fgColor='FFCDD2')
    yesil = PatternFill('solid', fgColor='C8E6C9')

    from barkod.kod import barkod_degeri
    for s in sorted(oturum.satirlar.values(), key=lambda x: x['kodu']):
        sis = sistem.get(int(s['kart_id']), 0.0)
        fark = round(s['miktar'] - sis, 6)
        ws.append([barkod_degeri(s['kart_id']), s['kodu'], s['adi'], s['birim'],
                   s['miktar'], sis, fark, s['son_okutma']])
        ws.cell(ws.max_row, 7).fill = yesil if abs(fark) < 1e-6 else kirmizi

    if sayilmayanlari_ekle:
        ws2 = wb.create_sheet('Sayılmayanlar')
        ws2.append(['Depoda sistem bakiyesi olup hiç okutulmayan kartlar'])
        ws2.append(['Barkod', 'Stok Kodu', 'Stok Adı', 'Birim', 'Sistem'])
        for c in ws2[2]:
            c.font = kalin
        eksik = [kid for kid, m in sistem.items() if abs(m) > 1e-6 and str(kid) not in oturum.satirlar]
        oz = kart_ozetleri(conn, eksik)
        for kid in sorted(eksik, key=lambda i: oz.get(i, {}).get('kodu', '')):
            o = oz.get(kid, {})
            ws2.append([barkod_degeri(kid), o.get('kodu', ''), o.get('adi', ''), o.get('birim', ''), sistem[kid]])

    for w, gen in zip('ABCDEFGH', (10, 22, 50, 8, 10, 10, 10, 10)):
        ws.column_dimensions[w].width = gen
    yol = Path(yol)
    wb.save(yol)
    return yol
