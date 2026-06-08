"""mamul_agaci_tab.py — Mamül Ağacı Bağlantı Aracı sekmesi.

Mevcut BaglantiSayfasi → TaramaSayfasi → EslestirmeSayfasi → RaporSayfasi
akisini tek bir QWidget sekme icinde sarar.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QMessageBox,
)
from PyQt5.QtCore import pyqtSignal

from config import config_kaydet
from db.baglanti import get_connection
from ui.baglanti   import BaglantiSayfasi
from ui.tarama     import TaramaSayfasi
from ui.eslestirme import EslestirmeSayfasi
from ui.rapor      import RaporSayfasi


class MamulAgaciTab(QWidget):
    durum_guncelle = pyqtSignal(str)   # ana pencere status bar icin

    def __init__(self):
        super().__init__()
        self._conn = None

        self.s1 = BaglantiSayfasi()
        self.s2 = TaramaSayfasi()
        self.s3 = EslestirmeSayfasi()
        self.s4 = RaporSayfasi()

        self.stack = QStackedWidget()
        for s in [self.s1, self.s2, self.s3, self.s4]:
            self.stack.addWidget(s)

        self.s1.devam.connect(self._tarama_baslat)
        self.s2.bitti.connect(self._eslestirme_baslat)
        self.s3.rapor_signal.connect(self._rapor_goster)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)

    # ── bağlantı ────────────────────────────────────────────────────────────
    def _baglanti_al(self):
        if self._conn is None:
            self._conn = get_connection(
                self.s1.sunucu.text(), self.s1.db_adi.text(),
                self.s1.kullanici.text(), self.s1.sifre.text(),
            )
        return self._conn

    # ── adım geçişleri ───────────────────────────────────────────────────────
    def _tarama_baslat(self):
        tarihler = self.s1.tarih_araligi()
        if tarihler is None:
            QMessageBox.warning(self, "Eksik Bilgi",
                                "Lütfen geçerli başlangıç ve bitiş tarihi girin.\n"
                                "Format: GG.AA.YYYY")
            return
        try:
            conn = self._baglanti_al()
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası",
                                 f"Veritabanına bağlanılamadı:\n\n{e}")
            return
        config_kaydet(
            self.s1.sunucu.text(), self.s1.db_adi.text(),
            self.s1.kullanici.text(), self.s1.sifre.text(),
        )
        yontem = self.s1.secili_yontem()
        self.stack.setCurrentIndex(1)
        self.s2.baslat(conn, yontem, tarihler[0], tarihler[1])
        self.durum_guncelle.emit("Tarama çalışıyor…")

    def _eslestirme_baslat(self, stoklar: list):
        conn = self._baglanti_al()
        self.stack.setCurrentIndex(2)
        self.s3.baslat(conn, stoklar)
        self.durum_guncelle.emit(f"{len(stoklar)} bağlantısız stok bulundu.")

    def _rapor_goster(self, sonuclar: list):
        self.s4.goster(sonuclar)
        self.stack.setCurrentIndex(3)
        self.durum_guncelle.emit("Rapor hazır.")

    # ── sıfırla ─────────────────────────────────────────────────────────────
    def sifirla(self):
        """Bağlantı sayfasına geri döner."""
        self._conn = None
        self.stack.setCurrentIndex(0)
