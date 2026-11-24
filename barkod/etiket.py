"""Stok etiketi çekirdek modülü — Zebra ZPL + PIL/PNG önizleme + USB/TCP yazdırma.

CEO ERP'den YALNIZCA OKUR (veritabanına hiçbir şey yazmaz).
Barkod/QR içeriği: S + StokKarti.Id (6 hane), örn. S468311.
Hem `barkod_app.py` (GUI) hem `tools/etiket/etiket.py` (CLI) tarafından ortak kullanılır.
"""
from __future__ import annotations

import io
import os
import socket
from dataclasses import dataclass

from barkod.kod import barkod_coz, barkod_degeri  # noqa: F401

FONT_DIZIN = r'C:\Windows\Fonts'
HAZIR_OLCULER = ('70x30', '50x25', '40x20', '100x50', '30x15')


# ───────────────────────── veri ─────────────────────────
@dataclass
class Kart:
    id: int
    kodu: str
    adi: str
    birim: str
    bakiye: float = 0.0
    aktif: bool = True


def olcu_coz(metin: str) -> tuple[float, float]:
    """'70x30' veya '70×30' → (gen_mm, yuk_mm). Geçersizse ValueError."""
    temiz = (metin or '').strip().lower().replace('×', 'x').replace(',', '.')
    parcalar = temiz.split('x')
    if len(parcalar) != 2:
        raise ValueError(f'Geçersiz etiket ölçüsü: {metin!r} (örnek: 70x30)')
    gen, yuk = float(parcalar[0].strip()), float(parcalar[1].strip())
    if not (15.0 <= gen <= 150.0 and 10.0 <= yuk <= 150.0):
        raise ValueError(f'Etiket ölçüsü sınır dışı ({gen:g}x{yuk:g} mm; 15..150 x 10..150 beklenir)')
    return gen, yuk


def kartlari_oku(conn, kodlar=(), idler=(), bakiyeli=False, limit=None) -> list[Kart]:
    """CLI ve toplu sorgular için aktif stok kartlarını okur."""
    from db.baglanti import cursor_ctx
    from db.sorgular import birimleri_getir, stok_guncel_bakiyeleri

    with cursor_ctx(conn) as cur:
        cur.execute("SELECT Id, Kodu, Adi, ISNULL(CONVERT(NVARCHAR(50), StokBirim), '') "
                    "FROM StokKarti WHERE Aktif = 1")
        tum = cur.fetchall()

    secili = []
    bak = {}
    if kodlar or idler:
        kset = {k.strip().upper() for k in kodlar}
        iset = set(idler)
        secili = [r for r in tum if (r[1] or '').strip().upper() in kset or r[0] in iset]
        bulunan = {(r[1] or '').strip().upper() for r in secili} | {r[0] for r in secili}
        for k in kset - bulunan:
            print(f'UYARI: aktif kart bulunamadı: {k}')
        for i in iset - bulunan:
            print(f'UYARI: aktif kart bulunamadı: Id {i}')
    if bakiyeli:
        bak = stok_guncel_bakiyeleri(conn, [r[1] for r in tum])
        mevcut = {r[0] for r in secili}
        secili += [r for r in tum if bak.get(r[1], 0) > 0.0001 and r[0] not in mevcut]

    secili.sort(key=lambda r: (r[1] or ''))
    if limit:
        secili = secili[:limit]

    g2a = {str(g).casefold().strip('{}'): a for a, g in birimleri_getir(conn).items()}
    return [Kart(int(r[0]), (r[1] or '').strip(), (r[2] or '').strip(),
                 g2a.get(str(r[3]).casefold().strip('{}'), ''),
                 float(bak.get(r[1], 0.0)), True) for r in secili]


def depo_bakiyeli_kartlar(conn, depo_id: int | None = None) -> list[Kart]:
    """Seçili depoda (veya depo_id=None ise şirket genelinde) bakiyesi > 0 olan AKTİF kartlar."""
    from barkod.sorgu import depo_bakiyeleri, kart_ozetleri

    if depo_id is not None:
        ham = {kid: m for (kid, _), m in depo_bakiyeleri(conn, depo_id=depo_id).items() if m > 1e-6}
    else:
        toplam: dict[int, float] = {}
        for (kid, _), m in depo_bakiyeleri(conn).items():
            toplam[kid] = toplam.get(kid, 0.0) + m
        ham = {kid: round(m, 6) for kid, m in toplam.items() if m > 1e-6}

    if not ham:
        return []
    ozetler = kart_ozetleri(conn, list(ham.keys()))
    sonuc = [
        Kart(kid, oz['kodu'], oz['adi'], oz['birim'], ham[kid], True)
        for kid, oz in ozetler.items()
        if oz.get('aktif')
    ]
    sonuc.sort(key=lambda k: k.kodu)
    return sonuc


