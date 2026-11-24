"""Giriş (20) / Çıkış (21) / Transfer (23) sayfası — CEO ERP'ye YAZAR.

Akış: okut → liste → "Kontrol et" (fiyat + depo yeterliliği + deneme yazımı, ROLLBACK)
      → "Kaydet" (özet onayı → yeniden kontrol → COMMIT). Liste/depo/tarih değişirse
      kontrol düşer, Kaydet yeniden kapanır.
"""
from __future__ import annotations

from datetime import date

from PyQt5.QtCore import QDate, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from barkod.fis import ISLEMLER, fis_yaz, taslak_hazirla
from barkod.kod import barkod_degeri, okutma_coz
from barkod.sorgu import TRANSFER

_YESIL = "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2e7d32,stop:1 #43a047);color:white;font-size:14px;"
_MAVI = "background:#3f51b5;color:white;font-size:14px;"


class HareketSayfasi(QWidget):
    durum = pyqtSignal(str)
    SUTUN = ['Barkod', 'Stok Kodu', 'Stok Adı', 'Birim', 'Miktar', 'Kaynak bakiye', 'Birim fiyat', 'Tutar', 'Durum']

    def __init__(self, pencere, islem: int):
        super().__init__()
        from barkod.ui.ana_pencere import _tablo
        self.p, self.islem = pencere, islem
        self.bilgi = ISLEMLER[islem]
        self.kalemler: dict[int, dict] = {}   # kart_id → {kodu, adi, birim, miktar, fiyat(elle|None)}
        self._sira: list[int] = []
        self._kontrol_ok = False
        self._taslak = None

        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        g = QGroupBox(self.bilgi['ad'] + f' — fiş türü {islem}')
        h = QHBoxLayout(g)
        h.addWidget(QLabel('Depo:' if islem != TRANSFER else 'Çıkan depo:'))
        self.depo = QComboBox(); self.depo.setMinimumWidth(230); h.addWidget(self.depo)
        self.karsi = QComboBox(); self.karsi.setMinimumWidth(230)
        if islem == TRANSFER:
            h.addWidget(QLabel('→ Giren depo:')); h.addWidget(self.karsi)
        h.addWidget(QLabel('Tarih:'))
        self.tarih = QDateEdit(QDate.currentDate()); self.tarih.setCalendarPopup(True)
        self.tarih.setDisplayFormat('dd.MM.yyyy'); self.tarih.setMaximumDate(QDate.currentDate())
        h.addWidget(self.tarih)
        h.addWidget(QLabel('Açıklama:'))
        self.notlar = QLineEdit(); self.notlar.setPlaceholderText('CEO fiş notu (zorunlu)')
        h.addWidget(self.notlar, 1)
        for w in (self.depo, self.karsi, self.tarih, self.notlar):
            w.setFocusPolicy(Qt.ClickFocus)
        self.depo.currentIndexChanged.connect(self._degisti)
        self.karsi.currentIndexChanged.connect(self._degisti)
        self.tarih.dateChanged.connect(self._degisti)
        lay.addWidget(g)

        h2 = QHBoxLayout()
        self.adet_sor = QCheckBox('Okutunca adet sor'); self.adet_sor.setFocusPolicy(Qt.NoFocus)
        h2.addWidget(self.adet_sor); h2.addStretch()
        self.b_adet = QPushButton('Adet düzelt'); self.b_adet.clicked.connect(self._adet)
        self.b_fiyat = QPushButton('Fiyat düzelt'); self.b_fiyat.clicked.connect(self._fiyat)
        self.b_fiyat.setVisible(self.bilgi['yon'] > 0)   # yalnız girişte elle fiyat
        self.b_sil = QPushButton('Satırı sil'); self.b_sil.clicked.connect(self._sil)
        self.b_temizle = QPushButton('Listeyi temizle'); self.b_temizle.clicked.connect(self._temizle)
        for b in (self.b_adet, self.b_fiyat, self.b_sil, self.b_temizle):
            b.setFocusPolicy(Qt.NoFocus); h2.addWidget(b)
        lay.addLayout(h2)

        self.tablo = _tablo(self.SUTUN); self.tablo.setColumnWidth(2, 380)
        lay.addWidget(self.tablo, 1)

        h3 = QHBoxLayout()
        self.ozet = QLabel(''); self.ozet.setStyleSheet('font-weight:bold;color:#3949ab;')
        h3.addWidget(self.ozet, 1)
        self.b_kontrol = QPushButton('Kontrol et'); self.b_kontrol.setStyleSheet(_MAVI)
        self.b_kontrol.clicked.connect(self.kontrol)
        self.b_kaydet = QPushButton("CEO'ya kaydet"); self.b_kaydet.setStyleSheet(_YESIL)
        self.b_kaydet.clicked.connect(self.kaydet)
        for b in (self.b_kontrol, self.b_kaydet):
            b.setFocusPolicy(Qt.NoFocus); b.setMinimumHeight(42); b.setMinimumWidth(170); h3.addWidget(b)
        lay.addLayout(h3)
        self._yenile()

    # ── kurulum ──
    def depolari_doldur(self, depolar: dict):
        for cb, vars_ in ((self.depo, 2), (self.karsi, None)):
            cb.blockSignals(True); cb.clear()
            if cb is self.karsi:
                cb.addItem('— seçin —', None)
            for i, ad in depolar.items():
                cb.addItem(ad, i)
            if vars_ is not None:
                cb.setCurrentIndex(max(0, cb.findData(vars_)))
            cb.blockSignals(False)

    # ── liste ──
    def okut(self, deger: str) -> bool:
        kid = okutma_coz(self.p.conn, deger)
        if not kid:
            self.durum.emit(f'Tanınmayan barkod / kod: {deger}'); return False
        k = self.p.kart_ozet(kid)
        if not k['aktif']:
            self.durum.emit(f"{k['kodu']} PASİF kart — fişe eklenmez"); return False
        miktar = 1.0
        if self.adet_sor.isChecked():
            miktar, ok = QInputDialog.getDouble(self, 'Adet', f"{k['kodu']}\n{k['adi']}\nAdet:", 1, 0.001, 1e9, 3)
            if not ok:
                return False
        if kid in self.kalemler:
            self.kalemler[kid]['miktar'] = round(self.kalemler[kid]['miktar'] + miktar, 6)
            self._sira.remove(kid)
        else:
            self.kalemler[kid] = {**k, 'miktar': miktar, 'fiyat': None}
        self._sira.insert(0, kid)
        self._degisti(vurgu=kid)
        self.durum.emit(f"{k['kodu']} → {self.kalemler[kid]['miktar']:g} {k['birim']}")
        return True

    def _secili(self) -> int | None:
        r = self.tablo.currentRow()
        return None if r < 0 else int(self.tablo.item(r, 0).data(Qt.UserRole))

    def _adet(self):
        kid = self._secili()
        if kid is None: return
        k = self.kalemler[kid]
        v, ok = QInputDialog.getDouble(self, 'Adet', f"{k['kodu']}\nYeni adet:", k['miktar'], 0.001, 1e9, 3)
        if ok:
            k['miktar'] = v; self._degisti(vurgu=kid)

    def _fiyat(self):
        kid = self._secili()
        if kid is None: return
        k = self.kalemler[kid]
        mevcut = k['fiyat'] if k['fiyat'] is not None else (self._oto_fiyat(kid) or 0)
        if not mevcut:
            from barkod.fis import son_giris_fiyati
            c = self.p.conn.cursor()
            try: mevcut = son_giris_fiyati(c, kid)
            finally: c.close()
        v, ok = QInputDialog.getDouble(self, 'Birim fiyat (TL)', f"{k['kodu']}\nBirim fiyat:", mevcut, 0, 1e9, 4)
        if ok:
            k['fiyat'] = v; self._degisti(vurgu=kid)

    def _oto_fiyat(self, kid):
        if self._taslak:
            for s in self._taslak.satirlar:
                if s.kart_id == kid:
                    return s.birim_fiyat
        return None

    def _sil(self):
        kid = self._secili()
        if kid is None: return
        self.kalemler.pop(kid, None); self._sira.remove(kid); self._degisti()

    def _temizle(self, sor=True):
        if sor and self.kalemler and QMessageBox.question(self, 'Temizle', 'Liste temizlensin mi?') != QMessageBox.Yes:
            return
        self.kalemler.clear(); self._sira.clear(); self._degisti()

    def _degisti(self, *_, vurgu=None):
        self._kontrol_ok = False
        self._taslak = None          # depo/tarih/liste değişti → eski kontrol sonucu geçersiz
        self._yenile(vurgu)

    # ── kontrol / kaydet ──
    def _hazirla(self):
        karsi = self.karsi.currentData() if self.islem == TRANSFER else None
        kal = [(kid, self.kalemler[kid]['miktar'], self.kalemler[kid]['fiyat']) for kid in reversed(self._sira)]
        return taslak_hazirla(self.p.conn, self.islem, self.depo.currentData(), karsi,
                              self.tarih.date().toPyDate(), kal, self.notlar.text().strip(), self.p.kullanici_guid())

    def _engeller(self, tz) -> list[str]:
        e = list(tz.engel)
        if not self.notlar.text().strip():
            e.append('Açıklama boş')
        if 'claude' in self.notlar.text().lower():
            e.append('Açıklamada "Claude" geçemez')
        return e

    def kontrol(self) -> bool:
        if not self.kalemler or self.p.mesgul():
            return False
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            tz = self._hazirla(); self._taslak = tz
            engel = self._engeller(tz)
            sonuc = None if engel else fis_yaz(self.p.conn, tz, commit=False)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, 'Kontrol', f'{type(e).__name__}: {e}'); return False
        QApplication.restoreOverrideCursor()
        if sonuc and sonuc['sorunlar']:
            engel = sonuc['sorunlar']
        self._kontrol_ok = not engel
        self._yenile()
        if engel:
            self.durum.emit('Kontrol: ' + ' | '.join(engel[:4]))
        else:
            self.durum.emit(f"Kontrol TAMAM — {len(tz.satirlar)} kalem, {tz.toplam:,.2f} ₺. Deneme yazımı geri alındı. Kaydedebilirsiniz.")
        return self._kontrol_ok

    def kaydet(self):
        if not self._kontrol_ok:
            return
        tz = self._taslak
        dep = self.depo.currentText() + (f'  →  {self.karsi.currentText()}' if self.islem == TRANSFER else '')
        metin = (f"<b>{self.bilgi['ad']}</b> (fiş türü {self.islem})<br>Depo: {dep}<br>"
                 f"Tarih: {self.tarih.date().toString('dd.MM.yyyy')}<br>Kullanıcı: {self.p.kullanici_adi()}<br>"
                 f"Açıklama: {self.notlar.text().strip()}<br><br>"
                 f"<b>{len(tz.satirlar)} kalem, {sum(s.miktar for s in tz.satirlar):g} adet, {tz.toplam:,.2f} ₺</b><br><br>"
                 "CEO'ya kalıcı olarak yazılsın mı?")
        if QMessageBox.question(self, "CEO'ya kaydet", metin) != QMessageBox.Yes:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            tz = self._hazirla()            # son durumla yeniden hesapla
            engel = self._engeller(tz)
            sonuc = None if engel else fis_yaz(self.p.conn, tz, commit=True)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, 'Kayıt', f'Yazılmadı (geri alındı).\n{type(e).__name__}: {e}'); return
        QApplication.restoreOverrideCursor()
        if engel or not sonuc['commit']:
            self._kontrol_ok = False; self._taslak = tz; self._yenile()
            QMessageBox.warning(self, 'Kayıt', 'Yazılmadı (geri alındı):\n' + '\n'.join(engel or sonuc['sorunlar']))
            return
        from barkod.ayar import fis_gunluge_yaz
        fis_gunluge_yaz({**sonuc, 'islem_kodu': self.islem, 'depo': self.depo.currentData(),
                         'karsi_depo': tz.karsi_depo_id, 'tarih': str(tz.tarih), 'kullanici': self.p.kullanici_adi(),
                         'notlar': tz.notlar, 'satirlar': [[s.kodu, s.miktar, s.birim_fiyat] for s in tz.satirlar]})
        QMessageBox.information(self, 'Kaydedildi',
                                f"Fiş yazıldı: {sonuc['belge']} (Id {sonuc['hareket_id']})\n"
                                f"{sonuc['satir']} kalem, {sonuc['toplam']:,.2f} ₺\n\n"
                                "CEO açıksa görmek için kapatıp açmanız gerekebilir.")
        self.durum.emit(f"Kaydedildi: {self.bilgi['ad']} {sonuc['belge']} (Id {sonuc['hareket_id']})")
        self.notlar.clear(); self._taslak = None
        self._temizle(sor=False)

    # ── görünüm ──
    def _yenile(self, vurgu=None):
        from barkod.ui.ana_pencere import _hucre
        satir_tz = {s.kart_id: s for s in (self._taslak.satirlar if self._taslak else [])}
        self.tablo.setRowCount(0)
        for kid in self._sira:
            k = self.kalemler[kid]
            s = satir_tz.get(kid)
            r = self.tablo.rowCount(); self.tablo.insertRow(r)
            it = _hucre(barkod_degeri(kid)); it.setData(Qt.UserRole, kid); self.tablo.setItem(r, 0, it)
            for c, v in enumerate((k['kodu'], k['adi'], k['birim']), 1):
                self.tablo.setItem(r, c, _hucre(v))
            self.tablo.setItem(r, 4, _hucre(k['miktar'], True))
            guncel = s is not None and abs(s.miktar - k['miktar']) < 1e-9
            if guncel and s.kaynak_bakiye is not None:
                self.tablo.setItem(r, 5, _hucre(s.kaynak_bakiye, True))
            fiyat = k['fiyat'] if k['fiyat'] is not None else (s.birim_fiyat if guncel else None)
            if fiyat is not None:
                self.tablo.setItem(r, 6, _hucre(fiyat, True))
                self.tablo.setItem(r, 7, _hucre(round(fiyat * k['miktar'], 2), True))
            durum, renk = 'kontrol edilmedi', None
            if guncel:
                if s.hata: durum, renk = s.hata, '#ffcdd2'
                elif s.uyari: durum, renk = s.uyari, '#fff9c4'
                else: durum, renk = ('tamam' + (' (elle fiyat)' if k['fiyat'] is not None else '')), '#c8e6c9'
            self.tablo.setItem(r, 8, _hucre(durum))
            for c in range(len(self.SUTUN)):
                if kid == vurgu:
                    self.tablo.item(r, c) and self.tablo.item(r, c).setBackground(QColor('#fff59d'))
                elif renk and self.tablo.item(r, c):
                    self.tablo.item(r, c).setBackground(QColor(renk))
        adet = sum(k['miktar'] for k in self.kalemler.values())
        self.ozet.setText(f'{len(self.kalemler)} kalem · {adet:g} adet' +
                          (' · KONTROL TAMAM' if self._kontrol_ok else ''))
        self.b_kaydet.setEnabled(self._kontrol_ok)
        self.b_kontrol.setEnabled(bool(self.kalemler))
        for b in (self.b_adet, self.b_fiyat, self.b_sil, self.b_temizle):
            b.setEnabled(bool(self.kalemler))
