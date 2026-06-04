#!/usr/bin/env python3
import sys
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import bom_listesi

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])
bom = bom_listesi(conn)

p = bom.get('GMP-200-230602')
if p:
    print('GMP-200-230602 bilesenleri:', len(p['bilesenleri']))
    for b in p['bilesenleri']:
        print(' ', b['kod'], '-', b['ad'][:40])
else:
    print('BOM da yok')
