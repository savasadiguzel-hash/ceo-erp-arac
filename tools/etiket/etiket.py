"""
Stok etiketi üretici (CLI) — Zebra ZPL + PNG önizleme.

Çekirdek mantık `barkod/etiket.py` modülündedir; bu betik komut satırı arayüzüdür.
CEO ERP'den YALNIZCA OKUR.

Örnekler:
  python tools/etiket/etiket.py --kod GMP-200-240431 --kod AKTRMİK0001
  python tools/etiket/etiket.py --bakiyeli --limit 20 --olcu 50x25
  python tools/etiket/etiket.py --id 468311 --olcu 40x20 --dpi 300
  python tools/etiket/etiket.py --kod X --usb                    (USB Zebra'ya gönderir)
  python tools/etiket/etiket.py --kod X --yazici 192.168.1.50   (ağdaki yazıcıya gönderir)
  python tools/etiket/etiket.py --coz S468311                     (okutulan değeri karta çevirir)

Çıktı: tools/etiket/cikti/etiketler_<zaman>.zpl  ve  onizleme_*.png
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from barkod.etiket import (  # noqa: E402,F401
    Kart, Yerlesim, barkod_coz, barkod_degeri,
    kartlari_oku, olcu_coz, png_uret, usb_yazici_bul, usb_yaziciya_gonder,
    yaziciya_gonder, yerlesim_hesapla, zpl_uret,
)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Stok etiketi (ZPL + PNG önizleme) — CEO ERP salt okuma')
    ap.add_argument('--kod', action='append', default=[], help='stok kodu (tekrarlanabilir)')
    ap.add_argument('--id', action='append', type=int, default=[], help='StokKarti.Id')
    ap.add_argument('--bakiyeli', action='store_true', help='bakiyesi > 0 olan tüm aktif kartlar')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--olcu', default='70x30', help='etiket ölçüsü mm, GxY (varsayılan 70x30 — Labelika)')
    ap.add_argument('--dpi', type=int, default=203, choices=[203, 300])
    ap.add_argument('--font', default='0', help="ZPL yazı tipi: '0' ya da yazıcıdaki dosya, örn E:TT0003M_.TTF")
    ap.add_argument('--png', type=int, default=30, help='en fazla kaç PNG önizleme (0 = yok)')
    ap.add_argument('--cikti', default=os.path.join(os.path.dirname(__file__), 'cikti'))
    ap.add_argument('--yazici', help='Zebra IP adresi — verilirse ZPL ağ üzerinden gönderilir')
    ap.add_argument('--usb', nargs='?', const='', default=None,
                    help='USB (Windows) yazıcıya RAW gönder; ad verilmezse Zebra otomatik bulunur')
    ap.add_argument('--coz', help='okutulan barkod değerini karta çevir (örn S468311)')
    a = ap.parse_args()

    from config import DB_DEFAULTS
    from db.baglanti import baglanti_ctx

    if a.coz:
        kid = barkod_coz(a.coz)
        if kid is None:
            print('Tanınmayan barkod:', a.coz); return
        with baglanti_ctx(**DB_DEFAULTS) as conn:
            k = kartlari_oku(conn, idler=[kid])
        print(f'{a.coz} → ' + (f'Id {k[0].id} | {k[0].kodu} | {k[0].adi} | {k[0].birim}' if k else 'kart yok'))
        return

    if not (a.kod or a.id or a.bakiyeli):
        ap.error('--kod, --id veya --bakiyeli verin')
    gen, yuk = olcu_coz(a.olcu)

    with baglanti_ctx(**DB_DEFAULTS) as conn:
        kartlar = kartlari_oku(conn, a.kod, a.id, a.bakiyeli, a.limit)
    if not kartlar:
        print('Etiketlenecek kart yok.'); return

    y = yerlesim_hesapla(gen, yuk, a.dpi, barkod_degeri(max(k.id for k in kartlar)))
    for u in y.uyarilar:
        print('UYARI:', u)

    os.makedirs(a.cikti, exist_ok=True)
    zaman = datetime.now().strftime('%Y%m%d_%H%M%S')
    zpl = '\n'.join(zpl_uret(k, y, a.font) for k in kartlar)
    zpl_yol = os.path.join(a.cikti, f'etiketler_{a.olcu}_{a.dpi}dpi_{zaman}.zpl')
    with open(zpl_yol, 'w', encoding='utf-8') as f:
        f.write(zpl)
    print(f'{len(kartlar)} etiket → {zpl_yol}')

    for k in kartlar[:a.png]:
        guvenli = ''.join(c if c.isalnum() or c in '-_' else '_' for c in k.kodu)
        png_uret(k, y, os.path.join(a.cikti, f'onizleme_{a.olcu}_{guvenli}.png'))
    if a.png:
        print(f'{min(a.png, len(kartlar))} PNG önizleme → {a.cikti}')

    if a.yazici:
        yaziciya_gonder(a.yazici, zpl)
        print(f'Yazıcıya gönderildi: {a.yazici}:9100')
    if a.usb is not None:
        ad = usb_yazici_bul(a.usb or None)
        usb_yaziciya_gonder(ad, zpl)
        print(f'USB yazıcıya gönderildi: {ad}')


if __name__ == '__main__':
    main()
