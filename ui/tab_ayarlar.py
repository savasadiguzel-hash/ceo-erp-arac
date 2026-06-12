"""tab_ayarlar.py — Ayarlar ve Hakkında diyalogları."""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QLineEdit, QPushButton, QFrame,
)
from PyQt5.QtCore import Qt

from config import gemini_api_key_kaydet, gemini_api_key_oku

_SURUM = "1.0.0"


# ── Ayarlar Diyaloğu (Gemini API Key) ─────────────────────────────────────────

class AyarlarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar — Gemini API Anahtarı")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(14)

        lay.addWidget(self._api_grubu())

        kapat = QPushButton("Kapat")
        kapat.setFixedHeight(34)
        kapat.setStyleSheet(
            "QPushButton{background:#546e7a;color:white;border-radius:6px;"
            "padding:0 24px;font-weight:bold;font-size:12px;border:none;}"
            "QPushButton:hover{background:#455a64;}"
        )
        kapat.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(kapat)
        lay.addLayout(row)

    def _api_grubu(self) -> QGroupBox:
        grp = QGroupBox("Gemini API Anahtarı")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        aciklama = QLabel(
            "Fatura yüklemede PDF ve görsel (PNG/JPEG) dosyalarını okumak için "
            "Google Gemini API anahtarı gereklidir.\n"
            "Anahtar şifrelenmiş olarak yerel config.json dosyasında saklanır."
        )
        aciklama.setWordWrap(True)
        aciklama.setStyleSheet("color:#546e7a;font-size:11px;")
        lay.addWidget(aciklama)

        self._durum_lbl = QLabel()
        self._durum_lbl.setStyleSheet("font-size:11px;font-weight:bold;")
        self._guncelle_durum()
        lay.addWidget(self._durum_lbl)

        satir = QHBoxLayout()
        satir.setSpacing(8)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("AIza...")
        self._key_input.setEchoMode(QLineEdit.Password)
        self._key_input.setMinimumHeight(34)
        satir.addWidget(self._key_input, stretch=1)

        goz = QPushButton("👁")
        goz.setFixedSize(34, 34)
        goz.setCheckable(True)
        goz.setStyleSheet(
            "QPushButton{background:#e8eaf6;color:#3949ab;border-radius:6px;"
            "font-size:16px;border:none;}"
            "QPushButton:checked{background:#c5cae9;}"
        )
        goz.toggled.connect(
            lambda acik: self._key_input.setEchoMode(
                QLineEdit.Normal if acik else QLineEdit.Password
            )
        )
        satir.addWidget(goz)

        kaydet = QPushButton("💾  Kaydet")
        kaydet.setFixedHeight(34)
        kaydet.setStyleSheet(
            "QPushButton{background:#1565c0;color:white;border-radius:6px;"
            "padding:0 18px;font-weight:bold;font-size:12px;border:none;}"
            "QPushButton:hover{background:#1976d2;}"
        )
        kaydet.clicked.connect(self._kaydet)
        satir.addWidget(kaydet)

        sil = QPushButton("🗑")
        sil.setFixedSize(34, 34)
        sil.setToolTip("API anahtarını sil")
        sil.setStyleSheet(
            "QPushButton{background:#ef5350;color:white;border-radius:6px;"
            "font-size:16px;border:none;}"
            "QPushButton:hover{background:#e53935;}"
        )
        sil.clicked.connect(self._sil)
        satir.addWidget(sil)

        lay.addLayout(satir)
        return grp

    def _kaydet(self):
        key = self._key_input.text().strip()
        if not key:
            self._durum_lbl.setText("⚠  Anahtar alanı boş.")
            self._durum_lbl.setStyleSheet("color:#e65100;font-size:11px;font-weight:bold;")
            return
        gemini_api_key_kaydet(key)
        self._key_input.clear()
        self._guncelle_durum()

    def _sil(self):
        gemini_api_key_kaydet("")
        self._key_input.clear()
        self._guncelle_durum()

    def _guncelle_durum(self):
        if gemini_api_key_oku():
            self._durum_lbl.setText("✅  API anahtarı kayıtlı.")
            self._durum_lbl.setStyleSheet("color:#2e7d32;font-size:11px;font-weight:bold;")
        else:
            self._durum_lbl.setText("❌  API anahtarı henüz girilmemiş.")
            self._durum_lbl.setStyleSheet("color:#b71c1c;font-size:11px;font-weight:bold;")


# ── Hakkında Diyaloğu ──────────────────────────────────────────────────────────

class HakkindaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hakkında — CEO ERP Araçları")
        self.setMinimumWidth(480)
        self.setFixedHeight(340)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(12)

        baslik = QLabel("⚙  CEO ERP Araçları")
        baslik.setStyleSheet(
            "font-size:20px;font-weight:bold;color:#1a237e;padding:2px 0;"
        )
        lay.addWidget(baslik)

        surum = QLabel(f"Sürüm {_SURUM}")
        surum.setStyleSheet("color:#9e9e9e;font-size:11px;")
        lay.addWidget(surum)

        ayrac = QFrame()
        ayrac.setFrameShape(QFrame.HLine)
        ayrac.setStyleSheet("color:#e0e0e0;")
        lay.addWidget(ayrac)

        metin = QLabel(
            "Üretim ve satınalma operasyonlarını desteklemek amacıyla "
            "CEO şirketi için geliştirilmiştir.<br><br>"
            "<b>Geliştirici:</b> Savaş Adigüzel<br>"
            "<b>E-posta:</b> savasadiguzel@gmail.com<br>"
            "<b>GitHub:</b> github.com/savasadiguzel-hash/ceo-erp-arac<br><br>"
            "<b>Veritabanı:</b> SQL Server · WIN-3FATBI9RQAA\\CEO1 · DB 504<br>"
            "<b>Platform:</b> Windows 11 · Python 3 · PyQt5"
        )
        metin.setTextFormat(Qt.RichText)
        metin.setWordWrap(True)
        metin.setStyleSheet("color:#37474f;font-size:12px;line-height:1.5;")
        lay.addWidget(metin)

        lay.addStretch()

        kapat = QPushButton("Kapat")
        kapat.setFixedHeight(34)
        kapat.setStyleSheet(
            "QPushButton{background:#546e7a;color:white;border-radius:6px;"
            "padding:0 24px;font-weight:bold;font-size:12px;border:none;}"
            "QPushButton:hover{background:#455a64;}"
        )
        kapat.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(kapat)
        lay.addLayout(row)
