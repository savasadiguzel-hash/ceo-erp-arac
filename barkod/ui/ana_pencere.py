"""CEO Barkod — ayrı program ana penceresi.

Okuyucu klavye kaması (HID) modunda çalışır: barkodu okutma kutusuna yazar
ve Enter gönderir. Cihaz yokken kutuya S468311 + Enter yazmak aynı işi görür.

Faz 1 modları (ERP'ye YAZMAZ): Sorgula, Sayım.
Faz 2+ (Giriş / Çıkış / Transfer / Reçete) henüz kapalı.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog,
    QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QStackedWidget, QStatusBar, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from barkod.kod import barkod_degeri, okutma_coz

_STIL = """
QMainWindow,QWidget{font-family:'Segoe UI';font-size:13px;background:#f0f2f5;}
QGroupBox{border:1.5px solid #c5cae9;border-radius:8px;margin-top:8px;
    padding:10px 8px 8px 8px;background:white;}
QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;color:#3949ab;font-weight:bold;}
QLineEdit,QComboBox{border:1.5px solid #9fa8da;border-radius:6px;padding:5px 8px;background:white;}
QPushButton{border-radius:6px;padding:8px 16px;font-weight:bold;border:none;
    background:#e8eaf6;color:#1a237e;}
QPushButton:hover{background:#c5cae9;}
QPushButton:checked{background:#3f51b5;color:white;}
QPushButton:disabled{background:#e0e0e0;color:#9e9e9e;}
QTableWidget{border:1px solid #e8eaf6;background:white;gridline-color:#eeeeee;}
QHeaderView::section{background:#e8eaf6;color:#3949ab;font-weight:bold;padding:5px;border:none;}
"""
_OKUT_NORMAL = ("font-size:26px;font-weight:bold;padding:10px 14px;border:3px solid #3f51b5;"
                "border-radius:10px;background:white;")
_OKUT_IYI = _OKUT_NORMAL.replace('#3f51b5', '#2e7d32').replace('background:white', 'background:#e8f5e9')
_OKUT_KOTU = _OKUT_NORMAL.replace('#3f51b5', '#c62828').replace('background:white', 'background:#ffebee')


def _tablo(basliklar: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(basliklar))
    t.setHorizontalHeaderLabels(basliklar)
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setFocusPolicy(Qt.NoFocus)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def _hucre(v, sayi=False) -> QTableWidgetItem:
    if sayi:
        v = f'{v:,.4f}'.rstrip('0').rstrip('.').replace(',', 'X').replace('.', ',').replace('X', '.')
    it = QTableWidgetItem('' if v is None else str(v))
    if sayi:
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


# ───────────────────────── thread'ler ─────────────────────────
class _BaglanThread(QThread):
    bitti = pyqtSignal(object)
    hata = pyqtSignal(str)

    def run(self):
        try:
            from config import DB_DEFAULTS
            from db.baglanti import get_connection
            self.bitti.emit(get_connection(**DB_DEFAULTS))
        except Exception as e:
            self.hata.emit(str(e))


class _SorguThread(QThread):
    bitti = pyqtSignal(object, str)
    hata = pyqtSignal(str)

    def __init__(self, conn, deger: str):
        super().__init__()
        self._conn, self._deger = conn, deger

    def run(self):
        try:
            from barkod.sorgu import kart_bilgi
            kid = okutma_coz(self._conn, self._deger)
            self.bitti.emit(kart_bilgi(self._conn, kid) if kid else None, self._deger)
        except Exception as e:
            self.hata.emit(f'{type(e).__name__}: {e}')


# ───────────────────────── Sorgula sayfası ─────────────────────────
class SorgulaSayfasi(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.baslik = QLabel('Bir barkod okutun.')
        self.baslik.setWordWrap(True)
        self.baslik.setTextFormat(Qt.RichText)
        self.baslik.setStyleSheet('background:white;border:1px solid #c5cae9;border-radius:8px;padding:10px;font-size:15px;')
        lay.addWidget(self.baslik)

        sp = QSplitter(Qt.Vertical)
        ust = QSplitter(Qt.Horizontal)
        g1 = QGroupBox('Depo bakiyeleri')
        QVBoxLayout(g1).addWidget(t1 := _tablo(['Depo', 'Bakiye']))
        g2 = QGroupBox('Hangi reçetede kaç adet')
        QVBoxLayout(g2).addWidget(t2 := _tablo(['Mamul', 'Adı', 'Hat', 'Adet', 'Birim']))
        ust.addWidget(g1); ust.addWidget(g2); ust.setSizes([300, 700])
        g3 = QGroupBox('Son hareketler')
        QVBoxLayout(g3).addWidget(t3 := _tablo(['Tarih', 'İşlem', 'Belge', 'Depo', 'Miktar', 'Not']))
        sp.addWidget(ust); sp.addWidget(g3); sp.setSizes([320, 260])
        lay.addWidget(sp, 1)
        self.t_depo, self.t_recete, self.t_hareket = t1, t2, t3

    def goster(self, k, depo_adlari: dict):
        from barkod.sorgu import islem_adi  # noqa: F401
        durum = '' if k.aktif else ' <span style="color:#c62828">(PASİF KART)</span>'
        self.baslik.setText(
            f'<b style="font-size:20px;color:#1a237e">{k.kodu}</b>{durum}<br>{k.adi}<br>'
            f'<span style="color:#757575">Barkod {barkod_degeri(k.id)} · Birim {k.birim or "-"} · '
            f'Toplam bakiye <b>{k.toplam_bakiye:g}</b></span>')

        self.t_depo.setRowCount(0)
        for d, m in sorted(k.depo_bakiye.items(), key=lambda x: -x[1]):
            r = self.t_depo.rowCount(); self.t_depo.insertRow(r)
            self.t_depo.setItem(r, 0, _hucre(depo_adlari.get(d, f'Depo {d}')))
            it = _hucre(m, True)
            if m < 0:
                it.setForeground(QColor('#c62828'))
            self.t_depo.setItem(r, 1, it)

        self.t_recete.setRowCount(0)
        for u in k.recete_kullanim:
            r = self.t_recete.rowCount(); self.t_recete.insertRow(r)
            for c, v in enumerate((u['mamul_kodu'], u['mamul_adi'], u['hat'])):
                self.t_recete.setItem(r, c, _hucre(v))
            self.t_recete.setItem(r, 3, _hucre(u['miktar'], True))
            self.t_recete.setItem(r, 4, _hucre(u['birim']))
        for m in k.dolayli_mamuller:
            r = self.t_recete.rowCount(); self.t_recete.insertRow(r)
            for c, v in enumerate((m['kodu'], m['adi'], f'dolaylı (seviye {m["seviye"]})')):
                it = _hucre(v); it.setForeground(QColor('#757575'))
                self.t_recete.setItem(r, c, it)
        if not k.recete_kullanim:
            self.t_recete.insertRow(0)
            self.t_recete.setItem(0, 0, _hucre('Hiçbir aktif reçetede yok'))

        self.t_hareket.setRowCount(0)
        for h in k.son_hareketler:
            r = self.t_hareket.rowCount(); self.t_hareket.insertRow(r)
            depo = depo_adlari.get(h['depo'], h['depo'] or '')
            if h['karsi_depo']:
                depo = f"{depo} → {depo_adlari.get(h['karsi_depo'], h['karsi_depo'])}"
            islem = h['islem'] + (' (faturalaştı)' if h['faturalasmis'] else '')
            vals = (h['tarih'].strftime('%d.%m.%Y') if h['tarih'] else '', islem, h['belge'], depo)
            for c, v in enumerate(vals):
                self.t_hareket.setItem(r, c, _hucre(v))
            self.t_hareket.setItem(r, 4, _hucre(h['miktar'], True))
            self.t_hareket.setItem(r, 5, _hucre(h['notlar']))

    def bulunamadi(self, deger: str):
        self.baslik.setText(f'<b style="color:#c62828;font-size:18px">Tanınmayan barkod / kod: {deger}</b>')
        for t in (self.t_depo, self.t_recete, self.t_hareket):
            t.setRowCount(0)


# ───────────────────────── Sayım sayfası ─────────────────────────
class SayimSayfasi(QWidget):
    durum = pyqtSignal(str)

    SUTUN = ['Barkod', 'Stok Kodu', 'Stok Adı', 'Birim', 'Sayılan', 'Son okutma']

    def __init__(self, pencere: 'BarkodPencere'):
        super().__init__()
        self.p = pencere
        self.oturum = None
        self._kart_cache: dict[int, dict] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        g = QGroupBox('Sayım oturumu')
        h = QHBoxLayout(g)
        h.addWidget(QLabel('Depo:'))
        self.depo = QComboBox(); self.depo.setMinimumWidth(260)
        h.addWidget(self.depo)
        h.addWidget(QLabel('Sayan:'))
        self.sayan = QLineEdit(); self.sayan.setMaximumWidth(160)
        h.addWidget(self.sayan)
        self.b_yeni = QPushButton('Yeni sayım'); self.b_yeni.clicked.connect(self.yeni)
        self.b_devam = QPushButton('Yarım kalanı aç'); self.b_devam.clicked.connect(self.devam)
        self.b_excel = QPushButton('Excel'); self.b_excel.clicked.connect(self.excel)
        self.b_bitir = QPushButton('Bitir'); self.b_bitir.clicked.connect(self.bitir)
        for b in (self.b_yeni, self.b_devam, self.b_excel, self.b_bitir):
            b.setFocusPolicy(Qt.NoFocus); h.addWidget(b)
        h.addStretch()
        lay.addWidget(g)

        h2 = QHBoxLayout()
        self.adet_sor = QCheckBox('Okutunca adet sor (kutu/paket sayımı)')
        self.adet_sor.setFocusPolicy(Qt.NoFocus)
        h2.addWidget(self.adet_sor)
        h2.addStretch()
        self.ozet = QLabel('Oturum yok.')
        self.ozet.setStyleSheet('font-weight:bold;color:#3949ab;')
        h2.addWidget(self.ozet)
        self.b_duzelt = QPushButton('Seçili adedi düzelt'); self.b_duzelt.clicked.connect(self.duzelt)
        self.b_sil = QPushButton('Seçili satırı sil'); self.b_sil.clicked.connect(self.sil)
        for b in (self.b_duzelt, self.b_sil):
            b.setFocusPolicy(Qt.NoFocus); h2.addWidget(b)
        lay.addLayout(h2)

        self.tablo = _tablo(self.SUTUN)
        self.tablo.setColumnWidth(2, 420)
        lay.addWidget(self.tablo, 1)
        self._butonlar()

    def depolari_doldur(self, depolar: dict):
        self.depo.clear()
        for i, ad in depolar.items():
            self.depo.addItem(ad, i)
        i = self.depo.findData(2)
        if i >= 0:
            self.depo.setCurrentIndex(i)

    def _butonlar(self):
        var = self.oturum is not None
        self.depo.setEnabled(not var)
        self.sayan.setEnabled(not var)
        self.b_yeni.setEnabled(not var)
        self.b_devam.setEnabled(not var)
        for b in (self.b_excel, self.b_bitir, self.b_duzelt, self.b_sil):
            b.setEnabled(var)

    # ── oturum ──
    def yeni(self):
        from barkod.sayim import SayimOturumu
        if not self.p.conn:
            return
        self.oturum = SayimOturumu.yeni(self.depo.currentData(), self.depo.currentText(), self.sayan.text().strip())
        self._yenile(); self._butonlar()
        self.durum.emit(f'Sayım başladı: {self.oturum.depo_adi}. Okutmaya başlayın.')

    def devam(self):
        from barkod.sayim import SayimOturumu, acik_oturumlar
        dosyalar = acik_oturumlar()
        if not dosyalar:
            QMessageBox.information(self, 'Sayım', 'Yarım kalmış sayım yok.'); return
        adlar = []
        for p in dosyalar:
            o = SayimOturumu.yukle(p)
            adlar.append(f'{o.baslangic} · {o.depo_adi} · {len(o.satirlar)} kalem · {o.sayan}')
        sec, ok = QInputDialog.getItem(self, 'Yarım kalan sayım', 'Oturum:', adlar, 0, False)
        if ok:
            self.oturum = SayimOturumu.yukle(dosyalar[adlar.index(sec)])
            self._yenile(); self._butonlar()

    def bitir(self):
        if not self.oturum:
            return
        if QMessageBox.question(self, 'Sayımı bitir',
                                'Sayım bitirilsin mi? (Excel çıktısı ister misiniz diye ayrıca sorulur)') != QMessageBox.Yes:
            return
        self.oturum.bitir()
        if QMessageBox.question(self, 'Excel', 'Sayım Excel\'i şimdi alınsın mı?') == QMessageBox.Yes:
            self.excel()
        self.oturum = None
        self.tablo.setRowCount(0); self.ozet.setText('Oturum yok.'); self._butonlar()

    def excel(self):
        from barkod.sayim import excel_yaz
        if not self.oturum:
            return
        oneri = str(Path.home() / 'Desktop' / f'sayim_{datetime.now():%Y%m%d_%H%M}.xlsx')
        yol, _ = QFileDialog.getSaveFileName(self, 'Sayım Excel', oneri, 'Excel (*.xlsx)')
        if not yol:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            excel_yaz(self.p.conn, self.oturum, yol)
        except Exception as e:
            QMessageBox.critical(self, 'Excel', str(e)); return
        finally:
            QApplication.restoreOverrideCursor()
        self.durum.emit(f'Excel yazıldı: {yol}')

    # ── okutma ──
    def okut(self, deger: str) -> bool:
        if not self.oturum:
            self.durum.emit('Önce "Yeni sayım" başlatın.')
            return False
        kid = okutma_coz(self.p.conn, deger)
        if not kid:
            self.durum.emit(f'Tanınmayan barkod / kod: {deger}')
            return False
        k = self._kart(kid)
        miktar = 1.0
        if self.adet_sor.isChecked():
            miktar, ok = QInputDialog.getDouble(self, 'Adet', f"{k['kodu']}\n{k['adi']}\nAdet:", 1, 0, 1e9, 3)
            if not ok:
                return False
        s = self.oturum.ekle(kid, k['kodu'], k['adi'], k['birim'], miktar)
        self._yenile(vurgu=kid)
        uyari = ' (PASİF KART)' if not k['aktif'] else ''
        self.durum.emit(f"{k['kodu']} → {s['miktar']:g} {k['birim']}{uyari}")
        return True

    def _kart(self, kid: int) -> dict:
        if kid not in self._kart_cache:
            from barkod.sorgu import kart_ozetleri
            self._kart_cache.update(kart_ozetleri(self.p.conn, [kid]))
        return self._kart_cache[kid]

    def _secili_kid(self) -> int | None:
        r = self.tablo.currentRow()
        if r < 0:
            return None
        return int(self.tablo.item(r, 0).data(Qt.UserRole))

    def duzelt(self):
        kid = self._secili_kid()
        if kid is None:
            return
        s = self.oturum.satirlar[str(kid)]
        v, ok = QInputDialog.getDouble(self, 'Adet düzelt', f"{s['kodu']}\nYeni adet:", s['miktar'], 0, 1e9, 3)
        if ok:
            self.oturum.ekle(kid, s['kodu'], s['adi'], s['birim'], v, mutlak=True)
            self._yenile(vurgu=kid)

    def sil(self):
        kid = self._secili_kid()
        if kid is None:
            return
        s = self.oturum.satirlar[str(kid)]
        if QMessageBox.question(self, 'Sil', f"{s['kodu']} sayımdan silinsin mi?") == QMessageBox.Yes:
            self.oturum.sil(kid); self._yenile()

    def _yenile(self, vurgu: int | None = None):
        self.tablo.setRowCount(0)
        if not self.oturum:
            return
        satirlar = sorted(self.oturum.satirlar.values(), key=lambda s: s['son_okutma'], reverse=True)
        for s in satirlar:
            r = self.tablo.rowCount(); self.tablo.insertRow(r)
            it = _hucre(barkod_degeri(s['kart_id'])); it.setData(Qt.UserRole, s['kart_id'])
            self.tablo.setItem(r, 0, it)
            for c, v in enumerate((s['kodu'], s['adi'], s['birim']), 1):
                self.tablo.setItem(r, c, _hucre(v))
            self.tablo.setItem(r, 4, _hucre(s['miktar'], True))
            self.tablo.setItem(r, 5, _hucre(s['son_okutma']))
            if s['kart_id'] == vurgu:
                for c in range(len(self.SUTUN)):
                    self.tablo.item(r, c).setBackground(QColor('#fff59d'))
        self.ozet.setText(f'{self.oturum.depo_adi} · {len(satirlar)} kalem · '
                          f'{sum(s["miktar"] for s in satirlar):g} adet')


# ───────────────────────── ana pencere ─────────────────────────
class BarkodPencere(QMainWindow):
    MODLAR = [('Sorgula', True), ('Sayım', True), ('Giriş', False), ('Çıkış', False),
              ('Transfer', False), ('Reçeteye ekle', False)]

    def __init__(self):
        super().__init__()
        self.conn = None
        self.depo_adlari: dict = {}
        self._t = None
        self.setWindowTitle('CEO Barkod')
        self.resize(1180, 820)
        self.setStyleSheet(_STIL)

        merkez = QWidget(); lay = QVBoxLayout(merkez)
        lay.setContentsMargins(12, 10, 12, 10)

        ust = QHBoxLayout()
        self.grup = QButtonGroup(self); self.grup.setExclusive(True)
        for i, (ad, acik) in enumerate(self.MODLAR):
            b = QPushButton(ad); b.setCheckable(True); b.setEnabled(acik); b.setFocusPolicy(Qt.NoFocus)
            b.setMinimumHeight(40)
            if not acik:
                b.setToolTip('Sonraki aşamada açılacak')
            self.grup.addButton(b, i); ust.addWidget(b)
        self.grup.button(0).setChecked(True)
        self.grup.buttonClicked[int].connect(self._mod_degisti)
        ust.addStretch()
        self.bag = QLabel('Bağlanıyor…'); self.bag.setStyleSheet('color:#757575;')
        ust.addWidget(self.bag)
        lay.addLayout(ust)

        self.okut = QLineEdit()
        self.okut.setPlaceholderText('Barkodu okutun (ya da stok kodunu yazıp Enter)')
        self.okut.setStyleSheet(_OKUT_NORMAL)
        self.okut.returnPressed.connect(self._okutuldu)
        self.okut.setEnabled(False)
        lay.addWidget(self.okut)

        self.sayfalar = QStackedWidget()
        self.sorgula = SorgulaSayfasi()
        self.sayim = SayimSayfasi(self)
        self.sayim.durum.connect(self._durum)
        self.sayfalar.addWidget(self.sorgula)
        self.sayfalar.addWidget(self.sayim)
        lay.addWidget(self.sayfalar, 1)
        self.setCentralWidget(merkez)

        self.sb = QStatusBar(); self.setStatusBar(self.sb)
        self._baglan()

    # ── bağlantı ──
    def _baglan(self):
        self._tb = _BaglanThread()
        self._tb.bitti.connect(self._baglandi)
        self._tb.hata.connect(lambda e: self.bag.setText(f'<span style="color:#c62828">Bağlantı hatası: {e}</span>'))
        self._tb.start()

    def _baglandi(self, conn):
        from barkod.sorgu import depolar
        self.conn = conn
        self.depo_adlari = depolar(conn)
        self.sayim.depolari_doldur(self.depo_adlari)
        self.bag.setText('<span style="color:#2e7d32">● CEO bağlı</span>')
        self.okut.setEnabled(True); self.okut.setFocus()

    # ── mod ──
    def _mod_degisti(self, i: int):
        if i <= 1:
            self.sayfalar.setCurrentIndex(i)
        self.okut.setFocus()

    # ── okutma ──
    def _okutuldu(self):
        deger = self.okut.text().strip()
        self.okut.clear()
        if not deger or not self.conn:
            return
        mod = self.grup.checkedId()
        if mod == 0:
            if self._t and self._t.isRunning():
                self._durum('Önceki sorgu sürüyor…'); return
            self._durum(f'Sorgulanıyor: {deger}')
            self._t = _SorguThread(self.conn, deger)
            self._t.bitti.connect(self._sorgu_bitti)
            self._t.hata.connect(lambda e: (self._geri_bildirim(False), self._durum(e)))
            self._t.start()
        elif mod == 1:
            if self._t and self._t.isRunning():
                self._durum('Sorgu bitmeden sayım okutulamaz, tekrar okutun.')
                self._geri_bildirim(False); return
            self._geri_bildirim(self.sayim.okut(deger))
        self.okut.setFocus()

    def _sorgu_bitti(self, k, deger):
        if k is None:
            self.sorgula.bulunamadi(deger); self._geri_bildirim(False)
            self._durum(f'Tanınmayan barkod / kod: {deger}')
        else:
            self.sorgula.goster(k, self.depo_adlari); self._geri_bildirim(True)
            self._durum(f'{k.kodu} · toplam {k.toplam_bakiye:g} {k.birim}')
        self.okut.setFocus()

    def _geri_bildirim(self, iyi: bool):
        self.okut.setStyleSheet(_OKUT_IYI if iyi else _OKUT_KOTU)
        if not iyi:
            QApplication.beep()
        QTimer.singleShot(600, lambda: self.okut.setStyleSheet(_OKUT_NORMAL))

    def _durum(self, msg: str):
        self.sb.showMessage(msg)
