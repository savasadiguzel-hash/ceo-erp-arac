"""tab_ayarlar.py — Ayarlar & Hakkında sekmesi."""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QLineEdit, QPushButton, QScrollArea, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from config import gemini_api_key_kaydet, gemini_api_key_oku

_UYGULAMA_SURUMU = "1.0.0"

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

<i>Sürüm {surum}</i>
""".strip().format(surum=_UYGULAMA_SURUMU)


class TabAyarlar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        dis = QVBoxLayout(self)
        dis.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        ic = QWidget()
        lay = QVBoxLayout(ic)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(20)

        lay.addWidget(self._ayarlar_grubu())
        lay.addWidget(self._hakkinda_grubu())
        lay.addStretch()

        scroll.setWidget(ic)
        dis.addWidget(scroll)

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
            "background:#e8eaf6;color:#3949ab;border-radius:6px;"
            "font-size:16px;border:none;"
        )
        self._goster_btn.toggled.connect(self._goster_toggled)
        satir.addWidget(self._goster_btn)

        kaydet_btn = QPushButton("💾  Kaydet")
        kaydet_btn.setFixedHeight(34)
        kaydet_btn.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1565c0,stop:1 #1976d2);"
            "color:white;border-radius:6px;padding:0 18px;"
            "font-weight:bold;font-size:12px;border:none;"
        )
        kaydet_btn.clicked.connect(self._kaydet)
        satir.addWidget(kaydet_btn)

        sil_btn = QPushButton("🗑  Sil")
        sil_btn.setFixedHeight(34)
        sil_btn.setStyleSheet(
            "background:#ef5350;color:white;border-radius:6px;"
            "padding:0 14px;font-weight:bold;font-size:12px;border:none;"
        )
        sil_btn.clicked.connect(self._sil)
        satir.addWidget(sil_btn)

        lay.addLayout(satir)
        return grp

    def _goster_toggled(self, acik: bool):
        self._key_input.setEchoMode(
            QLineEdit.Normal if acik else QLineEdit.Password
        )

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

        logo_lbl = QLabel("⚙  CEO ERP Araçları")
        logo_lbl.setStyleSheet(
            "font-size:22px;font-weight:bold;color:#1a237e;padding:6px 0;"
        )
        lay.addWidget(logo_lbl)

        ayrac = QFrame()
        ayrac.setFrameShape(QFrame.HLine)
        ayrac.setStyleSheet("color:#e0e0e0;")
        lay.addWidget(ayrac)

        metin = QLabel(_HAKKINDA_METNI)
        metin.setTextFormat(Qt.RichText)
        metin.setWordWrap(True)
        metin.setStyleSheet("color:#37474f;font-size:12px;line-height:1.6;padding:4px 0;")
        metin.setOpenExternalLinks(True)
        lay.addWidget(metin)

        return grp
