"""CEO Barkod — Etiket basma sayfası ve tekli etiket penceresi.

CEO ERP'den YALNIZCA OKUR.
Özellikler:
  - 30.11 Sayım hazırlığı: seçili depoda (veya tüm şirkette) bakiyesi > 0 olan aktif kartları tek tıkla yükleme.
  - Barkod okutarak veya stok kodu yazarak listeye kart ekleme / etiket adedini artırma.
  - Kod/ad arama filtresi, görünenleri seçme/kaldırma, kopya adedi düzenleme.
  - Seçili satır için gerçek oranlı canlı PNG önizleme (QR + Code128 + kod/ad/birim).
  - Windows USB RAW yazdırma (`win32print`, Zebra ZD220t), tekli test baskısı ve ZPL dosyası kaydetme.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from barkod.ayar import ayar_oku, ayar_yaz
from barkod.etiket import (
    HAZIR_OLCULER, Kart, barkod_degeri, depo_bakiyeli_kartlar, kurulu_yazicilar,
    olcu_coz, png_bytes_uret, toplu_zpl_uret, usb_yaziciya_gonder,
    varsayilan_zebra_bul, yerlesim_hesapla,
)
from barkod.kod import coz, coz_mesaj

_MAVI_BTN = "background:#3f51b5;color:white;font-size:13px;padding:8px 16px;"
_YESIL_BTN = ("background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2e7d32,stop:1 #43a047);"
              "color:white;font-size:14px;padding:8px 18px;")


def _etiket_ayarlari_oku() -> dict:
    a = ayar_oku()
    return {
        'yazici': a.get('etiket_yazici', ''),
        'olcu': a.get('etiket_olcu', '70x30') or '70x30',
        'dpi': int(a.get('etiket_dpi', 203) or 203),
        'font': a.get('etiket_font', '0') or '0',
    }


def _yazici_kutusu_doldur(cb: QComboBox, kayitli: str = '') -> None:
    cb.blockSignals(True)
    onceki = kayitli or cb.currentData() or ''
    cb.clear()
    liste = kurulu_yazicilar()
    zebra = varsayilan_zebra_bul(liste)
    cb.addItem('— USB / Windows yazıcı seçin —', '')
    for ad in liste:
        etiket = f'★ {ad}' if ad == zebra else ad
        cb.addItem(etiket, ad)
    hedef = onceki if onceki in liste else (zebra or '')
    idx = cb.findData(hedef)
    cb.setCurrentIndex(max(0, idx))
    cb.blockSignals(False)


def _onizleme_ciz(kart: Kart | None, olcu_metni: str, dpi: int,
                  hedef_lbl: QLabel, bilgi_lbl: QLabel, max_gen: int = 380, max_yuk: int = 210) -> bool:
    """Kartın etiket önizlemesini `hedef_lbl` üzerine çizer; ölçü geçerliyse True döner."""
    if kart is None:
        hedef_lbl.setPixmap(QPixmap())
        hedef_lbl.setText('Önizleme için listeden bir kart seçin\nveya barkod okutun.')
        bilgi_lbl.setText('')
        return False
    try:
        gen, yuk = olcu_coz(olcu_metni)
    except ValueError as e:
        hedef_lbl.setPixmap(QPixmap())
        hedef_lbl.setText(str(e))
        bilgi_lbl.setText(f'<span style="color:#c62828">{e}</span>')
        return False

    y = yerlesim_hesapla(gen, yuk, dpi, barkod_degeri(kart.id))
    png = png_bytes_uret(kart, y)
    pix = QPixmap()
    pix.loadFromData(png, 'PNG')
    hedef_lbl.setText('')
    hedef_lbl.setPixmap(pix.scaled(max_gen, max_yuk, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    bilesenler = []
    if y.qr:
        bilesenler.append('QR')
    if y.c128:
        bilesenler.append('Code128')
    duzen_adi = 'Yan düzen' if y.duzen == 'yan' else 'Alt düzen'
    satir1 = (f'<b>{kart.kodu}</b> · Barkod: <b>{barkod_degeri(kart.id)}</b><br>'
              f'<span style="color:#555">{gen:g}×{yuk:g} mm · {dpi} dpi ({y.gen}×{y.yuk} nokta) · '
              f'{duzen_adi} · {" + ".join(bilesenler) or "Yalnız yazı"}</span>')
    if y.uyarilar:
        uy = '<br>'.join(f'⚠ {u}' for u in y.uyarilar)
        satir1 += f'<br><span style="color:#c62828">{uy}</span>'
    bilgi_lbl.setText(satir1)
    return True


# ───────────────────────── arka plan yükleyici ─────────────────────────
class _BakiyeliYukleThread(QThread):
    bitti = pyqtSignal(list, str)   # (list[Kart], depo_etiketi)
    hata = pyqtSignal(str)

    def __init__(self, depo_id: int | None, depo_etiketi: str):
        super().__init__()
        self._depo_id = depo_id
        self._etiket = depo_etiketi

    def run(self):
        try:
            from config import DB_DEFAULTS
            from db.baglanti import baglanti_ctx
            with baglanti_ctx(**DB_DEFAULTS) as conn:
                kartlar = depo_bakiyeli_kartlar(conn, self._depo_id)
            self.bitti.emit(kartlar, self._etiket)
        except Exception as e:
            self.hata.emit(f'{type(e).__name__}: {e}')


# ───────────────────────── tekli etiket penceresi (Sorgula / Sayım kısayolu) ─────────────────────────
class EtiketTekliDialog(QDialog):
    """Tek bir stok kartı için hızlı önizleme + USB yazdırma / ZPL kaydetme / listeye ekleme."""

    def __init__(self, pencere, kart: Kart):
        super().__init__(pencere)
        self.p = pencere
        self.kart = kart
        self.setWindowTitle(f'Etiket Bas — {kart.kodu}')
        self.setMinimumWidth(520)

        ay = _etiket_ayarlari_oku()
        lay = QVBoxLayout(self)

        ust = QLabel(f'<b style="font-size:16px;color:#1a237e">{kart.kodu}</b> '
                     f'<span style="color:#555">({barkod_degeri(kart.id)})</span><br>{kart.adi}')
        ust.setWordWrap(True)
        ust.setTextFormat(Qt.RichText)
        lay.addWidget(ust)

        # Önizleme kutusu
        cerceve = QGroupBox('Etiket Önizleme')
        cv = QVBoxLayout(cerceve)
        self.lbl_img = QLabel()
        self.lbl_img.setAlignment(Qt.AlignCenter)
        self.lbl_img.setMinimumSize(440, 200)
        self.lbl_img.setStyleSheet('background:#fafafa;border:1px dashed #b0bec5;border-radius:6px;padding:8px;')
        cv.addWidget(self.lbl_img)
        self.lbl_bilgi = QLabel()
        self.lbl_bilgi.setWordWrap(True)
        self.lbl_bilgi.setTextFormat(Qt.RichText)
        cv.addWidget(self.lbl_bilgi)
        lay.addWidget(cerceve)

        # Ayarlar
        g_ayar = QGroupBox('Yazdırma Ayarları')
        v_ayar = QVBoxLayout(g_ayar)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel('Yazıcı:'))
        self.yazici = QComboBox()
        _yazici_kutusu_doldur(self.yazici, ay['yazici'])
        r1.addWidget(self.yazici, 1)
        b_yenile = QPushButton('Yenile')
        b_yenile.clicked.connect(lambda: _yazici_kutusu_doldur(self.yazici))
        r1.addWidget(b_yenile)
        v_ayar.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel('Ölçü (mm):'))
        self.olcu = QComboBox()
        self.olcu.setEditable(True)
        for o in HAZIR_OLCULER:
            self.olcu.addItem(o)
        self.olcu.setCurrentText(ay['olcu'])
        self.olcu.currentTextChanged.connect(self._guncelle)
        r2.addWidget(self.olcu)

        r2.addWidget(QLabel('DPI:'))
        self.dpi = QComboBox()
        self.dpi.addItem('203', 203)
        self.dpi.addItem('300', 300)
        self.dpi.setCurrentIndex(max(0, self.dpi.findData(ay['dpi'])))
        self.dpi.currentIndexChanged.connect(self._guncelle)
        r2.addWidget(self.dpi)

        r2.addWidget(QLabel('Kopya adedi:'))
        self.adet = QSpinBox()
        self.adet.setRange(1, 500)
        self.adet.setValue(1)
        r2.addWidget(self.adet)
        r2.addStretch()
        v_ayar.addLayout(r2)
        lay.addWidget(g_ayar)

        # Düğmeler
        alt = QHBoxLayout()
        b_liste = QPushButton('Etiket Listesine Ekle')
        b_liste.clicked.connect(self._listeye_ekle)
        alt.addWidget(b_liste)

        b_zpl = QPushButton('ZPL Kaydet…')
        b_zpl.clicked.connect(self._zpl_kaydet)
        alt.addWidget(b_zpl)

        alt.addStretch()
        b_kapat = QPushButton('Kapat')
        b_kapat.clicked.connect(self.reject)
        alt.addWidget(b_kapat)

        self.b_yazdir = QPushButton('USB Yazdır')
        self.b_yazdir.setStyleSheet(_YESIL_BTN)
        self.b_yazdir.setDefault(True)
        self.b_yazdir.clicked.connect(self._yazdir)
        alt.addWidget(self.b_yazdir)
        lay.addLayout(alt)

        self._font = ay['font']
        self._guncelle()

    def _ayarlari_sakla(self):
        ayar_yaz(
            etiket_yazici=self.yazici.currentData() or '',
            etiket_olcu=self.olcu.currentText().strip(),
            etiket_dpi=int(self.dpi.currentData()),
        )
        if hasattr(self.p, 'etiket'):
            self.p.etiket.ayarlari_tazele()

    def _guncelle(self, *_):
        ok = _onizleme_ciz(self.kart, self.olcu.currentText(), int(self.dpi.currentData()),
                           self.lbl_img, self.lbl_bilgi, max_gen=440, max_yuk=190)
        self.b_yazdir.setEnabled(ok)

    def _zpl_olustur(self) -> str | None:
        try:
            gen, yuk = olcu_coz(self.olcu.currentText())
        except ValueError as e:
            QMessageBox.warning(self, 'Etiket', str(e))
            return None
        zpl, _ = toplu_zpl_uret([(self.kart, self.adet.value())], gen, yuk,
                                dpi=int(self.dpi.currentData()), font=self._font)
        return zpl

    def _yazdir(self):
        yaz = self.yazici.currentData() or ''
        if not yaz:
            QMessageBox.information(
                self, 'Yazıcı seçilmedi',
                'Lütfen listeden Zebra / USB yazıcıyı seçin.\n'
                'Yazıcı henüz bağlı değilse "ZPL Kaydet…" ile dosyaya kaydedebilirsiniz.')
            return
        zpl = self._zpl_olustur()
        if not zpl:
            return
        try:
            usb_yaziciya_gonder(yaz, zpl)
            self._ayarlari_sakla()
            logging.info('Tekli etiket yazdirildi: %s (%s) x%d -> %s',
                         self.kart.kodu, barkod_degeri(self.kart.id), self.adet.value(), yaz)
        except Exception as e:
            QMessageBox.critical(self, 'Yazdırma hatası', f'{type(e).__name__}: {e}')
            return
        self.p._durum(f'Etiket yazdırıldı: {self.kart.kodu} ×{self.adet.value()} → {yaz}')
        self.accept()

    def _zpl_kaydet(self):
        zpl = self._zpl_olustur()
        if not zpl:
            return
        guvenli = ''.join(c if c.isalnum() or c in '-_' else '_' for c in self.kart.kodu)
        oneri = str(Path.home() / 'Desktop' / f'etiket_{guvenli}_{self.olcu.currentText().strip()}.zpl')
        yol, _ = QFileDialog.getSaveFileName(self, 'ZPL Kaydet', oneri, 'ZPL (*.zpl)')
        if not yol:
            return
        Path(yol).write_text(zpl, encoding='utf-8')
        self._ayarlari_sakla()
        self.p._durum(f'ZPL kaydedildi: {yol}')

    def _listeye_ekle(self):
        if hasattr(self.p, 'etiket'):
            self.p.etiket.kart_ekle(self.kart, self.adet.value(), uzerine_ekle=True)
            self._ayarlari_sakla()
            self.p._durum(f'{self.kart.kodu} (×{self.adet.value()}) Etiket listesine eklendi.')
            self.accept()


# ───────────────────────── ana Etiket sayfası (30.11 Sayım Hazırlığı + Günlük Etiket) ─────────────────────────
class EtiketSayfasi(QWidget):
    durum = pyqtSignal(str)
    SUTUN = ['Seç', 'Barkod', 'Stok Kodu', 'Stok Adı', 'Birim', 'Bakiye', 'Etiket Adedi']

    def __init__(self, pencere):
        super().__init__()
        self.p = pencere
        self._satirlar: dict[int, dict] = {}   # kart_id → {'kart': Kart, 'adet': int, 'secili': bool}
        self._sira: list[int] = []
        self._yukleme_thread: _BakiyeliYukleThread | None = None
        self._dolduruluyor = False

        ay = _etiket_ayarlari_oku()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        # ── Üst 1: Yazıcı ve Etiket Boyutu ──
        g_yaz = QGroupBox('Yazıcı ve Etiket Ayarları')
        hy = QHBoxLayout(g_yaz)
        hy.addWidget(QLabel('Yazıcı:'))
        self.yazici = QComboBox()
        self.yazici.setMinimumWidth(250)
        self.yazici.setFocusPolicy(Qt.ClickFocus)
        _yazici_kutusu_doldur(self.yazici, ay['yazici'])
        self.yazici.currentIndexChanged.connect(self._ayar_degisti)
        hy.addWidget(self.yazici, 1)

        self.b_yazici_yenile = QPushButton('Yenile')
        self.b_yazici_yenile.setFocusPolicy(Qt.NoFocus)
        self.b_yazici_yenile.setToolTip('Takılan USB yazıcıları yeniden tara')
        self.b_yazici_yenile.clicked.connect(self._yazicilari_yenile)
        hy.addWidget(self.b_yazici_yenile)

        hy.addWidget(QLabel('Ölçü (mm):'))
        self.olcu = QComboBox()
        self.olcu.setEditable(True)
        self.olcu.setMinimumWidth(95)
        self.olcu.setFocusPolicy(Qt.ClickFocus)
        for o in HAZIR_OLCULER:
            self.olcu.addItem(o)
        self.olcu.setCurrentText(ay['olcu'])
        self.olcu.currentTextChanged.connect(self._ayar_degisti)
        hy.addWidget(self.olcu)

        hy.addWidget(QLabel('DPI:'))
        self.dpi = QComboBox()
        self.dpi.setFocusPolicy(Qt.ClickFocus)
        self.dpi.addItem('203', 203)
        self.dpi.addItem('300', 300)
        self.dpi.setCurrentIndex(max(0, self.dpi.findData(ay['dpi'])))
        self.dpi.currentIndexChanged.connect(self._ayar_degisti)
        hy.addWidget(self.dpi)

        hy.addWidget(QLabel('ZPL Font:'))
        self.zpl_font = QLineEdit(ay['font'])
        self.zpl_font.setMaximumWidth(110)
        self.zpl_font.setFocusPolicy(Qt.ClickFocus)
        self.zpl_font.setToolTip("Varsayılan '0'. Yazıcıya özel Türkçe TTF yüklendiyse örn: E:TT0003M_.TTF")
        self.zpl_font.editingFinished.connect(self._ayar_degisti)
        hy.addWidget(self.zpl_font)
        lay.addWidget(g_yaz)

        # ── Üst 2: Sayım Hazırlığı (Depodan Yükle) & Arama ──
        g_kaynak = QGroupBox('30.11 Sayım Hazırlığı / Kart Seçimi')
        hk = QHBoxLayout(g_kaynak)
        hk.addWidget(QLabel('Depo:'))
        self.depo = QComboBox()
        self.depo.setMinimumWidth(250)
        self.depo.setFocusPolicy(Qt.ClickFocus)
        hk.addWidget(self.depo)

        self.b_depodan = QPushButton('Bakiyeli Kartları Getir (> 0)')
        self.b_depodan.setFocusPolicy(Qt.NoFocus)
        self.b_depodan.setStyleSheet(_MAVI_BTN)
        self.b_depodan.clicked.connect(self.depodan_yukle)
        hk.addWidget(self.b_depodan)

        hk.addSpacing(12)
        hk.addWidget(QLabel('Ara:'))
        self.ara = QLineEdit()
        self.ara.setPlaceholderText('Tabloda kod veya ad süz…')
        self.ara.setClearButtonEnabled(True)
        self.ara.setFocusPolicy(Qt.ClickFocus)
        self.ara.textChanged.connect(self._filtre_uygula)
        hk.addWidget(self.ara, 1)

        self.adet_sor = QCheckBox('Okutunca adet sor')
        self.adet_sor.setFocusPolicy(Qt.NoFocus)
        hk.addWidget(self.adet_sor)
        lay.addWidget(g_kaynak)

        # ── Orta Alan: Sol Tablo + Sağ Canlı Önizleme ──
        sp = QSplitter(Qt.Horizontal)

        sol = QWidget()
        v_sol = QVBoxLayout(sol)
        v_sol.setContentsMargins(0, 0, 4, 0)

        arac = QHBoxLayout()
        self.b_tum_sec = QPushButton('Görünenleri seç')
        self.b_tum_sec.clicked.connect(lambda: self._gorunenleri_isaretle(True))
        self.b_sec_kaldir = QPushButton('Seçimi kaldır')
        self.b_sec_kaldir.clicked.connect(lambda: self._gorunenleri_isaretle(False))
        self.b_adet = QPushButton('Adet düzelt')
        self.b_adet.clicked.connect(self._adet_duzelt)
        self.b_toplu_adet = QPushButton('İşaretlilere adet')
        self.b_toplu_adet.clicked.connect(self._isaretlilere_adet)
        self.b_sil = QPushButton('Satırı sil')
        self.b_sil.clicked.connect(self._satir_sil)
        self.b_temizle = QPushButton('Temizle')
        self.b_temizle.clicked.connect(self._temizle)
        for b in (self.b_tum_sec, self.b_sec_kaldir, self.b_adet, self.b_toplu_adet, self.b_sil, self.b_temizle):
            b.setFocusPolicy(Qt.NoFocus)
            arac.addWidget(b)
        arac.addStretch()
        v_sol.addLayout(arac)

        self.tablo = QTableWidget(0, len(self.SUTUN))
        self.tablo.setHorizontalHeaderLabels(self.SUTUN)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setFocusPolicy(Qt.NoFocus)
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tablo.itemChanged.connect(self._hucre_degisti)
        self.tablo.currentCellChanged.connect(lambda *_: self._onizleme_guncelle())
        self.tablo.cellDoubleClicked.connect(self._cift_tik)
        v_sol.addWidget(self.tablo, 1)
        sp.addWidget(sol)

        # Sağ önizleme paneli
        sag = QGroupBox('Canlı Etiket Önizleme')
        v_sag = QVBoxLayout(sag)
        self.lbl_onizleme = QLabel('Önizleme için listeden bir kart seçin\nveya barkod okutun.')
        self.lbl_onizleme.setAlignment(Qt.AlignCenter)
        self.lbl_onizleme.setWordWrap(True)
        self.lbl_onizleme.setMinimumSize(340, 210)
        self.lbl_onizleme.setStyleSheet(
            'background:#fafafa;border:1px dashed #b0bec5;border-radius:8px;padding:10px;color:#757575;'
        )
        v_sag.addWidget(self.lbl_onizleme, 1)

        self.lbl_onizleme_bilgi = QLabel('')
        self.lbl_onizleme_bilgi.setWordWrap(True)
        self.lbl_onizleme_bilgi.setTextFormat(Qt.RichText)
        self.lbl_onizleme_bilgi.setStyleSheet('padding:4px 2px;font-size:12px;')
        v_sag.addWidget(self.lbl_onizleme_bilgi)

        self.b_test_bas = QPushButton('Seçili Karttan 1 Test Etiketi Bas')
        self.b_test_bas.setFocusPolicy(Qt.NoFocus)
        self.b_test_bas.setMinimumHeight(38)
        self.b_test_bas.clicked.connect(self.tek_test_bas)
        v_sag.addWidget(self.b_test_bas)
        sp.addWidget(sag)
        sp.setSizes([740, 400])
        lay.addWidget(sp, 1)

        # ── Alt Çubuk: Özet + ZPL Kaydet + Toplu USB Yazdır ──
        alt = QHBoxLayout()
        self.ozet = QLabel('Liste boş.')
        self.ozet.setStyleSheet('font-weight:bold;color:#3949ab;font-size:13px;')
        alt.addWidget(self.ozet, 1)

        self.b_zpl = QPushButton('İşaretlileri ZPL Kaydet…')
        self.b_zpl.setFocusPolicy(Qt.NoFocus)
        self.b_zpl.setMinimumHeight(42)
        self.b_zpl.clicked.connect(self.zpl_kaydet)
        alt.addWidget(self.b_zpl)

        self.b_yazdir = QPushButton('İşaretli Etiketleri Yazdır (USB)')
        self.b_yazdir.setFocusPolicy(Qt.NoFocus)
        self.b_yazdir.setMinimumHeight(42)
        self.b_yazdir.setMinimumWidth(240)
        self.b_yazdir.setStyleSheet(_YESIL_BTN)
        self.b_yazdir.clicked.connect(self.toplu_yazdir)
        alt.addWidget(self.b_yazdir)
        lay.addLayout(alt)

        self._buton_durumlari()

    # ── kurulum / ayarlar ──
    def depolari_doldur(self, depolar: dict):
        self.depo.blockSignals(True)
        self.depo.clear()
        self.depo.addItem('00 - TÜM DEPOLAR (Şirket bakiyesi > 0)', 0)
        for i, ad in depolar.items():
            self.depo.addItem(ad, i)
        idx = self.depo.findData(2)
        if idx >= 0:
            self.depo.setCurrentIndex(idx)
        self.depo.blockSignals(False)

    def ayarlari_tazele(self):
        ay = _etiket_ayarlari_oku()
        _yazici_kutusu_doldur(self.yazici, ay['yazici'])
        self.olcu.blockSignals(True); self.olcu.setCurrentText(ay['olcu']); self.olcu.blockSignals(False)
        self.dpi.blockSignals(True); self.dpi.setCurrentIndex(max(0, self.dpi.findData(ay['dpi']))); self.dpi.blockSignals(False)
        self.zpl_font.setText(ay['font'])
        self._onizleme_guncelle()

    def _yazicilari_yenile(self):
        _yazici_kutusu_doldur(self.yazici)
        secili = self.yazici.currentData()
        self._ayar_degisti()
        self.durum.emit(f'Yazıcı listesi yenilendi. Seçili: {secili or "yok"}')

    def _ayar_degisti(self, *_):
        ayar_yaz(
            etiket_yazici=self.yazici.currentData() or '',
            etiket_olcu=self.olcu.currentText().strip(),
            etiket_dpi=int(self.dpi.currentData()),
            etiket_font=self.zpl_font.text().strip() or '0',
        )
        self._onizleme_guncelle()

    # ── veri ekleme / okutma ──
    def okut(self, deger: str) -> bool:
        kid, drm = coz(self.p.conn, deger)
        if not kid:
            self.durum.emit(coz_mesaj(drm, deger))
            return False
        oz = self.p.kart_ozet(kid)
        adet = 1
        if self.adet_sor.isChecked():
            v, ok = QInputDialog.getInt(self, 'Etiket adedi',
                                        f"{oz['kodu']}\n{oz['adi']}\nKaç adet etiket basılsın?", 1, 1, 500)
            if not ok:
                return False
            adet = v
        # Mevcut seçili deponun bakiyesini de gösterelim
        depo_id = self.depo.currentData()
        from barkod.sorgu import depo_bakiyeleri
        bak_map = depo_bakiyeleri(self.p.conn, [kid], depo_id=None if not depo_id else int(depo_id))
        bak = round(sum(bak_map.values()), 6)
        kart = Kart(kid, oz['kodu'], oz['adi'], oz['birim'], bak, oz['aktif'])
        toplam_adet = self.kart_ekle(kart, adet, uzerine_ekle=True)
        uyari = ' (PASİF KART)' if not oz['aktif'] else ''
        self.durum.emit(f"{oz['kodu']} → {toplam_adet} etiket{uyari}")
        return True

    def kart_ekle(self, kart: Kart, adet: int = 1, uzerine_ekle: bool = True) -> int:
        if kart.id in self._satirlar:
            mevcut = self._satirlar[kart.id]
            mevcut['adet'] = (mevcut['adet'] + adet) if uzerine_ekle else adet
            mevcut['secili'] = True
            mevcut['kart'] = kart
            self._sira.remove(kart.id)
        else:
            self._satirlar[kart.id] = {'kart': kart, 'adet': max(1, int(adet)), 'secili': True}
        self._sira.insert(0, kart.id)
        self._tabloyu_yenile(sec_kid=kart.id)
        return self._satirlar[kart.id]['adet']

    def depodan_yukle(self):
        if not self.p.conn:
            QMessageBox.information(self, 'Etiket', 'Veritabanı bağlantısı henüz kurulmadı, birkaç saniye bekleyin.')
            return
        if self._yukleme_thread and self._yukleme_thread.isRunning():
            return
        if self._satirlar:
            cevap = QMessageBox.question(
                self, 'Bakiyeli kartları yükle',
                'Mevcut liste temizlenip seçili depodaki bakiyeli kartlar yüklensin mi?\n'
                '(Hayır derseniz mevcut listenin üzerine eklenir.)',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if cevap == QMessageBox.Cancel:
                return
            if cevap == QMessageBox.Yes:
                self._satirlar.clear()
                self._sira.clear()

        secim = self.depo.currentData()
        depo_id = None if not secim else int(secim)
        etiket = self.depo.currentText()
        self.b_depodan.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.durum.emit(f'Bakiyeli kartlar yükleniyor: {etiket}…')

        self._yukleme_thread = _BakiyeliYukleThread(depo_id, etiket)
        self._yukleme_thread.bitti.connect(self._depodan_yuklendi)
        self._yukleme_thread.hata.connect(self._depodan_hata)
        self._yukleme_thread.start()

    def _depodan_yuklendi(self, kartlar: list[Kart], depo_etiketi: str):
        QApplication.restoreOverrideCursor()
        self.b_depodan.setEnabled(True)
        eklenen = 0
        for k in kartlar:
            if k.id not in self._satirlar:
                self._satirlar[k.id] = {'kart': k, 'adet': 1, 'secili': True}
                self._sira.append(k.id)
                eklenen += 1
            else:
                self._satirlar[k.id]['kart'] = k
        self._tabloyu_yenile(sec_kid=self._sira[0] if self._sira else None)
        self.durum.emit(f'{depo_etiketi}: {len(kartlar)} bakiyeli kart bulundu ({eklenen} yeni eklendi).')
        self.p.okut.setFocus()

    def _depodan_hata(self, hata: str):
        QApplication.restoreOverrideCursor()
        self.b_depodan.setEnabled(True)
        QMessageBox.critical(self, 'Etiket', f'Kartlar yüklenemedi:\n{hata}')

    # ── tablo işlemleri ──
    def _tabloyu_yenile(self, sec_kid: int | None = None):
        from barkod.ui.ana_pencere import _hucre
        self._dolduruluyor = True
        self.tablo.setUpdatesEnabled(False)
        try:
            self.tablo.setRowCount(len(self._sira))
            sec_satir = 0
            q = self.ara.text().strip().casefold()
            for r, kid in enumerate(self._sira):
                kayit = self._satirlar[kid]
                k: Kart = kayit['kart']

                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                chk.setCheckState(Qt.Checked if kayit['secili'] else Qt.Unchecked)
                chk.setData(Qt.UserRole, kid)
                self.tablo.setItem(r, 0, chk)

                self.tablo.setItem(r, 1, _hucre(barkod_degeri(kid)))
                self.tablo.setItem(r, 2, _hucre(k.kodu))
                self.tablo.setItem(r, 3, _hucre(k.adi))
                self.tablo.setItem(r, 4, _hucre(k.birim))
                self.tablo.setItem(r, 5, _hucre(k.bakiye, True))
                self.tablo.setItem(r, 6, _hucre(kayit['adet'], True))

                if not k.aktif:
                    for c in range(1, len(self.SUTUN)):
                        self.tablo.item(r, c).setForeground(QColor('#c62828'))

                gizli = bool(q and q not in k.kodu.casefold() and q not in k.adi.casefold()
                             and q not in barkod_degeri(kid).casefold())
                self.tablo.setRowHidden(r, gizli)
                if kid == sec_kid:
                    sec_satir = r

            if self._sira:
                self.tablo.selectRow(sec_satir)
        finally:
            self.tablo.setUpdatesEnabled(True)
            self._dolduruluyor = False
        self._ozet_guncelle()
        self._onizleme_guncelle()

    def _filtre_uygula(self):
        q = self.ara.text().strip().casefold()
        self.tablo.setUpdatesEnabled(False)
        try:
            for r in range(self.tablo.rowCount()):
                kid = int(self.tablo.item(r, 0).data(Qt.UserRole))
                k: Kart = self._satirlar[kid]['kart']
                gizli = bool(q and q not in k.kodu.casefold() and q not in k.adi.casefold()
                             and q not in barkod_degeri(kid).casefold())
                self.tablo.setRowHidden(r, gizli)
        finally:
            self.tablo.setUpdatesEnabled(True)
        self._ozet_guncelle()

    def _hucre_degisti(self, item: QTableWidgetItem):
        if self._dolduruluyor or item.column() != 0:
            return
        kid = item.data(Qt.UserRole)
        if kid is not None and int(kid) in self._satirlar:
            self._satirlar[int(kid)]['secili'] = (item.checkState() == Qt.Checked)
            self._ozet_guncelle()

    def _gorunenleri_isaretle(self, sec: bool):
        self._dolduruluyor = True
        self.tablo.setUpdatesEnabled(False)
        try:
            durum = Qt.Checked if sec else Qt.Unchecked
            for r in range(self.tablo.rowCount()):
                if not self.tablo.isRowHidden(r):
                    it = self.tablo.item(r, 0)
                    kid = int(it.data(Qt.UserRole))
                    self._satirlar[kid]['secili'] = sec
                    it.setCheckState(durum)
        finally:
            self.tablo.setUpdatesEnabled(True)
            self._dolduruluyor = False
        self._ozet_guncelle()

    def _secili_kid(self) -> int | None:
        r = self.tablo.currentRow()
        if r < 0 or self.tablo.item(r, 0) is None:
            return None
        return int(self.tablo.item(r, 0).data(Qt.UserRole))

    def _cift_tik(self, row: int, col: int):
        if col == 0:
            return
        self._adet_duzelt()

    def _adet_duzelt(self):
        from barkod.ui.ana_pencere import _hucre
        kid = self._secili_kid()
        if kid is None:
            return
        kayit = self._satirlar[kid]
        k: Kart = kayit['kart']
        v, ok = QInputDialog.getInt(self, 'Etiket adedi', f'{k.kodu}\n{k.adi}\nEtiket kopya adedi:',
                                    kayit['adet'], 1, 500)
        if not ok:
            return
        kayit['adet'] = v
        r = self.tablo.currentRow()
        if r >= 0:
            self._dolduruluyor = True
            self.tablo.setItem(r, 6, _hucre(v, True))
            self._dolduruluyor = False
        self._ozet_guncelle()

    def _isaretlilere_adet(self):
        from barkod.ui.ana_pencere import _hucre
        hedefler = [kid for kid in self._sira if self._satirlar[kid]['secili']]
        if not hedefler:
            QMessageBox.information(self, 'Etiket', 'Önce listeden en az bir kart işaretleyin.')
            return
        v, ok = QInputDialog.getInt(
            self, 'Toplu etiket adedi',
            f'İşaretli {len(hedefler)} kartın her biri için kaç adet etiket basılsın?', 1, 1, 500)
        if not ok:
            return
        self._dolduruluyor = True
        self.tablo.setUpdatesEnabled(False)
        try:
            for r in range(self.tablo.rowCount()):
                kid = int(self.tablo.item(r, 0).data(Qt.UserRole))
                if self._satirlar[kid]['secili']:
                    self._satirlar[kid]['adet'] = v
                    self.tablo.setItem(r, 6, _hucre(v, True))
        finally:
            self.tablo.setUpdatesEnabled(True)
            self._dolduruluyor = False
        self._ozet_guncelle()

    def _satir_sil(self):
        kid = self._secili_kid()
        if kid is None:
            return
        self._satirlar.pop(kid, None)
        self._sira.remove(kid)
        self._tabloyu_yenile(sec_kid=self._sira[0] if self._sira else None)

    def _temizle(self):
        if not self._satirlar:
            return
        if QMessageBox.question(self, 'Listeyi temizle', 'Etiket listesi temizlensin mi?') != QMessageBox.Yes:
            return
        self._satirlar.clear()
        self._sira.clear()
        self._tabloyu_yenile()

    # ── önizleme ve durum ──
    def _onizleme_guncelle(self):
        kid = self._secili_kid()
        kart = self._satirlar[kid]['kart'] if (kid is not None and kid in self._satirlar) else None
        ok = _onizleme_ciz(kart, self.olcu.currentText(), int(self.dpi.currentData()),
                           self.lbl_onizleme, self.lbl_onizleme_bilgi)
        self.b_test_bas.setEnabled(bool(kart and ok))

    def _isaretli_kalemler(self) -> list[tuple[Kart, int]]:
        return [(self._satirlar[kid]['kart'], self._satirlar[kid]['adet'])
                for kid in self._sira if self._satirlar[kid]['secili']]

    def _ozet_guncelle(self):
        toplam_kart = len(self._sira)
        gorunen = sum(1 for r in range(self.tablo.rowCount()) if not self.tablo.isRowHidden(r))
        isaretli = self._isaretli_kalemler()
        toplam_etiket = sum(a for _, a in isaretli)
        if not toplam_kart:
            self.ozet.setText('Liste boş.')
        else:
            filtre_ek = f' (görünen {gorunen})' if gorunen != toplam_kart else ''
            self.ozet.setText(
                f'Listedeki: {toplam_kart} kart{filtre_ek} · '
                f'İşaretli: {len(isaretli)} kart ({toplam_etiket} adet etiket)'
            )
        self._buton_durumlari()

    def _buton_durumlari(self):
        var = bool(self._sira)
        secili_var = any(v['secili'] for v in self._satirlar.values())
        for b in (self.b_tum_sec, self.b_sec_kaldir, self.b_adet, self.b_toplu_adet, self.b_sil, self.b_temizle):
            b.setEnabled(var)
        self.b_zpl.setEnabled(secili_var)
        self.b_yazdir.setEnabled(secili_var)
        self.b_test_bas.setEnabled(self._secili_kid() is not None)

    # ── yazdırma / dışa aktarma ──
    def _gecerli_olcu(self) -> tuple[float, float] | None:
        try:
            return olcu_coz(self.olcu.currentText())
        except ValueError as e:
            QMessageBox.warning(self, 'Etiket ölçüsü', str(e))
            return None

    def tek_test_bas(self):
        kid = self._secili_kid()
        if kid is None:
            return
        yaz = self.yazici.currentData() or ''
        if not yaz:
            QMessageBox.information(self, 'Yazıcı seçilmedi', 'Önce üstten USB / Zebra yazıcıyı seçin.')
            return
        olcu = self._gecerli_olcu()
        if not olcu:
            return
        kart: Kart = self._satirlar[kid]['kart']
        zpl, _ = toplu_zpl_uret([(kart, 1)], olcu[0], olcu[1],
                                dpi=int(self.dpi.currentData()),
                                font=self.zpl_font.text().strip() or '0')
        try:
            usb_yaziciya_gonder(yaz, zpl)
            logging.info('Test etiketi yazdirildi: %s (%s) x1 -> %s', kart.kodu, barkod_degeri(kart.id), yaz)
        except Exception as e:
            QMessageBox.critical(self, 'Yazdırma hatası', f'{type(e).__name__}: {e}')
            return
        self.durum.emit(f'1 adet test etiketi gönderildi: {kart.kodu} → {yaz}')
        self.p.okut.setFocus()

    def toplu_yazdir(self):
        kalemler = self._isaretli_kalemler()
        if not kalemler:
            return
        yaz = self.yazici.currentData() or ''
        if not yaz:
            QMessageBox.information(
                self, 'Yazıcı seçilmedi',
                'Lütfen üstteki listeden Zebra / USB yazıcıyı seçin.\n'
                'Yazıcı henüz bağlı değilse "İşaretlileri ZPL Kaydet…" ile dosyaya kaydedebilirsiniz.')
            return
        olcu = self._gecerli_olcu()
        if not olcu:
            return

        toplam_adet = sum(a for _, a in kalemler)
        zpl, y = toplu_zpl_uret(kalemler, olcu[0], olcu[1],
                                dpi=int(self.dpi.currentData()),
                                font=self.zpl_font.text().strip() or '0')
        uyari_html = ''
        if y.uyarilar:
            uyari_html = '<br><span style="color:#c62828">' + '<br>'.join(y.uyarilar) + '</span>'

        onay = QMessageBox.question(
            self, 'Etiketleri Yazdır',
            f'<b>Yazıcı:</b> {yaz}<br>'
            f'<b>Ölçü:</b> {olcu[0]:g}×{olcu[1]:g} mm ({self.dpi.currentData()} dpi)<br>'
            f'<b>Basılacak:</b> {len(kalemler)} stok kartı · toplam <b>{toplam_adet} adet etiket</b>'
            f'{uyari_html}<br><br>Yazıcıya gönderilsin mi?',
        )
        if onay != QMessageBox.Yes:
            return

        try:
            usb_yaziciya_gonder(yaz, zpl)
            logging.info('Toplu etiket yazdirildi: %d kart (%d etiket) -> %s',
                         len(kalemler), toplam_adet, yaz)
        except Exception as e:
            QMessageBox.critical(self, 'Yazdırma hatası', f'{type(e).__name__}: {e}')
            return
        self.durum.emit(f'{len(kalemler)} kart ({toplam_adet} etiket) yazıcıya gönderildi: {yaz}')
        self.p.okut.setFocus()

    def zpl_kaydet(self):
        kalemler = self._isaretli_kalemler()
        if not kalemler:
            return
        olcu = self._gecerli_olcu()
        if not olcu:
            return
        toplam_adet = sum(a for _, a in kalemler)
        oneri = str(Path.home() / 'Desktop' /
                    f'etiketler_{olcu[0]:g}x{olcu[1]:g}_{datetime.now():%Y%m%d_%H%M}.zpl')
        yol, _ = QFileDialog.getSaveFileName(self, 'ZPL Dosyası Kaydet', oneri, 'ZPL (*.zpl)')
        if not yol:
            return
        zpl, _ = toplu_zpl_uret(kalemler, olcu[0], olcu[1],
                                dpi=int(self.dpi.currentData()),
                                font=self.zpl_font.text().strip() or '0')
        Path(yol).write_text(zpl, encoding='utf-8')
        self.durum.emit(f'ZPL kaydedildi ({len(kalemler)} kart, {toplam_adet} etiket): {yol}')
        self.p.okut.setFocus()