def depo_kartlari(conn, depo_id: int | None = None) -> list[Kart]:
    """Etiket listesi için AKTİF kartlar — bakiye 0 ve eksi dahil.

    depo_id verilirse: o depoda (transfer hedefi dahil) hiç hareketi olmuş aktif kartlar,
    bakiye o deponun bakiyesidir. depo_id None ise: tüm aktif stok kartları, bakiye şirket toplamıdır.
    """
    from barkod.sorgu import depo_bakiyeleri, kart_ozetleri
    from db.baglanti import cursor_ctx

    with cursor_ctx(conn) as cur:
        if depo_id is not None:
            cur.execute("""
                SELECT DISTINCT shd.IslemKartId
                FROM StokHareketDetay shd
                JOIN StokHareket sh ON sh.Id = shd.HareketId
                WHERE shd.Turu = 1 AND shd.Aktif = 1 AND sh.Aktif = 1 AND shd.IslemKartId IS NOT NULL
                  AND (COALESCE(shd.DepoKartId, sh.DepoKartId) = ?
                       OR (sh.IslemKodu = 23 AND COALESCE(shd.KarsiDepoKartId, sh.KarsiDepoKartId) = ?))
            """, depo_id, depo_id)
        else:
            cur.execute("SELECT Id FROM StokKarti WHERE Aktif = 1")
        idler = [int(r[0]) for r in cur.fetchall()]
    if not idler:
        return []

    bakiye: dict[int, float] = {}
    for (kid, _), m in depo_bakiyeleri(conn, depo_id=depo_id).items():
        bakiye[kid] = bakiye.get(kid, 0.0) + m

    ozetler = kart_ozetleri(conn, idler)
    sonuc = [
        Kart(kid, oz['kodu'], oz['adi'], oz['birim'], round(bakiye.get(kid, 0.0), 6), True)
        for kid, oz in ozetler.items()
        if oz.get('aktif')
    ]
    sonuc.sort(key=lambda k: k.kodu)
    return sonuc


# ───────────────────────── Code128 (önizleme + genişlik hesabı) ─────────────────────────
_C128 = ("212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 "
         "221312 231212 112232 122132 122231 113222 123122 123221 223211 221132 "
         "221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 "
         "212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 "
         "231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 "
         "231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 "
         "314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 "
         "112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 "
         "111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 "
         "214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 "
         "114131 311141 411131 211412 211214 211232 2331112").split()
assert all(sum(map(int, p)) == 11 for p in _C128[:106]) and sum(map(int, _C128[106])) == 13


def code128_kodla(veri: str) -> list[int]:
    """B kümesi + 4 ve üzeri çift rakam dizilerinde C kümesi (ZPL otomatik moduna yakın)."""
    i, kod, set_ = 0, [], None
    while i < len(veri):
        j = i
        while j < len(veri) and veri[j].isdigit():
            j += 1
        n = j - i
        if n >= 4 or (n >= 2 and i == 0 and j == len(veri) and n % 2 == 0):
            if n % 2:                       # tek sayıda rakam → ilkini B ile yaz
                if set_ != 'B':
                    kod.append(104 if set_ is None else 100); set_ = 'B'
                kod.append(ord(veri[i]) - 32); i += 1
            if set_ != 'C':
                kod.append(105 if set_ is None else 99); set_ = 'C'
            while i < j:
                kod.append(int(veri[i:i + 2])); i += 2
        else:
            if set_ != 'B':
                kod.append(104 if set_ is None else 100); set_ = 'B'
            kod.append(ord(veri[i]) - 32); i += 1
    kod.append((kod[0] + sum(k * n for n, k in enumerate(kod[1:], 1))) % 103)
    kod.append(106)
    return kod


def code128_modul_sayisi(veri: str) -> int:
    return sum(sum(map(int, _C128[k])) for k in code128_kodla(veri))


