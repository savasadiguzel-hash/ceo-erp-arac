"""CEO Barkod — Faz 3: Reçeteye ekle sayfası (`UretimReceteHatPlaniGirdi`).

Akış:
  1. Üstten aktif Mamül Reçetesi ve Hat Planı (Grup) seçilir (tek gruplu reçetede grup otomatik seçilir).
  2. Sağ panelde seçili grubun mevcut reçete girdileri canlı gösterilir.
  3. Barkod okutuldukça (veya stok kodu yazılıp Enter'a basıldıkça) sol listeye parça eklenir;
     aynı parça tekrar okutulursa eklenecek miktar artar. Parça reçetede zaten varsa mevcut miktarı
     ve yeni toplam miktarı tabloda yan yana gösterilir.
  4. "Kontrol et" → gerçek transaction içinde deneme yazımı yapar ve ROLLBACK ile geri alır.
  5. "CEO'ya kaydet" → özet onayı alır, işlem öncesi JSON yedeğini (`recete_barkod_yedek_*.json`)
     ve denetim günlüğünü (`barkod_fis_gunlugu.jsonl`) yazıp COMMIT eder.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from barkod.kod import barkod_degeri, coz, coz_mesaj
from barkod.recete import (
    aktif_mamuller, hat_girdileri_getir, hat_planlari_getir,
    recete_taslak_hazirla, recete_yaz,
)

_YESIL = "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2e7d32,stop:1 #43a047);color:white;font-size:14px;"
_MAVI = "background:#3f51b5;color:white;font-size:14px;"


class ReceteSayfasi(QWidget):
    durum = pyqtSignal(str)
    SUTUN = [
        'Barkod', 'Stok Kodu', 'Stok Adı', 'Birim',
        'Mevcut Reçetede', 'Eklenecek (+)', 'Yeni Miktar', 'Durum',
    ]
    MEVCUT_SUTUN = ['Tür', 'Kod', 'Adı', 'Miktar', 'Birim']

    def __init__(self, pencere):
        super().__init__()
        from barkod.ui.ana_pencere import _tablo

        self.p = pencere
        self._tum_mamuller: list[dict] = []
        self._mevcut_girdiler: list[dict] = []
        self._mevcut_stok_map: dict[int, float] = {}   # kart_id → seçili hattaki mevcut miktar
        self.kalemler: dict[int, dict] = {}            # kart_id → {kodu, adi, birim, miktar}
        self._sira: list[int] = []
        self._kontrol_ok = False
        self._taslak = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        # ── Üst: Mamül ve Hat Planı Seçimi ──
        g_hedef = QGroupBox('Hedef Mamül Reçetesi ve Hat Planı (Grup)')
        hh = QHBoxLayout(g_hedef)

        hh.addWidget(QLabel('Mamül ara:'))
        self.mamul_ara = QLineEdit()
        self.mamul_ara.setPlaceholderText('Kod veya ad ile filtrele…')
        self.mamul_ara.setClearButtonEnabled(True)
        self.mamul_ara.setMaximumWidth(210)
        self.mamul_ara.setFocusPolicy(Qt.ClickFocus)
        self.mamul_ara.textChanged.connect(self._mamul_filtrele)
        hh.addWidget(self.mamul_ara)

        hh.addWidget(QLabel('Mamül:'))
        self.mamul = QComboBox()
        self.mamul.setMinimumWidth(320)
        self.mamul.setFocusPolicy(Qt.ClickFocus)
        self.mamul.currentIndexChanged.connect(self._mamul_secildi)
        hh.addWidget(self.mamul, 1)

        hh.addWidget(QLabel('Reçete grubu (hat):'))
        self.hat = QComboBox()
        self.hat.setMinimumWidth(260)
        self.hat.setFocusPolicy(Qt.ClickFocus)
        self.hat.currentIndexChanged.connect(self._hat_secildi)
        hh.addWidget(self.hat, 1)

        self.b_yenile = QPushButton('Yenile')
        self.b_yenile.setFocusPolicy(Qt.NoFocus)
        self.b_yenile.clicked.connect(self.mamulleri_yukle)
        hh.addWidget(self.b_yenile)
        lay.addWidget(g_hedef)

        # ── Orta Alan: Sol Okutulanlar + Sağ Mevcut Reçete Girdileri ──
        sp = QSplitter(Qt.Horizontal)

        # Sol panel: Okutulan / eklenecek parçalar
        sol = QGroupBox('Okutulan / Reçeteye Eklenecek Parçalar')
        v_sol = QVBoxLayout(sol)

        h_arac = QHBoxLayout()
        self.adet_sor = QCheckBox('Okutunca miktar sor')
        self.adet_sor.setFocusPolicy(Qt.NoFocus)
        h_arac.addWidget(self.adet_sor)
        h_arac.addStretch()

        self.b_adet = QPushButton('Miktar düzelt')
        self.b_adet.clicked.connect(self._miktar_duzelt)
        self.b_sil = QPushButton('Satırı sil')
        self.b_sil.clicked.connect(self._sil)
        self.b_temizle = QPushButton('Listeyi temizle')
        self.b_temizle.clicked.connect(self._temizle)
        for b in (self.b_adet, self.b_sil, self.b_temizle):
            b.setFocusPolicy(Qt.NoFocus)
            h_arac.addWidget(b)
        v_sol.addLayout(h_arac)

        self.tablo = _tablo(self.SUTUN)
        self.tablo.setColumnWidth(2, 260)
        self.tablo.cellDoubleClicked.connect(lambda *_: self._miktar_duzelt())
        v_sol.addWidget(self.tablo, 1)
        sp.addWidget(sol)

        # Sağ panel: Seçili hat planının mevcut girdileri
        sag = QGroupBox('Seçili Grubun Mevcut Reçete Girdileri')
        v_sag = QVBoxLayout(sag)
        h_m_ara = QHBoxLayout()
        self.mevcut_ara = QLineEdit()
        self.mevcut_ara.setPlaceholderText('Mevcut girdilerde ara…')
        self.mevcut_ara.setClearButtonEnabled(True)
        self.mevcut_ara.setFocusPolicy(Qt.ClickFocus)
        self.mevcut_ara.textChanged.connect(self._mevcut_filtrele)
        h_m_ara.addWidget(self.mevcut_ara, 1)
        self.lbl_mevcut_sayac = QLabel('0 girdi')
        self.lbl_mevcut_sayac.setStyleSheet('color:#555;font-weight:bold;')
        h_m_ara.addWidget(self.lbl_mevcut_sayac)
        v_sag.addLayout(h_m_ara)

        self.t_mevcut = _tablo(self.MEVCUT_SUTUN)
        self.t_mevcut.setColumnWidth(2, 210)
        v_sag.addWidget(self.t_mevcut, 1)
        sp.addWidget(sag)
        sp.setSizes([740, 420])
        lay.addWidget(sp, 1)

        # ── Alt Çubuk: Özet + Kontrol Et + CEO'ya Kaydet ──
        alt = QHBoxLayout()
        self.ozet = QLabel('')
        self.ozet.setStyleSheet('font-weight:bold;color:#3949ab;')
        alt.addWidget(self.ozet, 1)

        self.b_kontrol = QPushButton('Kontrol et')
        self.b_kontrol.setStyleSheet(_MAVI)
        self.b_kontrol.clicked.connect(self.kontrol)

        self.b_kaydet = QPushButton("CEO'ya kaydet")
        self.b_kaydet.setStyleSheet(_YESIL)
        self.b_kaydet.clicked.connect(self.kaydet)

        for b in (self.b_kontrol, self.b_kaydet):
            b.setFocusPolicy(Qt.NoFocus)
            b.setMinimumHeight(42)
            b.setMinimumWidth(170)
            alt.addWidget(b)
        lay.addLayout(alt)

        self._yenile()

    # ── mamül ve hat planı yükleme ──
    def mamulleri_yukle(self):
        if not self.p.conn:
            return
        secili_kod = self.mamul.currentData()
        self._tum_mamuller = aktif_mamuller(self.p.conn)
        self._mamul_kutusunu_doldur(secili_kod)

    def _mamul_filtrele(self):
        secili_kod = self.mamul.currentData()
        self._mamul_kutusunu_doldur(secili_kod)

    def _mamul_kutusunu_doldur(self, tercih_kod: str | None = None):
        q = self.mamul_ara.text().strip().casefold()
        suzulen = [
            m for m in self._tum_mamuller
            if not q or q in m['kodu'].casefold() or q in m['adi'].casefold()
        ]
        self.mamul.blockSignals(True)
        self.mamul.clear()
        self.mamul.addItem(f'— Mamül seçin ({len(suzulen)} reçete) —', None)
        for m in suzulen:
            etiket = f"{m['kodu']} — {m['adi']}"
            if m['hat_sayisi'] > 1:
                etiket += f" ({m['hat_sayisi']} grup)"
            self.mamul.addItem(etiket, m['kodu'])
        if tercih_kod:
            idx = self.mamul.findData(tercih_kod)
            if idx >= 0:
                self.mamul.setCurrentIndex(idx)
        elif len(suzulen) == 1 and q:
            self.mamul.setCurrentIndex(1)
        self.mamul.blockSignals(False)
        self._mamul_secildi()

    def _mamul_secildi(self, *_):
        kod = self.mamul.currentData()
        self.hat.blockSignals(True)
        self.hat.clear()
        if kod and self.p.conn:
            hatlar = hat_planlari_getir(self.p.conn, kod)
            if len(hatlar) > 1:
                self.hat.addItem('— Reçete grubu (hat) seçin —', None)
            for h in hatlar:
                tip_ad = 'Mamül' if h['tip'] == 1 else 'Yarı Mamül/Grup'
                ad = f"{h['kod']} — {h['ad']}".strip(' —') or f"Hat #{h['id']}"
                self.hat.addItem(f"{ad} [{tip_ad}, {h['girdi_sayisi']} girdi]", h['id'])
        else:
            self.hat.addItem('— Önce mamül seçin —', None)
        self.hat.blockSignals(False)
        self._hat_secildi()

    def _hat_secildi(self, *_):
        hat_id = self.hat.currentData()
        self._mevcut_girdiler = []
        self._mevcut_stok_map = {}
        if hat_id and self.p.conn:
            self._mevcut_girdiler = hat_girdileri_getir(self.p.conn, int(hat_id))
            for g in self._mevcut_girdiler:
                if g['tipi'] == 1 and g['kart_id']:
                    self._mevcut_stok_map[g['kart_id']] = (
                        self._mevcut_stok_map.get(g['kart_id'], 0.0) + g['miktar']
                    )
        self._mevcut_tabloyu_doldur()
        self._degisti()

    def _mevcut_tabloyu_doldur(self):
        from barkod.ui.ana_pencere import _hucre
        self.t_mevcut.setUpdatesEnabled(False)
        try:
            self.t_mevcut.setRowCount(len(self._mevcut_girdiler))
            for r, g in enumerate(self._mevcut_girdiler):
                self.t_mevcut.setItem(r, 0, _hucre(g['tur']))
                self.t_mevcut.setItem(r, 1, _hucre(g['kodu']))
                self.t_mevcut.setItem(r, 2, _hucre(g['adi']))
                self.t_mevcut.setItem(r, 3, _hucre(g['miktar'], True))
                self.t_mevcut.setItem(r, 4, _hucre(g['birim']))
                if g['tipi'] == 1 and g['kart_id'] in self.kalemler:
                    for c in range(len(self.MEVCUT_SUTUN)):
                        self.t_mevcut.item(r, c).setBackground(QColor('#fff9c4'))
        finally:
            self.t_mevcut.setUpdatesEnabled(True)
        self.lbl_mevcut_sayac.setText(f'{len(self._mevcut_girdiler)} girdi')
        self._mevcut_filtrele()

    def _mevcut_filtrele(self):
        q = self.mevcut_ara.text().strip().casefold()
        for r, g in enumerate(self._mevcut_girdiler):
            gizli = bool(q and q not in g['kodu'].casefold() and q not in g['adi'].casefold())
            self.t_mevcut.setRowHidden(r, gizli)

    # ── okutma ve liste ──
    def okut(self, deger: str) -> bool:
        if not self.mamul.currentData():
            self.durum.emit('Önce üstten eklenecek Mamül reçetesini seçin.')
            return False
        if not self.hat.currentData():
            self.durum.emit('Bu mamül çok gruplu; lütfen üstten Reçete grubunu (hat) seçin.')
            return False
        kid, drm = coz(self.p.conn, deger)
        if not kid:
            self.durum.emit(coz_mesaj(drm, deger))
            return False
        k = self.p.kart_ozet(kid)
        if not k['aktif']:
            self.durum.emit(f"{k['kodu']} PASİF kart — reçeteye eklenemez")
            return False
        if k['kodu'].upper() == str(self.mamul.currentData()).upper():
            self.durum.emit(f"{k['kodu']} seçili mamülün kendisidir — kendi reçetesine eklenemez")
            return False

        miktar = 1.0
        if self.adet_sor.isChecked():
            miktar, ok = QInputDialog.getDouble(
                self, 'Reçete miktarı',
                f"{k['kodu']}\n{k['adi']}\nEklenecek birim başı miktar ({k['birim'] or 'ADET'}):",
                1.0, 0.0001, 1e9, 4,
            )
            if not ok:
                return False

        if kid in self.kalemler:
            self.kalemler[kid]['miktar'] = round(self.kalemler[kid]['miktar'] + miktar, 6)
            self._sira.remove(kid)
        else:
            self.kalemler[kid] = {**k, 'miktar': round(miktar, 6)}
        self._sira.insert(0, kid)
        self._degisti(vurgu=kid)
        self._mevcut_tabloyu_doldur()

        mevcut = self._mevcut_stok_map.get(kid, 0.0)
        ek = self.kalemler[kid]['miktar']
        if mevcut > 0:
            self.durum.emit(
                f"{k['kodu']} reçetede zaten {mevcut:g} {k['birim']} var → +{ek:g} ile {mevcut + ek:g} olacak"
            )
        else:
            self.durum.emit(f"{k['kodu']} → +{ek:g} {k['birim']} (yeni girdi)")
        return True

    def _secili(self) -> int | None:
        r = self.tablo.currentRow()
        if r < 0 or self.tablo.item(r, 0) is None:
            return None
        return int(self.tablo.item(r, 0).data(Qt.UserRole))

    def _miktar_duzelt(self):
        kid = self._secili()
        if kid is None:
            return
        k = self.kalemler[kid]
        mevcut = self._mevcut_stok_map.get(kid, 0.0)
        aciklama = f"{k['kodu']}\n{k['adi']}\n"
        if mevcut > 0:
            aciklama += f"(Mevcut reçetede: {mevcut:g} {k['birim']})\n"
        aciklama += f"Eklenecek miktar (+):"
        v, ok = QInputDialog.getDouble(self, 'Miktar düzelt', aciklama, k['miktar'], 0.0001, 1e9, 4)
        if ok:
            k['miktar'] = round(v, 6)
            self._degisti(vurgu=kid)

    def _sil(self):
        kid = self._secili()
        if kid is None:
            return
        self.kalemler.pop(kid, None)
        self._sira.remove(kid)
        self._degisti()
        self._mevcut_tabloyu_doldur()

    def _temizle(self, sor: bool = True):
        if sor and self.kalemler:
            if QMessageBox.question(self, 'Temizle', 'Okutulan parça listesi temizlensin mi?') != QMessageBox.Yes:
                return
        self.kalemler.clear()
        self._sira.clear()
        self._degisti()
        self._mevcut_tabloyu_doldur()

    def _degisti(self, *_, vurgu: int | None = None):
        self._kontrol_ok = False
        self._taslak = None
        self._yenile(vurgu)

    # ── kontrol (dry-run rollback) ve kaydet (commit) ──
    def _hazirla(self):
        kal = [(kid, self.kalemler[kid]['miktar']) for kid in reversed(self._sira)]
        return recete_taslak_hazirla(
            self.p.conn,
            self.mamul.currentData() or '',
            self.hat.currentData(),
            kal,
            self.p.kullanici_guid() or '',
        )

    def kontrol(self) -> bool:
        if not self.kalemler or self.p.mesgul():
            return False
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            tz = self._hazirla()
            self._taslak = tz
            engel = list(tz.engel)
            sonuc = None if engel else recete_yaz(self.p.conn, tz, commit=False)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, 'Kontrol', f'{type(e).__name__}: {e}')
            return False
        QApplication.restoreOverrideCursor()
        if sonuc and sonuc['sorunlar']:
            engel = sonuc['sorunlar']
        self._kontrol_ok = not engel
        self._yenile()
        if engel:
            self.durum.emit('Kontrol: ' + ' | '.join(engel[:4]))
        else:
            yeni_say = sum(1 for s in tz.satirlar if s.islem_turu == 'ekle')
            gunc_say = sum(1 for s in tz.satirlar if s.islem_turu == 'guncelle')
            self.durum.emit(
                f"Kontrol TAMAM — {tz.mamul_kodu}: {yeni_say} yeni girdi, "
                f"{gunc_say} miktar güncelleme. Deneme yazımı geri alındı. Kaydedebilirsiniz."
            )
        self.p.okut.setFocus()
        return self._kontrol_ok

    def kaydet(self):
        if not self._kontrol_ok or not self._taslak:
            return
        tz = self._taslak
        yeni_say = sum(1 for s in tz.satirlar if s.islem_turu == 'ekle')
        gunc_say = sum(1 for s in tz.satirlar if s.islem_turu == 'guncelle')
        satir_ozet = '<br>'.join(
            f"• <b>{s.kodu}</b>: "
            + (f"yeni girdi <b>{s.eklenecek_miktar:g} {s.birim}</b>"
               if s.islem_turu == 'ekle'
               else f"mevcut {s.mevcut_miktar:g} → <b>{s.yeni_miktar:g} {s.birim}</b> (+{s.eklenecek_miktar:g})")
            for s in tz.satirlar[:12]
        )
        if len(tz.satirlar) > 12:
            satir_ozet += f'<br>… ve {len(tz.satirlar) - 12} kalem daha'

        metin = (
            f"<b>Mamül Reçetesi:</b> {tz.mamul_kodu} — {tz.mamul_adi}<br>"
            f"<b>Reçete Grubu (Hat):</b> {self.hat.currentText()}<br>"
            f"<b>Kullanıcı:</b> {self.p.kullanici_adi()}<br><br>"
            f"<b>{yeni_say} yeni bileşen eklenecek, {gunc_say} mevcut bileşenin miktarı artırılacak:</b><br>"
            f"{satir_ozet}<br><br>"
            "CEO ERP reçetesine kalıcı olarak kaydedilsin mi?"
        )
        if QMessageBox.question(self, "Reçeteye Kaydet", metin) != QMessageBox.Yes:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            tz = self._hazirla()
            engel = list(tz.engel)
            sonuc = None if engel else recete_yaz(self.p.conn, tz, commit=True)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, 'Reçete Kaydı', f'Yazılmadı (geri alındı).\n{type(e).__name__}: {e}')
            return
        QApplication.restoreOverrideCursor()

        if engel or not sonuc or not sonuc['commit']:
            self._kontrol_ok = False
            self._taslak = tz
            self._yenile()
            QMessageBox.warning(
                self, 'Reçete Kaydı',
                'Yazılmadı (geri alındı):\n' + '\n'.join(engel or (sonuc['sorunlar'] if sonuc else [])),
            )
            return

        from barkod.ayar import fis_gunluge_yaz
        fis_gunluge_yaz({
            'tur': 'recete_ekle',
            'mamul_kodu': tz.mamul_kodu,
            'recete_id': tz.recete_id,
            'hat_plani_id': tz.hat_plani_id,
            'kullanici': self.p.kullanici_adi(),
            'eklenen': sonuc['eklenen'],
            'guncellenen': sonuc['guncellenen'],
            'yedek_dosya': sonuc['yedek_dosya'],
        })

        QMessageBox.information(
            self, 'Reçete Güncellendi',
            f"Mamül: {tz.mamul_kodu}\n"
            f"Yeni eklenen girdi: {len(sonuc['eklenen'])}\n"
            f"Miktarı artırılan girdi: {len(sonuc['guncellenen'])}\n"
            f"Yedek: {sonuc['yedek_dosya']}",
        )
        self.durum.emit(
            f"Reçeteye kaydedildi: {tz.mamul_kodu} "
            f"({len(sonuc['eklenen'])} yeni, {len(sonuc['guncellenen'])} güncellendi)"
        )
        self._temizle(sor=False)
        # Sağdaki mevcut girdileri ve hat girdi sayısını tazele
        secili_hat = self.hat.currentData()
        self._mamul_secildi()
        if secili_hat:
            idx = self.hat.findData(secili_hat)
            if idx >= 0:
                self.hat.setCurrentIndex(idx)
        self.p.okut.setFocus()

    # ── tablo görünümü ──
    def _yenile(self, vurgu: int | None = None):
        from barkod.ui.ana_pencere import _hucre
        satir_tz = {s.kart_id: s for s in (self._taslak.satirlar if self._taslak else [])}
        self.tablo.setRowCount(0)
        for kid in self._sira:
            k = self.kalemler[kid]
            s = satir_tz.get(kid)
            r = self.tablo.rowCount()
            self.tablo.insertRow(r)

            it = _hucre(barkod_degeri(kid))
            it.setData(Qt.UserRole, kid)
            self.tablo.setItem(r, 0, it)
            for c, v in enumerate((k['kodu'], k['adi'], k['birim']), 1):
                self.tablo.setItem(r, c, _hucre(v))

            mevcut = s.mevcut_miktar if s is not None else self._mevcut_stok_map.get(kid, 0.0)
            ek = k['miktar']
            yeni = round(mevcut + ek, 6)
            self.tablo.setItem(r, 4, _hucre(mevcut, True))
            self.tablo.setItem(r, 5, _hucre(ek, True))
            self.tablo.setItem(r, 6, _hucre(yeni, True))

            guncel = s is not None and abs(s.eklenecek_miktar - ek) < 1e-9
            if guncel:
                if s.hata:
                    durum, renk = s.hata, '#ffcdd2'
                elif s.uyari:
                    durum, renk = s.uyari, '#fff9c4'
                else:
                    durum, renk = 'Yeni eklenecek (kontrol tamam)', '#c8e6c9'
            else:
                if mevcut > 0:
                    durum, renk = f'Reçetede var ({mevcut:g} → {yeni:g}) · kontrol bekliyor', None
                else:
                    durum, renk = 'Yeni girdi · kontrol bekliyor', None

            self.tablo.setItem(r, 7, _hucre(durum))
            for c in range(len(self.SUTUN)):
                if kid == vurgu and self.tablo.item(r, c):
                    self.tablo.item(r, c).setBackground(QColor('#fff59d'))
                elif renk and self.tablo.item(r, c):
                    self.tablo.item(r, c).setBackground(QColor(renk))

        yeni_say = sum(1 for kid in self._sira if self._mevcut_stok_map.get(kid, 0.0) <= 0)
        gunc_say = len(self._sira) - yeni_say
        if not self._sira:
            self.ozet.setText('Okutulan parça yok.')
        else:
            self.ozet.setText(
                f'{len(self._sira)} kalem ({yeni_say} yeni girdi, {gunc_say} miktar artırma)'
                + (' · KONTROL TAMAM' if self._kontrol_ok else '')
            )
        self.b_kaydet.setEnabled(self._kontrol_ok)
        self.b_kontrol.setEnabled(bool(self.kalemler))
        for b in (self.b_adet, self.b_sil, self.b_temizle):
            b.setEnabled(bool(self.kalemler))
