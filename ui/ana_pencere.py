from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFrame, QHBoxLayout,
    QLabel, QStackedWidget, QStatusBar, QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from config import USE_DEMO, config_kaydet
from db.baglanti import get_connection
from ui.stil import STIL
from ui.ana_menu    import AnaMenüSayfasi
from ui.baglanti    import BaglantiSayfasi
from ui.tarama      import TaramaSayfasi
from ui.eslestirme  import EslestirmeSayfasi
from ui.rapor       import RaporSayfasi
from ui.maliyet     import MaliyetSayfasi

ADIMLAR = ["① Bağlantı", "② Tarama", "③ Eşleştirme", "④ Rapor"]


class AnaPencere(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CEO ERP — Araçlar")
        self.setMinimumSize(920, 680)
        self.resize(1020, 750)
        self.setStyleSheet(STIL)

        self._conn = None

        self._adim_bar = self._adim_bar_olustur()
        self.stack = QStackedWidget()

        self.s0 = AnaMenüSayfasi()
        self.s1 = BaglantiSayfasi()
        self.s2 = TaramaSayfasi()
        self.s3 = EslestirmeSayfasi()
        self.s4 = RaporSayfasi()
        self.s5 = MaliyetSayfasi()

        for s in [self.s0, self.s1, self.s2, self.s3, self.s4, self.s5]:
            self.stack.addWidget(s)

        self.s0.arac1_signal.connect(lambda: self.sayfa_gec(1))
        self.s0.arac2_signal.connect(self._maliyet_baslat)
        self.s1.devam.connect(self._tarama_baslat)
        self.s1.geri.connect(lambda: self.sayfa_gec(0))
        self.s2.bitti.connect(self._eslestirme_baslat)
        self.s3.rapor_signal.connect(self._rapor_goster)

        merkez = QWidget()
        lay = QVBoxLayout(merkez)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._adim_bar)
        lay.addWidget(self.stack, stretch=1)
        self.setCentralWidget(merkez)

        self.sb = QStatusBar()
        self.sb.setStyleSheet("background:#f5f5f5;color:#555;font-size:11px;")
        self.setStatusBar(self.sb)
        mod = "Demo" if USE_DEMO else "Gerçek DB"
        self.sb.showMessage(f"Mod: {mod} — Araç seçmek için ana menüyü kullanın.")

    # ── Bağlantı yönetimi ────────────────────────────────────────────────────
    def _baglanti_al(self):
        if USE_DEMO:
            return None
        if self._conn is None:
            self._conn = get_connection(
                self.s1.sunucu.text(), self.s1.db_adi.text(),
                self.s1.kullanici.text(), self.s1.sifre.text(),
            )
        return self._conn

    # ── Sayfa geçişleri ──────────────────────────────────────────────────────
    def sayfa_gec(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self._adim_guncelle(idx)

    def _tarama_baslat(self):
        tarihler = self.s1.tarih_araligi()
        if tarihler is None:
            QMessageBox.warning(self, "Eksik Bilgi",
                                "Lütfen geçerli bir başlangıç ve bitiş tarihi girin.\n\n"
                                "Format: GG.AA.YYYY  (örn: 01.01.2025)")
            return
        try:
            conn = self._baglanti_al()
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası",
                                 f"Veritabanına bağlanılamadı:\n\n{e}")
            return
        if not USE_DEMO:
            config_kaydet(
                self.s1.sunucu.text(),
                self.s1.db_adi.text(),
                self.s1.kullanici.text(),
                self.s1.sifre.text(),
            )
        turleri = self.s1.secili_fatura_turleri()
        self.sayfa_gec(2)
        self.s2.baslat(conn, turleri, tarihler[0], tarihler[1])

    def _eslestirme_baslat(self, stoklar: list):
        conn = self._baglanti_al()
        self.sayfa_gec(3)
        self.s3.baslat(conn, stoklar)

    def _rapor_goster(self, sonuclar: list):
        self.s4.goster(sonuclar)
        self.sayfa_gec(4)

    def _maliyet_baslat(self):
        conn = self._baglanti_al()
        self.s5.baslat(conn)
        self.sayfa_gec(5)

    # ── Adım çubuğu ─────────────────────────────────────────────────────────
    def _adim_bar_olustur(self):
        frame = QFrame()
        frame.setFixedHeight(44)
        frame.setStyleSheet("background:#3f51b5;")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(20, 0, 20, 0)
        self._adim_lbller = []
        for i, ad in enumerate(ADIMLAR):
            lbl = QLabel(ad)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
            lbl.setStyleSheet("color:rgba(255,255,255,0.4);border:none;")
            lay.addWidget(lbl)
            self._adim_lbller.append(lbl)
            if i < len(ADIMLAR) - 1:
                ay = QLabel("›")
                ay.setStyleSheet("color:rgba(255,255,255,0.3);border:none;font-size:16px;")
                ay.setAlignment(Qt.AlignCenter)
                lay.addWidget(ay)
        return frame

    def _adim_guncelle(self, idx: int):
        if idx == 0:
            for w in self._adim_lbller:
                w.setStyleSheet("color:rgba(255,255,255,0.5);border:none;font-size:10px;")
            return
        if idx == 5:
            for i, w in enumerate(self._adim_lbller):
                w.setText(["💰 Maliyet", "Hesaplama", "", ""][i] if i < 2 else "")
                w.setStyleSheet("color:white;border:none;font-size:11px;" if i == 0
                                else "color:rgba(255,255,255,0.4);border:none;")
            return
        for i, w in enumerate(self._adim_lbller):
            w.setText(ADIMLAR[i])
            aktif = idx - 1
            if i == aktif:
                w.setStyleSheet("color:white;border:none;font-size:11px;")
            elif i < aktif:
                w.setStyleSheet("color:rgba(255,255,255,0.6);border:none;font-size:10px;")
            else:
                w.setStyleSheet("color:rgba(255,255,255,0.35);border:none;font-size:10px;")