# ───────────────────────── yerleşim ─────────────────────────
@dataclass
class Yerlesim:
    gen: int; yuk: int; dpi: int
    qr: tuple | None            # (x, y, büyütme)
    c128: tuple | None          # (x, y, modül, yükseklik)
    kod_yazi: tuple             # (x, y, font_h, genişlik)
    ad_yazi: tuple              # (x, y, font_h, genişlik, satır)
    alt_yazi: tuple | None      # (x, y, font_h, genişlik)
    uyarilar: list
    duzen: str = 'yan'


QR_MODUL = 21   # QR sürüm 1 (7 karakterlik S###### için yeter)


def yerlesim_hesapla(gen_mm: float, yuk_mm: float, dpi: int, ornek_deger: str = 'S999999') -> Yerlesim:
    """Önce 'yan' düzen (QR solda, barkod sağ sütunda); barkod sığmazsa
    'alt' düzen (barkod alt bantta tüm genişlikte); o da olmazsa yalnız QR."""
    y = _yan_duzen(gen_mm, yuk_mm, dpi, ornek_deger)
    if y.c128 is None:
        alt = _alt_duzen(gen_mm, yuk_mm, dpi, ornek_deger)
        if alt is not None:
            return alt
    return y


def _alt_duzen(gen_mm, yuk_mm, dpi, ornek_deger) -> Yerlesim | None:
    dpm = dpi / 25.4
    W, H = round(gen_mm * dpm), round(yuk_mm * dpm)
    m = round(1.5 * dpm)
    mod = max(2, round(0.25 * dpm))
    bar_gen = (code128_modul_sayisi(ornek_deger) + 20) * mod
    if bar_gen > W - 2 * m:
        mod = 2
        bar_gen = (code128_modul_sayisi(ornek_deger) + 20) * mod
        if bar_gen > W - 2 * m:
            return None
    c_h = max(round(3.5 * dpm), round(0.17 * H))
    c128 = (m + 10 * mod, H - m - c_h, mod, c_h)
    ust_H = c128[1] - round(1 * dpm) - m
    mag = min(10, ust_H // QR_MODUL)
    if mag < 2:
        return None
    qr_kenar = QR_MODUL * mag
    qr = (m, m, mag)
    x0 = m + qr_kenar + round(1.5 * dpm)
    sag_gen = W - x0 - m
    kod_h = max(round(2.2 * dpm), round(0.13 * H))
    ad_h = max(round(1.8 * dpm), round(0.095 * H))
    alt_h = max(round(1.6 * dpm), round(0.075 * H))
    kod_yazi = (x0, m, kod_h, sag_gen)
    ad_y = m + kod_h + round(0.4 * dpm)
    satir = max(1, min(3, (m + ust_H - ad_y) // round(ad_h * 1.1)))
    ad_yazi = (x0, ad_y, ad_h, sag_gen, satir)
    bar_son = m + bar_gen
    if W - m - bar_son >= round(10 * dpm):
        alt_yazi = (bar_son + round(0.5 * dpm), c128[1] + (c_h - alt_h) // 2, alt_h, W - m - bar_son)
    else:
        alt_yazi = None
    return Yerlesim(W, H, dpi, qr, c128, kod_yazi, ad_yazi, alt_yazi, [], duzen='alt')


def _yan_duzen(gen_mm, yuk_mm, dpi, ornek_deger) -> Yerlesim:
    dpm = dpi / 25.4
    W, H = round(gen_mm * dpm), round(yuk_mm * dpm)
    m = round(1.5 * dpm)
    uyari = []

    qr_alan = H - 2 * m
    mag = min(10, qr_alan // (QR_MODUL + 2))
    if mag < 2 or qr_alan > 0.55 * W:
        mag = min(mag, max(0, int(0.4 * W) // (QR_MODUL + 2)))
    qr = None
    x0 = m
    if mag >= 2:
        qr_kenar = QR_MODUL * mag
        qr = (m, (H - qr_kenar) // 2, mag)
        x0 = m + qr_kenar + 2 * mag + round(1 * dpm)
    else:
        uyari.append('QR için yer yetersiz — QR basılmadı')
    sag_gen = W - x0 - m

    moduller = code128_modul_sayisi(ornek_deger) + 20
    c128 = None
    for mod in sorted({max(2, round(0.25 * dpm)), 2}, reverse=True):
        if moduller * mod <= sag_gen:
            c_h = max(round(4 * dpm), round(0.22 * H))
            c128 = (x0 + 10 * mod, H - m - c_h - round(0.09 * H), mod, c_h)
            break
    if c128 is None:
        uyari.append(f'Code128 sığmadı ({moduller * 2 / dpm:.1f} mm gerekir, '
                     f'{sag_gen / dpm:.1f} mm var) — yalnız QR basıldı')

    kod_h = max(round(2.2 * dpm), round(0.15 * H))
    ad_h = max(round(1.8 * dpm), round(0.105 * H))
    alt_h = max(round(1.6 * dpm), round(0.08 * H))
    y = m
    kod_yazi = (x0, y, kod_h, sag_gen)
    y += kod_h + round(0.5 * dpm)
    alt_sinir = (c128[1] if c128 else H - m - alt_h - round(0.5 * dpm))
    satir = max(1, min(3, (alt_sinir - y) // round(ad_h * 1.1)))
    ad_yazi = (x0, y, ad_h, sag_gen, satir)
    alt_yazi = ((x0, c128[1] + c128[3] + round(0.4 * dpm), alt_h, sag_gen) if c128
                else (x0, H - m - alt_h, alt_h, sag_gen))
    return Yerlesim(W, H, dpi, qr, c128, kod_yazi, ad_yazi, alt_yazi, uyari, duzen='yan')


def _sigdir(metin: str, font_h: int, genislik: int, oran=0.52) -> int:
    if not metin:
        return font_h
    return max(12, min(font_h, int(genislik / (len(metin) * oran))))


# ───────────────────────── ZPL ─────────────────────────
def _zpl_kacis(s: str) -> str:
    return s.replace('\\', '\\5C').replace('^', '\\5E').replace('~', '\\7E')


def _font(h: int, font: str) -> str:
    return f'^A0N,{h},{h}' if font == '0' else f'^A@N,{h},{h},{font}'


def zpl_uret(kart: Kart, y: Yerlesim, font: str = '0', adet: int = 1) -> str:
    deger = barkod_degeri(kart.id)
    p = ['^XA', '^CI28', f'^PW{y.gen}', f'^LL{y.yuk}', '^LH0,0']
    if y.qr:
        x, yy, mag = y.qr
        p.append(f'^FO{x},{yy}^BQN,2,{mag}^FDMA,{deger}^FS')
    if y.c128:
        x, yy, mod, h = y.c128
        p.append(f'^FO{x},{yy}^BY{mod}^BCN,{h},N,N,N,A^FD{deger}^FS')
    x, yy, h, w = y.kod_yazi
    h = _sigdir(kart.kodu, h, w)
    p.append(f'^FO{x},{yy}{_font(h, font)}^FB{w},1,0,L,0^FH\\^FD{_zpl_kacis(kart.kodu)}^FS')
    x, yy, h, w, satir = y.ad_yazi
    p.append(f'^FO{x},{yy}{_font(h, font)}^FB{w},{satir},0,L,0^FH\\^FD{_zpl_kacis(kart.adi)}^FS')
    if y.alt_yazi:
        x, yy, h, w = y.alt_yazi
        alt = f'{deger}   {kart.birim}'.strip()
        p.append(f'^FO{x},{yy}{_font(h, font)}^FB{w},1,0,L,0^FH\\^FD{_zpl_kacis(alt)}^FS')
    if int(adet) > 1:
        p.append(f'^PQ{int(adet)},0,1,Y')
    p.append('^XZ')
    return '\n'.join(p)


def toplu_zpl_uret(kalemler: list[tuple[Kart, int]], gen_mm: float, yuk_mm: float,
                   dpi: int = 203, font: str = '0') -> tuple[str, Yerlesim]:
    """[(Kart, kopya_adedi), ...] → (birleşik ZPL metni, Yerlesim)."""
    en_buyuk = barkod_degeri(max((k.id for k, _ in kalemler), default=999999))
    y = yerlesim_hesapla(gen_mm, yuk_mm, dpi, en_buyuk)
    bloklar = [zpl_uret(k, y, font=font, adet=max(1, int(adet))) for k, adet in kalemler if int(adet) > 0]
    return '\n'.join(bloklar), y


# ───────────────────────── yazıcılar ─────────────────────────
def kurulu_yazicilar() -> list[str]:
    """Windows'ta kurulu yerel ve ağ yazıcılarının adları."""
    try:
        import win32print
        return [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
    except Exception:
        return []


def varsayilan_zebra_bul(yazicilar: list[str] | None = None) -> str | None:
    """Kurulu yazıcılar içinde Zebra / ZD220 / ZDesigner geçen ilk yazıcı."""
    liste = kurulu_yazicilar() if yazicilar is None else yazicilar
    aday = [p for p in liste if any(k in p.lower() for k in ('zebra', 'zd2', 'zdesigner'))]
    return aday[0] if aday else None


def usb_yazici_bul(ad: str | None = None) -> str:
    """CLI yardımcısı: yazıcı adını doğrular veya Zebra'yı otomatik bulur."""
    kurulu = kurulu_yazicilar()
    if ad:
        if ad not in kurulu:
            raise SystemExit(f'Yazıcı bulunamadı: {ad} | Kurulu: {kurulu}')
        return ad
    secim = varsayilan_zebra_bul(kurulu)
    if not secim:
        raise SystemExit(f'Zebra yazıcı bulunamadı; --usb "<yazıcı adı>" verin. | Kurulu: {kurulu}')
    return secim


def usb_yaziciya_gonder(yazici: str, zpl: str) -> None:
    """ZPL'i Windows yazıcı kuyruğuna RAW olarak gönderir (USB ZD220t)."""
    import win32print
    h = win32print.OpenPrinter(yazici)
    try:
        win32print.StartDocPrinter(h, 1, ('CEO etiket', None, 'RAW'))
        try:
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, zpl.encode('utf-8'))
            win32print.EndPagePrinter(h)
        finally:
            win32print.EndDocPrinter(h)
    finally:
        win32print.ClosePrinter(h)


def yaziciya_gonder(ip: str, zpl: str, port: int = 9100) -> None:
    with socket.create_connection((ip, port), timeout=10) as s:
        s.sendall(zpl.encode('utf-8'))


# ───────────────────────── PNG / bellek önizleme ─────────────────────────
def _pil_font(h: int, kalin=False):
    from PIL import ImageFont
    ad = 'ARIALNB.TTF' if kalin else 'ARIALN.TTF'
    try:
        return ImageFont.truetype(os.path.join(FONT_DIZIN, ad), h)
    except OSError:
        return ImageFont.load_default()


def _sar(draw, metin, font, genislik, satir):
    kel, satirlar, cur = metin.split(), [], ''
    for k in kel:
        aday = (cur + ' ' + k).strip()
        if draw.textlength(aday, font=font) <= genislik:
            cur = aday
        else:
            if cur:
                satirlar.append(cur)
            cur = k
    if cur:
        satirlar.append(cur)
    if len(satirlar) > satir:
        satirlar = satirlar[:satir]
    return satirlar


def imaj_uret(kart: Kart, y: Yerlesim):
    """PIL Image ('L' gri tonlama) olarak etiket önizlemesi üretir."""
    import qrcode
    from PIL import Image, ImageDraw
    deger = barkod_degeri(kart.id)
    img = Image.new('L', (y.gen, y.yuk), 255)
    d = ImageDraw.Draw(img)
    if y.qr:
        x, yy, mag = y.qr
        q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                          box_size=mag, border=0)
        q.add_data(deger); q.make(fit=False)
        img.paste(q.make_image().convert('L'), (x, yy))
    if y.c128:
        x, yy, mod, h = y.c128
        for k in code128_kodla(deger):
            for n, w in enumerate(_C128[k]):
                w = int(w) * mod
                if n % 2 == 0:
                    d.rectangle([x, yy, x + w - 1, yy + h - 1], fill=0)
                x += w
    x, yy, h, w = y.kod_yazi
    d.text((x, yy), kart.kodu, font=_pil_font(_sigdir(kart.kodu, h, w), True), fill=0)
    x, yy, h, w, satir = y.ad_yazi
    f = _pil_font(h)
    for i, s in enumerate(_sar(d, kart.adi, f, w, satir)):
        d.text((x, yy + i * round(h * 1.1)), s, font=f, fill=0)
    if y.alt_yazi:
        x, yy, h, w = y.alt_yazi
        d.text((x, yy), f'{deger}   {kart.birim}'.strip(), font=_pil_font(h), fill=0)
    d.rectangle([0, 0, y.gen - 1, y.yuk - 1], outline=160)
    return img


def png_bytes_uret(kart: Kart, y: Yerlesim) -> bytes:
    """Bellekte PNG baytları döndürür (PyQt QPixmap.loadFromData için)."""
    buf = io.BytesIO()
    imaj_uret(kart, y).save(buf, format='PNG', dpi=(y.dpi, y.dpi))
    return buf.getvalue()


def png_uret(kart: Kart, y: Yerlesim, yol: str) -> None:
    imaj_uret(kart, y).save(yol, dpi=(y.dpi, y.dpi))
