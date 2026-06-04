from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class AnaMenüSayfasi(QWidget):
    arac1_signal = pyqtSignal()
    arac2_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        ana = QVBoxLayout(self)
        ana.setAlignment(Qt.AlignCenter)
        ana.setSpacing(20)
        ana.setContentsMargins(40, 30, 40, 30)

        baslik = QLabel("CEO ERP Araçları")
        baslik.setFont(QFont("Segoe UI", 20, QFont.Bold))
        baslik.setStyleSheet("color:#1a237e;")
        baslik.setAlignment(Qt.AlignCenter)

        alt = QLabel("Kullanmak istediğiniz aracı seçin")
        alt.setAlignment(Qt.AlignCenter)
        alt.setStyleSheet("color:#7986cb;font-size:13px;")

        kartlar = QHBoxLayout()
        kartlar.setSpacing(24)
        kartlar.addWidget(self._kart(
            "🔗", "Mamül Ağacı\nBağlantı Aracı",
            "Reçete veya mamül ağacında yer almayan\n"
            "stokları tespit et ve doğru mamüle bağla.\n\n"
            "Boşta görünen maliyetleri ortadan kaldır.",
            "#e8eaf6", "#3f51b5", self.arac1_signal,
        ))
        kartlar.addWidget(self._kart(
            "💰", "Maliyet\nHesaplama",
            "Tüm reçete ve mamül ağaçlarını tara.\n"
            "LIFO, FIFO veya Ağırlıklı Ortalama ile\n"
            "ürün bazında maliyet raporu oluştur.",
            "#e8f5e9", "#2e7d32", self.arac2_signal,
        ))

        ana.addStretch()
        ana.addWidget(baslik)
        ana.addWidget(alt)
        ana.addSpacing(10)
        ana.addLayout(kartlar)
        ana.addStretch()

    def _kart(self, ikon, baslik, aciklama, bg, renk, sinyal):
        kart = QFrame()
        kart.setFixedSize(320, 300)
        kart.setStyleSheet(
            f"QFrame{{background:{bg};border-radius:14px;border:2px solid {renk}33;}}"
        )
        lay = QVBoxLayout(kart)
        lay.setSpacing(12)
        lay.setContentsMargins(24, 24, 24, 20)

        ikon_lbl = QLabel(ikon)
        ikon_lbl.setStyleSheet("font-size:36px;background:transparent;border:none;")
        ikon_lbl.setAlignment(Qt.AlignCenter)

        bas_lbl = QLabel(baslik)
        bas_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        bas_lbl.setStyleSheet(f"color:{renk};background:transparent;border:none;")
        bas_lbl.setAlignment(Qt.AlignCenter)

        ac_lbl = QLabel(aciklama)
        ac_lbl.setStyleSheet("color:#444;font-size:11px;background:transparent;border:none;")
        ac_lbl.setWordWrap(True)
        ac_lbl.setAlignment(Qt.AlignCenter)

        btn_w = QPushButton("Başlat  →")
        btn_w.setStyleSheet(
            f"background:{renk};color:white;border-radius:8px;"
            f"padding:10px;font-weight:bold;font-size:13px;")
        btn_w.clicked.connect(sinyal.emit)

        lay.addWidget(ikon_lbl)
        lay.addWidget(bas_lbl)
        lay.addWidget(ac_lbl, stretch=1)
        lay.addWidget(btn_w)
        return kart
