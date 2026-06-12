"""tab_ayarlar.py — Ayarlar & Hakkında diyaloğu."""
from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QLineEdit, QPushButton, QScrollArea, QFrame, QDialogButtonBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from config import gemini_api_key_kaydet, gemini_api_key_oku

_SURUM = "1.0.0"

_HAKKINDA_METNI = """
<b>CEO ERP Araçları</b> — Üretim ve Satınalma Yönetim Platformu<br><br>

Bu uygulama CEO şirketinin iç operasyonlarını desteklemek amacıyla geliştirilmiştir.
Mamül ağacı yönetimi, maliyet hesaplama, SolidWorks entegrasyonu, stok kartı aktarımı,
satış faturası takibi, üretim eksik stok raporlama ve fatura eşleştirme
işlevlerini tek bir arayüzde bir araya getirir.<br><br>

<b>Geliştirici:</b> Savaş Adigüzel<br>
<b>E-posta:</b> savasadiguzel@gmail.com<br>
<b>GitHub:</b> github.com/savasadiguzel-hash/ceo-erp-arac<br><br>

<b>Bağlantı:</b> SQL Server · WIN-3FATBI9RQAA\\CEO1 · DATABASE 504<br>
<b>Platform:</b> Windows 11 · Python 3 · PyQt5<br><br>

<i>Sürüm {v}</i>
""".strip().format(v=_SURUM)


class AyarlarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar & Hakkında")
        self.setMinimumWidth(560)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(16)

        lay.addWidget(self._ayarlar_grubu())
        lay.addWidget(self._hakkinda_grubu())

        kapat = QPushButton("Kapat")
        kapat.setFixedHeight(34)
        kapat.setStyleSheet(
            "background:#546e7a;color:white;border-radius:6px;"
            "padding:0 24px;font-weight:bold;font-size:12px;border:none;"
        )
        kapat.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(kapat)
        lay.addLayout(btn_row)

    # ── Gemini API Key ─────────────────────────────────────────────────────────

    def _ayarlar_grubu(self) -> QGroupBox:
        grp = QGroupBox("Yapay Zeka — Gemini API Anahtarı")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        aciklama = QLabel(
            "Fatura yüklemede PDF ve görsel (PNG/JPEG) dosyalarını okumak için "
            "Google Gemini API anahtarı gereklidir. Anahtar şifrelenmiş olarak "
            "yerel config.json dosyasında saklanır ve paylaşılmaz."
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

        self._goster_btn = QPushButton("👁")
        self._goster_btn.setFixedSize(34, 34)
        self._goster_btn.setCheckable(True)
        self._goster_btn.setStyleSheet(
            "QPushButton{background:#e8eaf6;color:#3949ab;border-radius:6px;"
            "font-size:16px;border:none;}"
            "QPushButton:checked{background:#c5cae9;}"
        )
        self._goster_btn.toggled.connect(
            lambda acik: self._key_input.setEchoMode(
                QLineEdit.Normal if acik else QLineEdit.Password
            )
        )
        satir.addWidget(self._goster_btn)

        kaydet_btn = QPushButton("💾  Kaydet")
        kaydet_btn.setFixedHeight(34)
        kaydet_btn.setStyleSheet(
            "QPushButton{background:#1565c0;color:white;border-radius:6px;"
            "padding:0 18px;font-weight:bold;font-size:12px;border:none;}"
            "QPushButton:hover{background:#1976d2;}"
        )
        kaydet_btn.clicked.connect(self._kaydet)
        satir.addWidget(kaydet_btn)

        sil_btn = QPushButton("🗑")
        sil_btn.setFixedSize(34, 34)
        sil_btn.setToolTip("API anahtarını sil")
        sil_btn.setStyleSheet(
            "QPushButton{background:#ef5350;color:white;border-radius:6px;"
            "font-size:16px;border:none;}"
            "QPushButton:hover{background:#e53935;}"
        )
        sil_btn.clicked.connect(self._sil)
        satir.addWidget(sil_btn)

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

    # ── Hakkında ───────────────────────────────────────────────────────────────

    def _hakkinda_grubu(self) -> QGroupBox:
        grp = QGroupBox("Hakkında")
        lay = QVBoxLayout(grp)
        lay.setSpacing(6)

        baslik = QLabel("⚙  CEO ERP Araçları")
        baslik.setStyleSheet(
            "font-size:18px;font-weight:bold;color:#1a237e;padding:4px 0;"
        )
        lay.addWidget(baslik)

        ayrac = QFrame()
        ayrac.setFrameShape(QFrame.HLine)
        ayrac.setStyleSheet("color:#e0e0e0;")
        lay.addWidget(ayrac)

        metin = QLabel(_HAKKINDA_METNI)
        metin.setTextFormat(Qt.RichText)
        metin.setWordWrap(True)
        metin.setStyleSheet("color:#37474f;font-size:12px;padding:4px 0;")
        metin.setOpenExternalLinks(True)
        lay.addWidget(metin)

        return grp
