"""CEO Barkod — ayrı program ana penceresi.

Okuyucu klavye kaması (HID) modunda çalışır: barkodu okutma kutusuna yazar
ve Enter gönderir. Cihaz yokken kutuya S468311 + Enter yazmak aynı işi görür.

Modlar: Sorgula, Sayım, Etiket (ERP'ye yazmaz) · Giriş 20 / Çıkış 21 / Transfer 23 / Reçeteye ekle
(CEO'ya YAZAR; önce "Kontrol et" deneme yazımı ve ROLLBACK, sonra onaylı "CEO'ya kaydet").
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog,
    QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QStackedWidget, QStatusBar, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from barkod.kod import barkod_degeri, coz, coz_mesaj

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
    # (kart|None, deger, durum)  — durum: 'ok'|'yok'|'mukerrer'
    bitti = pyqtSignal(object, str, str)
    hata = pyqtSignal(str)

    def __init__(self, deger: str):
        super().__init__()
        self._deger = deger

    def run(self):
        # Ana iş parçacığının paylaşımlı bağlantısını kullanmaz; kendi kısa
        # ömürlü bağlantısını açar (eşzamanlı kullanım/çakışma olmaz).
        try:
            from config import DB_DEFAULTS
            from db.baglanti import baglanti_ctx
            from barkod.kod import coz
            from barkod.sorgu import kart_bilgi
            with baglanti_ctx(**DB_DEFAULTS) as conn:
                kid, durum = coz(conn, self._deger)
                k = kart_bilgi(conn, kid) if kid else None
            self.bitti.emit(k, self._deger, durum)
        except Exception as e:
            self.hata.emit(f'{type(e).__name__}: {e}')


# ───────────────────────── Sorgula sayfası ─────────────────────────
class SorgulaSayfasi(QWidget):
    def __init__(self, pencere: 'BarkodPencere'):
        super().__init__()
        self.p = pencere
        self._son_kart = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        ust_bar = QHBoxLayout()
        self.baslik = QLabel('Bir barkod okutun.')
        self.baslik.setWordWrap(True)
        self.baslik.setTextFormat(Qt.RichText)
        self.baslik.setStyleSheet('background:white;border:1px solid #c5cae9;border-radius:8px;padding:10px;font-size:15px;')
        ust_bar.addWidget(self.baslik, 1)
        self.b_etiket = QPushButton('Etiket Bas…')
        self.b_etiket.setFocusPolicy(Qt.NoFocus)
        self.b_etiket.setMinimumHeight(52)
        self.b_etiket.setMinimumWidth(140)
        self.b_etiket.setEnabled(False)
        self.b_etiket.clicked.connect(self._etiket_bas)
        ust_bar.addWidget(self.b_etiket)
        lay.addLayout(ust_bar)

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
        self._son_kart = k
        self.b_etiket.setEnabled(True)
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

    def bulunamadi(self, mesaj: str):
        self._son_kart = None
        self.b_etiket.setEnabled(False)
        self.baslik.setText(f'<b style="color:#c62828;font-size:18px">{mesaj}</b>')
        for t in (self.t_depo, self.t_recete, self.t_hareket):
            t.setRowCount(0)

    def _etiket_bas(self):
        if not self._son_kart:
            return
        from barkod.etiket import Kart
        from barkod.ui.etiket import EtiketTekliDialog
        k = self._son_kart
        EtiketTekliDialog(
            self.p, Kart(k.id, k.kodu, k.adi, k.birim, k.toplam_bakiye, k.aktif)
        ).exec_()


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
        self.b_yeni = QPushButton('Yeni sayım'); self.b_yeni.clicked.connect(self.yeni)
        self.b_devam = QPushButton('Sayım aç'); self.b_devam.clicked.connect(self.devam)
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
        self.b_etiket = QPushButton('Seçiliye etiket'); self.b_etiket.clicked.connect(self.etiket_bas)
        self.b_duzelt = QPushButton('Seçili adedi düzelt'); self.b_duzelt.clicked.connect(self.duzelt)
        self.b_sil = QPushButton('Seçili satırı sil'); self.b_sil.clicked.connect(self.sil)
        for b in (self.b_etiket, self.b_duzelt, self.b_sil):
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
        self.b_yeni.setEnabled(not var)
        self.b_devam.setEnabled(not var)
        for b in (self.b_excel, self.b_bitir, self.b_etiket, self.b_duzelt, self.b_sil):
            b.setEnabled(var)

    # ── oturum ──
    def yeni(self):
        from barkod.sayim import SayimOturumu
        if not self.p.conn:
            QMessageBox.information(self, 'Sayım', 'Bağlantı henüz kurulmadı, birkaç saniye bekleyin.')
            return
        sayan = self.p.kullanici_adi()          # sayan = sağ üstte seçili CEO kullanıcısı
        if not sayan:
            QMessageBox.information(self, 'Sayım', 'Önce sağ üstten Kullanıcı seçin.')
            return
        self.oturum = SayimOturumu.yeni(self.depo.currentData(), self.depo.currentText(), sayan)
        self._yenile(); self._butonlar()
        self.durum.emit(f'Sayım başladı: {self.oturum.depo_adi} · sayan {sayan}. Okutmaya başlayın.')

    def devam(self):
        from barkod.sayim import SayimOturumu, oturumlar
        liste = oturumlar()
        if not liste:
            QMessageBox.information(self, 'Sayım', 'Kayıtlı sayım yok.'); return
        adlar = [f"{'[BİTTİ] ' if o['bitti'] else ''}{o['baslangic']} · {o['depo_adi']} · "
                 f"{o['kalem']} kalem · {o['sayan']}" for o in liste]
        sec, ok = QInputDialog.getItem(self, 'Sayım aç', 'Oturum (bitmiş olanlar yeniden açılır):', adlar, 0, False)
        if not ok:
            return
        self.oturum = SayimOturumu.yukle(liste[adlar.index(sec)]['yol'])
        if self.oturum.bitis:                 # biten oturumu açmak = yeniden devam
            self.oturum.bitis = ''
            self.oturum.kaydet()
        self._yenile(); self._butonlar()
        self.durum.emit(f'Sayım açıldı: {self.oturum.depo_adi} · {len(self.oturum.satirlar)} kalem.')

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
        kid, durum = coz(self.p.conn, deger)
        if not kid:
            self.durum.emit(coz_mesaj(durum, deger))
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

    def etiket_bas(self):
        kid = self._secili_kid()
        if kid is None or not self.oturum:
            return
        from barkod.etiket import Kart
        from barkod.ui.etiket import EtiketTekliDialog
        s = self.oturum.satirlar[str(kid)]
        EtiketTekliDialog(self.p, Kart(kid, s['kodu'], s['adi'], s['birim'], s['miktar'], True)).exec_()
        self.p.okut.setFocus()

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


# ───────────────────────── hakkında ─────────────────────────
class HakkindaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from barkod import FIRMA, GELISTIRICI, SURUM, logo_yolu
        self.setWindowTitle('Hakkında — CEO Barkod')
        self.setFixedWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(10)
        if logo_yolu():
            from PyQt5.QtGui import QPixmap
            lg = QLabel(); lg.setAlignment(Qt.AlignCenter)
            lg.setPixmap(QPixmap(str(logo_yolu())).scaledToWidth(260, Qt.SmoothTransformation))
            lg.setStyleSheet('background:white;border:1px solid #c5cae9;border-radius:8px;padding:10px;')
            lay.addWidget(lg)
        baslik = QLabel('CEO Barkod')
        baslik.setStyleSheet('font-size:22px;font-weight:bold;color:#1a237e;')
        lay.addWidget(baslik)
        surum = QLabel(f'Sürüm {SURUM}')
        surum.setStyleSheet('color:#9e9e9e;font-size:11px;')
        lay.addWidget(surum)
        metin = QLabel(
            'Depo sorgulama, sayım, giriş / çıkış / transfer fişleri, etiket basımı ve '
            'reçeteye parça ekleme işlemlerini barkodla yapmak için geliştirilmiştir.<br><br>'
            f'<b>Firma:</b> {FIRMA}<br>'
            f'<b>Geliştirici:</b> {GELISTIRICI}<br><br>'
            f'© 2026 {FIRMA} Tüm hakları saklıdır.')
        metin.setTextFormat(Qt.RichText); metin.setWordWrap(True)
        metin.setStyleSheet('color:#37474f;font-size:12px;')
        lay.addWidget(metin)
        kapat = QPushButton('Kapat'); kapat.clicked.connect(self.accept)
        lay.addWidget(kapat, 0, Qt.AlignRight)


# ───────────────────────── yetki yönetimi ─────────────────────────
class YetkiDialog(QDialog):
    def __init__(self, parent, kullanicilar: list[tuple[str, str]]):
        super().__init__(parent)
        from barkod import yetki
        self._y = yetki
        self.setWindowTitle('Kullanıcı yetkileri')
        self.resize(760, 520)
        self._veri, hata = yetki.oku()
        self._kul = kullanicilar
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel('Giriş / Çıkış / Transfer / Reçete yetkisi verilen kullanıcıdan şifre istenir. '
                             'Sorgula, Sayım ve Etiket herkese açıktır.'))
        self.sutun = ['Kullanıcı'] + [ad for _, ad in yetki.EK_YETKILER] + ['Yönetici', 'Şifre']
        self.tablo = QTableWidget(len(kullanicilar), len(self.sutun))
        self.tablo.setHorizontalHeaderLabels(self.sutun)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._yeni_sifre: dict[str, str] = {}      # guid → yeni özet
        n = len(yetki.EK_YETKILER)
        for r, (g, ad) in enumerate(kullanicilar):
            k = yetki.kayit(self._veri, g) or {}
            it = QTableWidgetItem(ad); it.setData(Qt.UserRole, g); self.tablo.setItem(r, 0, it)
            for c, (anahtar, _) in enumerate(yetki.EK_YETKILER, 1):
                self.tablo.setItem(r, c, self._kutu(anahtar in (k.get('yetki') or [])))
            self.tablo.setItem(r, n + 1, self._kutu(bool(k.get('yonetici'))))
            self.tablo.setItem(r, n + 2, QTableWidgetItem('var' if k.get('sifre') else '—'))
        lay.addWidget(self.tablo, 1)
        alt = QHBoxLayout()
        b_sifre = QPushButton('Seçiliye şifre belirle'); b_sifre.clicked.connect(self._sifre_belirle)
        b_kaydet = QPushButton('Kaydet'); b_kaydet.clicked.connect(self._kaydet)
        b_iptal = QPushButton('Kapat'); b_iptal.clicked.connect(self.reject)
        alt.addWidget(b_sifre); alt.addStretch(); alt.addWidget(b_kaydet); alt.addWidget(b_iptal)
        lay.addLayout(alt)
        if hata:
            lay.addWidget(QLabel(hata))

    @staticmethod
    def _kutu(isaretli: bool) -> QTableWidgetItem:
        it = QTableWidgetItem()
        it.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        it.setCheckState(Qt.Checked if isaretli else Qt.Unchecked)
        return it

    def _sifre_belirle(self):
        r = self.tablo.currentRow()
        if r < 0:
            QMessageBox.information(self, 'Şifre', 'Önce bir kullanıcı satırı seçin.'); return
        g = self.tablo.item(r, 0).data(Qt.UserRole)
        s1, ok = QInputDialog.getText(self, 'Şifre', f'{self.tablo.item(r, 0).text()} için yeni şifre:',
                                      QLineEdit.Password)
        if not ok or not s1:
            return
        s2, ok = QInputDialog.getText(self, 'Şifre', 'Şifreyi tekrar girin:', QLineEdit.Password)
        if not ok or s1 != s2:
            QMessageBox.warning(self, 'Şifre', 'Şifreler uyuşmadı; değişmedi.'); return
        self._yeni_sifre[g] = self._y.sifre_ozeti(s1)
        self.tablo.item(r, len(self.sutun) - 1).setText('yeni (kaydedilince geçerli)')

    def _kaydet(self):
        y = self._y
        veri, _ = y.oku()                      # başkası araya yazdıysa üstüne binmesin
        kayitlar = veri.setdefault('kullanicilar', {})
        n = len(y.EK_YETKILER)
        for r, (g, ad) in enumerate(self._kul):
            secilen = [a for c, (a, _) in enumerate(y.EK_YETKILER, 1)
                       if self.tablo.item(r, c).checkState() == Qt.Checked]
            yon = self.tablo.item(r, n + 1).checkState() == Qt.Checked
            eski = dict(y.kayit(veri, g) or {})
            ozet = self._yeni_sifre.get(g) or eski.get('sifre')
            if (secilen or yon) and not ozet:
                QMessageBox.warning(self, 'Yetki', f'{ad}: yetki verilen kullanıcıya şifre belirleyin.')
                return
            kayitlar.pop(g, None); kayitlar.pop(g.upper(), None)
            if secilen or yon:
                kayitlar[g.upper()] = {'ad': ad, 'yetki': secilen, 'yonetici': yon, 'sifre': ozet}
        if not any(v.get('yonetici') for v in kayitlar.values()):
            QMessageBox.warning(self, 'Yetki', 'En az bir yönetici kalmalı; kaydedilmedi.')
            return
        try:
            y.yaz(veri)
        except Exception as e:
            QMessageBox.critical(self, 'Yetki', f'Yazılamadı:\n{type(e).__name__}: {e}')
            return
        QMessageBox.information(self, 'Yetki', 'Kaydedildi.')
        self.accept()


# ───────────────────────── ana pencere ─────────────────────────
class BarkodPencere(QMainWindow):
    MODLAR = [('Sorgula', True), ('Sayım', True), ('Giriş', True), ('Çıkış', True),
              ('Transfer', True), ('Etiket', True), ('Reçeteye ekle', True)]
    FIS_MODLARI = {2: 20, 3: 21, 4: 23}   # mod düğmesi → fiş türü
    ETIKET_MODU = 5
    RECETE_MODU = 6

    def __init__(self):
        super().__init__()
        self.conn = None
        self.depo_adlari: dict = {}
        self._t = None
        self._kart_cache: dict[int, dict] = {}
        self._yetki_veri: dict = {'kullanicilar': {}}
        self._aktif_yetki: set[str] = set()
        self._yonetici = False
        self._onceki_kullanici = 0
        self.setWindowTitle('CEO Barkod')
        self.resize(1180, 820)
        self.setStyleSheet(_STIL)

        merkez = QWidget(); lay = QVBoxLayout(merkez)
        lay.setContentsMargins(12, 10, 12, 10)

        ust = QHBoxLayout()
        from barkod import FIRMA, logo_yolu
        self.setWindowTitle(f'CEO Barkod — {FIRMA}')
        if logo_yolu():
            from PyQt5.QtGui import QIcon, QPixmap
            self.setWindowIcon(QIcon(str(logo_yolu())))
            px = QPixmap(str(logo_yolu())).scaledToHeight(34, Qt.SmoothTransformation)
            lg = QLabel(); lg.setPixmap(px); lg.setToolTip(FIRMA)
            lg.setStyleSheet('background:white;border:1px solid #c5cae9;border-radius:6px;padding:3px 8px;')
            ust.addWidget(lg)
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
        ust.addWidget(QLabel('Kullanıcı:'))
        self.kullanici = QComboBox(); self.kullanici.setMinimumWidth(190); self.kullanici.setFocusPolicy(Qt.ClickFocus)
        self.kullanici.currentIndexChanged.connect(self._kullanici_secildi)
        ust.addWidget(self.kullanici)
        self.b_yetki = QPushButton('Yetkiler…'); self.b_yetki.setFocusPolicy(Qt.NoFocus)
        self.b_yetki.clicked.connect(self._yetki_duzenle); self.b_yetki.setVisible(False)
        ust.addWidget(self.b_yetki)
        self.bag = QLabel('Bağlanıyor…'); self.bag.setStyleSheet('color:#757575;')
        ust.addWidget(self.bag)
        b_hak = QPushButton('Hakkında'); b_hak.setFocusPolicy(Qt.NoFocus)
        b_hak.clicked.connect(lambda: HakkindaDialog(self).exec_())
        ust.addWidget(b_hak)
        lay.addLayout(ust)

        self.okut = QLineEdit()
        self.okut.setPlaceholderText('Barkodu okutun (ya da stok kodunu yazıp Enter)')
        self.okut.setStyleSheet(_OKUT_NORMAL)
        self.okut.returnPressed.connect(self._okutuldu)
        # Okuyucu sonuna Enter göndermiyorsa: S###### biçimi yazıldıktan 150 ms sonra otomatik gönder
        self._oto_enter = QTimer(self)
        self._oto_enter.setSingleShot(True)
        self._oto_enter.setInterval(150)
        self._oto_enter.timeout.connect(self._oto_enter_tetikle)
        self.okut.textChanged.connect(lambda _t: self._oto_enter.start())
        self.okut.setEnabled(False)
        lay.addWidget(self.okut)

        self.sayfalar = QStackedWidget()
        self.sorgula = SorgulaSayfasi(self)
        self.sayim = SayimSayfasi(self)
        self.sayim.durum.connect(self._durum)
        self.sayfalar.addWidget(self.sorgula)
        self.sayfalar.addWidget(self.sayim)
        from barkod.ui.hareket import HareketSayfasi
        self.hareket = {}
        for mod, islem in self.FIS_MODLARI.items():
            sy = HareketSayfasi(self, islem); sy.durum.connect(self._durum)
            self.hareket[mod] = sy; self.sayfalar.addWidget(sy)   # sayfa indeksi = mod
        from barkod.ui.etiket import EtiketSayfasi
        self.etiket = EtiketSayfasi(self)
        self.etiket.durum.connect(self._durum)
        self.sayfalar.addWidget(self.etiket)                      # sayfa indeksi = 5 (ETIKET_MODU)
        from barkod.ui.recete import ReceteSayfasi
        self.recete = ReceteSayfasi(self)
        self.recete.durum.connect(self._durum)
        self.sayfalar.addWidget(self.recete)                      # sayfa indeksi = 6 (RECETE_MODU)
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
        for sy in self.hareket.values():
            sy.depolari_doldur(self.depo_adlari)
        self.etiket.depolari_doldur(self.depo_adlari)
        self.recete.mamulleri_yukle()
        from barkod.ayar import ayar_oku, kullanicilar
        from barkod import yetki
        secili = ayar_oku().get('kullanici_guid')
        self.kullanici.blockSignals(True)
        self.kullanici.addItem('— seçin —', None)
        for g, ad in kullanicilar(conn):
            self.kullanici.addItem(ad, g)
        self._yetki_veri, yetki_hata = yetki.oku()
        # Yetkili/yönetici kullanıcı açılışta otomatik seçilmez (şifre her seferinde sorulur)
        if secili and not yetki.yukseltilmis_mi(yetki.kayit(self._yetki_veri, secili)):
            self.kullanici.setCurrentIndex(max(0, self.kullanici.findData(secili)))
        self.kullanici.blockSignals(False)
        self._onceki_kullanici = self.kullanici.currentIndex()
        self._yetkileri_uygula(set(yetki.VARSAYILAN), False)
        if yetki_hata:
            self._durum(yetki_hata)
        self.bag.setText('<span style="color:#2e7d32">● CEO bağlı</span>')
        self.okut.setEnabled(True); self.okut.setFocus()

    # ── ortak ──
    def _kullanici_secildi(self, idx):
        from barkod import yetki
        from barkod.ayar import ayar_yaz
        guid = self.kullanici.currentData()
        self._yetki_veri, yetki_hata = yetki.oku()      # her seçimde taze oku
        k = yetki.kayit(self._yetki_veri, guid)
        dogrulandi = False
        if guid and yetki.sifre_gerekli(k):
            sifre, tamam = QInputDialog.getText(self, 'Yetkili kullanıcı',
                                                f'{self.kullanici.currentText()} için şifre:',
                                                QLineEdit.Password)
            if not tamam or not k.get('sifre') or not yetki.sifre_dogru(sifre, k['sifre']):
                if tamam:
                    QMessageBox.warning(self, 'Yetkili kullanıcı', 'Şifre yanlış.')
                self.kullanici.blockSignals(True)
                self.kullanici.setCurrentIndex(self._onceki_kullanici)
                self.kullanici.blockSignals(False)
                self._durum('Şifre doğrulanmadı; kullanıcı değişmedi.')
                return
            dogrulandi = True
        self._onceki_kullanici = idx
        self._yetkileri_uygula(yetki.yetkiler(k, dogrulandi), yetki.yonetici_mi(k, dogrulandi))
        if yetki_hata:
            self._durum(yetki_hata)
        # yetkili kullanıcı sonraki açılışta otomatik seçilmesin
        ayar_yaz(kullanici_guid=None if yetki.yukseltilmis_mi(k) else guid)

    def _yetkileri_uygula(self, yetkiler: set, yonetici: bool):
        from barkod.yetki import MOD_ANAHTAR
        self._aktif_yetki = set(yetkiler)
        self._yonetici = yonetici
        self.b_yetki.setVisible(yonetici)
        for i, anahtar in MOD_ANAHTAR.items():
            b = self.grup.button(i)
            izin = anahtar in self._aktif_yetki
            b.setEnabled(izin)
            b.setToolTip('' if izin else 'Bu sekme için yetkiniz yok')
        if MOD_ANAHTAR[self.grup.checkedId()] not in self._aktif_yetki:
            self.grup.button(0).setChecked(True)
            self._mod_degisti(0)

    def _yetki_duzenle(self):
        if not self._yonetici:
            return
        kul = [(self.kullanici.itemData(i), self.kullanici.itemText(i))
               for i in range(self.kullanici.count()) if self.kullanici.itemData(i)]
        YetkiDialog(self, kul).exec_()

    def kullanici_guid(self):
        return self.kullanici.currentData()

    def kullanici_adi(self) -> str:
        return self.kullanici.currentText() if self.kullanici.currentData() else ''

    def mesgul(self) -> bool:
        return bool(self._t and self._t.isRunning())

    def kart_ozet(self, kid: int) -> dict:
        if kid not in self._kart_cache:
            from barkod.sorgu import kart_ozetleri
            self._kart_cache.update(kart_ozetleri(self.conn, [kid]))
        return self._kart_cache[kid]

    # ── mod ──
    def _mod_degisti(self, i: int):
        if i < self.sayfalar.count():
            self.sayfalar.setCurrentIndex(i)
        if (i in self.FIS_MODLARI or i == self.RECETE_MODU) and not self.kullanici_guid():
            self._durum('Kayıt yapmak için sağ üstten Kullanıcı seçin.')
        self.okut.setFocus()

    # ── okutma ──
    def _oto_enter_tetikle(self):
        from barkod.kod import barkod_coz
        d = self.okut.text().strip()
        if len(d) >= 7 and barkod_coz(d) is not None:
            self._okutuldu()

    def _okutuldu(self):
        deger = self.okut.text().strip()
        self.okut.clear()
        if not deger or not self.conn:
            return
        mod = self.grup.checkedId()
        from barkod.yetki import MOD_ANAHTAR
        if MOD_ANAHTAR.get(mod) not in self._aktif_yetki:
            self._durum('Bu sekme için yetkiniz yok.'); return
        if mod == 0:
            if self._t and self._t.isRunning():
                self._durum('Önceki sorgu sürüyor…'); return
            self._durum(f'Sorgulanıyor: {deger}')
            self._t = _SorguThread(deger)
            self._t.bitti.connect(self._sorgu_bitti)
            self._t.hata.connect(lambda e: (self._geri_bildirim(False), self._durum(e)))
            self._t.start()
        elif mod == 1:
            if self._t and self._t.isRunning():
                self._durum('Sorgu bitmeden sayım okutulamaz, tekrar okutun.')
                self._geri_bildirim(False); return
            self._geri_bildirim(self.sayim.okut(deger))
        elif mod in self.hareket:
            if self.mesgul():
                self._durum('Sorgu bitmeden okutulamaz, tekrar okutun.')
                self._geri_bildirim(False); return
            self._geri_bildirim(self.hareket[mod].okut(deger))
        elif mod == self.ETIKET_MODU:
            if self.mesgul():
                self._durum('Sorgu bitmeden okutulamaz, tekrar okutun.')
                self._geri_bildirim(False); return
            self._geri_bildirim(self.etiket.okut(deger))
        elif mod == self.RECETE_MODU:
            if self.mesgul():
                self._durum('Sorgu bitmeden okutulamaz, tekrar okutun.')
                self._geri_bildirim(False); return
            self._geri_bildirim(self.recete.okut(deger))
        self.okut.setFocus()

    def _sorgu_bitti(self, k, deger, durum):
        if k is None:
            from barkod.kod import coz_mesaj
            msg = coz_mesaj(durum, deger)
            self.sorgula.bulunamadi(msg); self._geri_bildirim(False)
            self._durum(msg)
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
