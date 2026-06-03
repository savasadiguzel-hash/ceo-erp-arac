import time
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QGroupBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from db.sorgular import tarama_istatistikleri, recetesiz_faturali_stoklar
from ui.stil import etiket, buton


class TaramaThread(QThread):
    adim  = pyqtSignal(str, int, int)
    bitti = pyqtSignal(list)   # kesişim stokları

    def __init__(self, conn, fatura_turleri):
        super().__init__()
        self.conn = conn
        self.fatura_turleri = fatura_turleri

    def run(self):
        adimlar = tarama_istatistikleri(self.conn)
        for mesaj, toplam in adimlar:
            adim = max(1, toplam // 50)
            for i in range(0, toplam + 1, adim):
                self.adim.emit(mesaj, min(i, toplam), toplam)
                time.sleep(0.016)
            self.adim.emit(mesaj, toplam, toplam)
            time.sleep(0.15)
        stoklar = recetesiz_faturali_stoklar(self.conn, self.fatura_turleri)
        self.bitti.emit(stoklar)


class TaramaSayfasi(QWidget):
    bitti = pyqtSignal(list)   # kesişim stokları

    def __init__(self):
        super().__init__()
        self._toplam_stok = 0
        self._recetesiz   = 0
        ana = QVBoxLayout(self)
        ana.setAlignment(Qt.AlignCenter)
        ana.setSpacing(14)

        self.adim_lbl = QLabel("Başlatılıyor...")
        self.adim_lbl.setAlignment(Qt.AlignCenter)
        self.adim_lbl.setStyleSheet("color:#5c6bc0;font-size:13px;")

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(16)
        self.bar.setMaximumWidth(540)
        self.bar.setTextVisible(False)

        self.sayac = QLabel("")
        self.sayac.setAlignment(Qt.AlignCenter)
        self.sayac.setStyleSheet("color:#9e9e9e;font-size:11px;")

        self.ozet_grup = QGroupBox("Tarama Sonucu")
        self.ozet_grup.setMaximumWidth(540)
        self.ozet_grup.hide()
        ol = QVBoxLayout(self.ozet_grup)
        self.ozet_lbl = QLabel()
        self.ozet_lbl.setStyleSheet("font-size:13px;color:#212121;line-height:1.8;")
        ol.addWidget(self.ozet_lbl)

        self.devam_btn = buton("Eşleştirmeye Geç  →", "#3f51b5", min_w=210, h=42)
        self.devam_btn.hide()

        ana.addStretch()
        ana.addWidget(etiket("Stok Analizi Yapılıyor...", "#1a237e", size=15),
                      alignment=Qt.AlignCenter)
        ana.addWidget(self.adim_lbl)
        ana.addWidget(self.bar, alignment=Qt.AlignCenter)
        ana.addWidget(self.sayac)
        ana.addSpacing(8)
        ana.addWidget(self.ozet_grup, alignment=Qt.AlignCenter)
        ana.addWidget(self.devam_btn, alignment=Qt.AlignCenter)
        ana.addStretch()

    def baslat(self, conn, fatura_turleri: list[str]):
        self.ozet_grup.hide()
        self.devam_btn.hide()
        self.bar.setValue(0)
        self.thread = TaramaThread(conn, fatura_turleri)
        self.thread.adim.connect(self._guncelle)
        self.thread.bitti.connect(self._bitti)
        self.thread.start()

    def _guncelle(self, mesaj, mevcut, toplam):
        self.adim_lbl.setText(mesaj)
        self.bar.setValue(int(mevcut / toplam * 100) if toplam else 0)
        self.sayac.setText(f"{mevcut:,} / {toplam:,}")

    def _bitti(self, stoklar: list):
        self.bar.setValue(100)
        self.adim_lbl.setText("Analiz tamamlandı.")
        self.sayac.setText("")
        self.ozet_lbl.setText(
            f"<b>Reçete/mamül ağacında olmayan stoklar:</b>  {len(stoklar):,}<br>"
            f"<b>Bunlardan alış faturası olanlar (kesişim):</b>  "
            f"<span style='color:#c62828;font-weight:bold;'>{len(stoklar)}</span>"
        )
        self.ozet_grup.show()
        self.devam_btn.show()
        self.devam_btn.clicked.connect(lambda: self.bitti.emit(stoklar))
