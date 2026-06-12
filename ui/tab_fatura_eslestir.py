"""tab_fatura_eslestir.py — Fatura Eşleştirme sekmesi (7. sekme)."""
import json
import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QGridLayout,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QSplitter,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QButtonGroup, QRadioButton, QApplication,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from config import DB_DEFAULTS
from db.baglanti import get_connection
from ui.stil import etiket

BASE = Path(__file__).resolve().parent.parent

_BTN_MAVI = (
    "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1565c0,stop:1 #1976d2);"
    "color:white;border-radius:6px;padding:9px 20px;font-weight:bold;font-size:13px;"
)
_BTN_YESIL = (
    "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2e7d32,stop:1 #43a047);"
    "color:white;border-radius:6px;padding:9px 20px;font-weight:bold;font-size:13px;"
)
_BTN_PASIF = (
    "background:#bdbdbd;color:#757575;"
    "border-radius:6px;padding:9px 20px;font-weight:bold;font-size:13px;"
)

_RENK_GUCLU    = QColor("#c8e6c9")
_RENK_GOZDEN   = QColor("#fff3e0")
_RENK_YOK      = QColor("#ffcdd2")
_RENK_ISCILIK  = QColor("#e3f2fd")
_RENK_MUHTELIF = QColor("#f5f5f5")


# ── Thread'ler ─────────────────────────────────────────────────────────────────

class BaglantiThread(QThread):
    bitti = pyqtSignal(object)
    hata  = pyqtSignal(str)

    def __init__(self, sunucu, veritabani, kullanici, sifre):
        super().__init__()
        self.sunucu = sunucu; self.veritabani = veritabani
        self.kullanici = kullanici; self.sifre = sifre

    def run(self):
        try:
            conn = get_connection(self.sunucu, self.veritabani, self.kullanici, self.sifre)
            self.bitti.emit(conn)
        except Exception as e:
            logging.error("FaturaEslestir BaglantiThread: %s", e)
            self.hata.emit(str(e))


class StokYuklemeThread(QThread):
    bitti = pyqtSignal(list)
    hata  = pyqtSignal(str)

    def __init__(self, conn):
        super().__init__()
        self.conn = conn

    def run(self):
        try:
            from tools.fatura_eslestir import stok_kartlari_db
            self.bitti.emit(stok_kartlari_db(self.conn))
        except Exception as e:
            logging.error("FaturaEslestir StokYuklemeThread: %s", e)
            self.hata.emit(str(e))


class EslestirmeThread(QThread):
    bitti = pyqtSignal(list, list)   # temiz_sonuclar, kirli_kalemler
    hata  = pyqtSignal(str)

    def __init__(self, kalemler, stok_kartlari):
        super().__init__()
        self.kalemler = kalemler
        self.stok_kartlari = stok_kartlari

    def run(self):
        try:
            from tools.fatura_eslestir import kova_ayir, adaylar_bul, operasyon_mu
            temiz, kirli = kova_ayir(self.kalemler)
            kirli_ids = {id(k) for k in kirli}
            sonuclar = []
            for idx, kalem in enumerate(self.kalemler):
                if id(kalem) in kirli_ids:
                    continue
                sonuclar.append({
                    "kalem":      kalem,
                    "kalem_idx":  idx,
                    "adaylar":    adaylar_bul(kalem, self.stok_kartlari),
                    "operasyon":  operasyon_mu(kalem),
                })
            self.bitti.emit(sonuclar, kirli)
        except Exception as e:
            logging.error("FaturaEslestir EslestirmeThread: %s", e)
            self.hata.emit(str(e))


# ── Ana Sekme ──────────────────────────────────────────────────────────────────

class FaturaEslestirTab(QWidget):
    durum_guncelle = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.conn = None
        self._stoklar: list[tuple[str, str]] = []
        self._kalemler: list[dict] = []
        self._temiz_sonuclar: list[dict] = []
        self._kirli_kalemler: list[dict] = []
        self._mevcut_kirli_kalem: dict | None = None
        self._baglanti_thread = None
        self._stok_thread     = None
        self._eslestirme_thread = None
        self._kur()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _kur(self):
        ana = QHBoxLayout(self)
        ana.setContentsMargins(12, 10, 12, 10)
        ana.setSpacing(12)
        ana.addWidget(self._sol_panel(),  stretch=2)
        ana.addWidget(self._sag_panel(), stretch=3)

    def _sol_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        bas = QLabel("Fatura Eşleştirme")
        bas.setFont(QFont("Segoe UI", 13, QFont.Bold))
        bas.setStyleSheet("color:#1a237e;")
        lay.addWidget(bas)

        # DB bağlantı
        db_grup = QGroupBox("Veritabanı Bağlantısı")
        dg = QGridLayout(db_grup)
        dg.setSpacing(6)
        self.fe_sunucu    = QLineEdit(DB_DEFAULTS["sunucu"])
        self.fe_db        = QLineEdit(DB_DEFAULTS["veritabani"])
        self.fe_kullanici = QLineEdit(DB_DEFAULTS["kullanici"])
        self.fe_sifre     = QLineEdit(DB_DEFAULTS.get("sifre", ""))
        self.fe_sifre.setEchoMode(QLineEdit.Password)
        self.fe_sifre.setPlaceholderText("••••••••")
        for i, (k, v) in enumerate([
            ("Sunucu:",     self.fe_sunucu),
            ("Veritabanı:", self.fe_db),
            ("Kullanıcı:",  self.fe_kullanici),
            ("Şifre:",      self.fe_sifre),
        ]):
            dg.addWidget(etiket(k), i, 0)
            dg.addWidget(v, i, 1)
        lay.addWidget(db_grup)

        self.baglan_btn = QPushButton("🔌  Bağlan ve Stok Yükle")
        self.baglan_btn.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1565c0,stop:1 #1976d2);"
            "color:white;border-radius:6px;padding:8px 16px;font-weight:bold;font-size:12px;"
        )
        self.baglan_btn.clicked.connect(self._baglan)
        lay.addWidget(self.baglan_btn)

        self.stok_lbl = QLabel("Stok kartları yüklenmedi.")
        self.stok_lbl.setStyleSheet("color:#9e9e9e;font-size:11px;padding:2px;")
        lay.addWidget(self.stok_lbl)

        # JSON yükleme
        fat_grup = QGroupBox("Fatura Kalemleri (JSON)")
        fg = QVBoxLayout(fat_grup)
        fg.setSpacing(6)
        btn_row = QHBoxLayout()
        self.json_yukle_btn = QPushButton("📂  JSON Yükle")
        self.json_yukle_btn.setStyleSheet(
            "background:#546e7a;color:white;border-radius:5px;"
            "padding:6px 12px;font-weight:bold;font-size:11px;"
        )
        self.json_yukle_btn.clicked.connect(self._json_yukle)
        self.ornek_yukle_btn = QPushButton("🔬  Örnek Yükle")
        self.ornek_yukle_btn.setStyleSheet(
            "background:#546e7a;color:white;border-radius:5px;"
            "padding:6px 12px;font-weight:bold;font-size:11px;"
        )
        self.ornek_yukle_btn.clicked.connect(self._ornek_yukle)
        btn_row.addWidget(self.json_yukle_btn)
        btn_row.addWidget(self.ornek_yukle_btn)
        fg.addLayout(btn_row)
        self.kalem_sayisi_lbl = QLabel("Yüklü kalem yok.")
        self.kalem_sayisi_lbl.setStyleSheet("color:#9e9e9e;font-size:11px;")
        fg.addWidget(self.kalem_sayisi_lbl)
        lay.addWidget(fat_grup)

        kalem_bas = QLabel("Fatura Kalemleri")
        kalem_bas.setStyleSheet("color:#37474f;font-weight:bold;font-size:11px;")
        lay.addWidget(kalem_bas)

        self.kalem_liste = QListWidget()
        self.kalem_liste.setStyleSheet(
            "QListWidget{background:white;border:1px solid #c5cae9;border-radius:6px;font-size:11px;}"
            "QListWidget::item{padding:6px 8px;border-bottom:1px solid #f0f0f0;}"
            "QListWidget::item:selected{background:#e8eaf6;color:#1a237e;}"
        )
        self.kalem_liste.currentRowChanged.connect(self._kalem_secildi)
        lay.addWidget(self.kalem_liste, stretch=1)

        self.eslestir_btn = QPushButton("🔍  Eşleştir")
        self.eslestir_btn.setStyleSheet(_BTN_PASIF)
        self.eslestir_btn.setEnabled(False)
        self.eslestir_btn.clicked.connect(self._eslestir)
        lay.addWidget(self.eslestir_btn)

        self.durum_lbl = QLabel("")
        self.durum_lbl.setStyleSheet("color:#555;font-size:11px;padding:4px;")
        self.durum_lbl.setAlignment(Qt.AlignCenter)
        self.durum_lbl.setWordWrap(True)
        lay.addWidget(self.durum_lbl)

        return w

    def _sag_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._sag_ust())
        splitter.addWidget(self._sag_alt())
        splitter.setSizes([280, 180])
        lay.addWidget(splitter, stretch=3)

        lay.addWidget(self._alt_panel(), stretch=2)
        return w

    def _sag_ust(self):
        w = QGroupBox("Seçili Kalem — Eşleştirme Önerileri")
        lay = QVBoxLayout(w)
        lay.setSpacing(6)

        self.oneri_baslik = QLabel("Listeden bir kalem seçin.")
        self.oneri_baslik.setStyleSheet(
            "color:#3949ab;font-size:12px;font-weight:bold;padding:2px;"
        )
        self.oneri_baslik.setWordWrap(True)
        lay.addWidget(self.oneri_baslik)

        self.oneri_liste = QListWidget()
        self.oneri_liste.setStyleSheet(
            "QListWidget{background:white;border:1px solid #e0e0e0;border-radius:4px;"
            "font-size:12px;font-family:'Consolas','Courier New',monospace;}"
            "QListWidget::item{padding:8px 10px;border-bottom:1px solid #f5f5f5;}"
            "QListWidget::item:selected{background:#e8eaf6;color:#1a237e;}"
        )
        lay.addWidget(self.oneri_liste)
        return w

    def _sag_alt(self):
        self._dagitim_grup = QGroupBox("Tutar Dagitimi — Muhtelif Kalem")
        lay = QVBoxLayout(self._dagitim_grup)
        lay.setSpacing(6)

        # Yöntem radio butonları
        yontem_lay = QHBoxLayout()
        yontem_lay.addWidget(QLabel("Yöntem:"))
        self._dag_btn_grp = QButtonGroup(self)
        for idx, (key, lbl) in enumerate([
            ("esit",    "Esit"),
            ("agirlik", "Agirlik"),
            ("miktar",  "Miktar"),
            ("elle",    "Elle"),
        ]):
            rb = QRadioButton(lbl)
            rb.setProperty("yontem", key)
            if idx == 0:
                rb.setChecked(True)
            self._dag_btn_grp.addButton(rb, idx)
            yontem_lay.addWidget(rb)
        yontem_lay.addStretch()
        lay.addLayout(yontem_lay)

        # Dağıtım tablosu
        self.dag_tablo = QTableWidget()
        self.dag_tablo.setColumnCount(4)
        self.dag_tablo.setHorizontalHeaderLabels(["Stok Kodu", "Aciklama", "Ag./Mkt.", "Tutar (TL)"])
        self.dag_tablo.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.SelectedClicked
        )
        self.dag_tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dag_tablo.verticalHeader().setVisible(False)
        self.dag_tablo.setMaximumHeight(140)
        self.dag_tablo.setStyleSheet(
            "QTableWidget{background:white;font-size:11px;}"
            "QHeaderView::section{background:#e8eaf6;color:#1a237e;"
            "font-weight:bold;font-size:11px;padding:4px;border:none;}"
        )
        lay.addWidget(self.dag_tablo)

        btn_row = QHBoxLayout()
        self.dag_hesapla_btn = QPushButton("Hesapla")
        self.dag_hesapla_btn.setStyleSheet(
            "background:#1565c0;color:white;border-radius:5px;"
            "padding:6px 14px;font-weight:bold;font-size:11px;"
        )
        self.dag_hesapla_btn.clicked.connect(self._dagitim_hesapla)
        btn_row.addWidget(self.dag_hesapla_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.dag_uyari_lbl = QLabel("")
        self.dag_uyari_lbl.setStyleSheet("color:#c62828;font-size:11px;padding:2px;")
        self.dag_uyari_lbl.setWordWrap(True)
        lay.addWidget(self.dag_uyari_lbl)

        return self._dagitim_grup

    def _alt_panel(self):
        w = QGroupBox("Satinalma Notu")
        lay = QVBoxLayout(w)
        lay.setSpacing(6)

        btn_row = QHBoxLayout()
        self.metin_uret_btn = QPushButton("Satinalma Metni Uret")
        self.metin_uret_btn.setStyleSheet(_BTN_YESIL)
        self.metin_uret_btn.setEnabled(False)
        self.metin_uret_btn.clicked.connect(self._metin_uret)
        btn_row.addWidget(self.metin_uret_btn)

        self.kopyala_btn = QPushButton("Kopyala")
        self.kopyala_btn.setStyleSheet(_BTN_PASIF)
        self.kopyala_btn.setEnabled(False)
        self.kopyala_btn.clicked.connect(self._kopyala)
        btn_row.addWidget(self.kopyala_btn)

        self.kaydet_btn = QPushButton("Dosyaya Kaydet")
        self.kaydet_btn.setStyleSheet(_BTN_PASIF)
        self.kaydet_btn.setEnabled(False)
        self.kaydet_btn.clicked.connect(self._dosyaya_kaydet)
        btn_row.addWidget(self.kaydet_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.metin_alan = QTextEdit()
        self.metin_alan.setReadOnly(True)
        self.metin_alan.setFont(QFont("Consolas", 10))
        self.metin_alan.setStyleSheet(
            "background:#fafafa;border:1px solid #e0e0e0;border-radius:4px;"
        )
        self.metin_alan.setPlaceholderText(
            "JSON yukleyin → Eslesitir → 'Satinalma Metni Uret' butonuna basin."
        )
        lay.addWidget(self.metin_alan)
        return w

    # ── Bağlantı ──────────────────────────────────────────────────────────────

    def _baglan(self):
        self.baglan_btn.setEnabled(False)
        self.baglan_btn.setText("  Baglanıyor…")
        self._baglanti_thread = BaglantiThread(
            self.fe_sunucu.text(), self.fe_db.text(),
            self.fe_kullanici.text(), self.fe_sifre.text(),
        )
        self._baglanti_thread.bitti.connect(self._baglanti_tamam)
        self._baglanti_thread.hata.connect(self._baglanti_hatasi)
        self._baglanti_thread.start()

    def _baglanti_tamam(self, conn):
        self.conn = conn
        self.baglan_btn.setText("  Stok Yukleniyor…")
        self.durum_lbl.setText("Baglandi, stok kartlari yukleniyor…")
        self.durum_lbl.setStyleSheet("color:#1565c0;font-size:11px;padding:4px;")
        self._stok_thread = StokYuklemeThread(conn)
        self._stok_thread.bitti.connect(self._stok_yuklendi)
        self._stok_thread.hata.connect(self._stok_hatasi)
        self._stok_thread.start()

    def _baglanti_hatasi(self, mesaj: str):
        self.baglan_btn.setEnabled(True)
        self.baglan_btn.setText("🔌  Baglan ve Stok Yukle")
        QMessageBox.critical(self, "Baglanti Hatasi",
                             f"Veritabanına bağlanılamadı:\n\n{mesaj}")

    def _stok_yuklendi(self, stoklar: list):
        self._stoklar = stoklar
        self.baglan_btn.setText("✅  Bagli")
        self.baglan_btn.setStyleSheet(
            "background:#2e7d32;color:white;border-radius:6px;"
            "padding:8px 16px;font-weight:bold;font-size:12px;"
        )
        self.stok_lbl.setText(f"{len(stoklar):,} stok karti yuklendi.")
        self.stok_lbl.setStyleSheet("color:#2e7d32;font-size:11px;padding:2px;")
        self.durum_lbl.setText(f"{len(stoklar):,} stok karti hazir.")
        self.durum_lbl.setStyleSheet("color:#2e7d32;font-size:11px;padding:4px;")
        self._eslestir_btn_guncelle()
        self.durum_guncelle.emit(f"Fatura Eslestir: {len(stoklar):,} stok karti yuklendi")

    def _stok_hatasi(self, mesaj: str):
        self.baglan_btn.setEnabled(True)
        self.baglan_btn.setText("🔌  Baglan ve Stok Yukle")
        QMessageBox.critical(self, "Stok Yukleme Hatasi",
                             f"Stok kartlari alinamadi:\n\n{mesaj}")

    # ── JSON yükleme ──────────────────────────────────────────────────────────

    def _json_yukle(self):
        dosya, _ = QFileDialog.getOpenFileName(
            self, "Fatura JSON Dosyasi Sec",
            str(BASE / "referans" / "faturalar"),
            "JSON Dosyasi (*.json)",
        )
        if dosya:
            self._json_oku(dosya)

    def _ornek_yukle(self):
        ornek = BASE / "referans" / "faturalar" / "test_kalemleri.json"
        if ornek.exists():
            self._json_oku(str(ornek))
        else:
            QMessageBox.warning(self, "Dosya Bulunamadi",
                                f"Ornek dosya bulunamadi:\n{ornek}")

    def _json_oku(self, dosya: str):
        try:
            with open(dosya, encoding="utf-8") as f:
                veri = json.load(f)
            if not isinstance(veri, list):
                raise ValueError("JSON dosyasi bir liste icermeli.")
            self._kalemler = veri
            self._temiz_sonuclar = []
            self._kirli_kalemler = []
            self._kalem_listesini_doldur()
            self.kalem_sayisi_lbl.setText(f"{len(veri)} kalem yuklendi.")
            self.kalem_sayisi_lbl.setStyleSheet("color:#2e7d32;font-size:11px;")
            self.durum_lbl.setText(f"{len(veri)} fatura kalemi yuklendi.")
            self.durum_lbl.setStyleSheet("color:#555;font-size:11px;padding:4px;")
            self._eslestir_btn_guncelle()
        except Exception as e:
            QMessageBox.critical(self, "JSON Okuma Hatasi", f"Dosya okunamadi:\n{e}")

    def _kalem_listesini_doldur(self):
        self.kalem_liste.clear()
        self.oneri_liste.clear()
        self.oneri_baslik.setText("Listeden bir kalem secin.")
        self.dag_tablo.setRowCount(0)
        self.dag_uyari_lbl.setText("")
        self.metin_uret_btn.setEnabled(False)
        self.kopyala_btn.setEnabled(False)
        self.kopyala_btn.setStyleSheet(_BTN_PASIF)
        self.kaydet_btn.setEnabled(False)
        self.kaydet_btn.setStyleSheet(_BTN_PASIF)
        self.metin_alan.clear()

        from tools.fatura_eslestir import operasyon_mu, kirli_neden
        for kalem in self._kalemler:
            aciklama  = kalem.get("aciklama", "")
            tedarikci = kalem.get("tedarikci", "")
            kirli     = kirli_neden(kalem)
            is_op     = operasyon_mu(kalem)
            if kirli:
                badge = "MUHTELIF"; renk = _RENK_MUHTELIF; frenk = QColor("#616161")
            elif is_op:
                badge = "ISCILK";   renk = _RENK_ISCILIK;  frenk = QColor("#1565c0")
            else:
                badge = "---";      renk = QColor("white"); frenk = QColor("#212121")
            item = QListWidgetItem(f"[{badge}]  {tedarikci}: {aciklama}")
            item.setBackground(renk)
            item.setForeground(frenk)
            self.kalem_liste.addItem(item)

    def _eslestir_btn_guncelle(self):
        hazir = bool(self._kalemler) and bool(self._stoklar)
        self.eslestir_btn.setEnabled(hazir)
        self.eslestir_btn.setStyleSheet(_BTN_MAVI if hazir else _BTN_PASIF)

    # ── Eşleştirme ────────────────────────────────────────────────────────────

    def _eslestir(self):
        if not self._kalemler:
            QMessageBox.warning(self, "Kalem Yok", "Once fatura kalemlerini yukleyin.")
            return
        if not self._stoklar:
            QMessageBox.warning(self, "Stok Yok",
                                "Once DB'ye baglanin ve stok kartlarini yukleyin.")
            return
        self.eslestir_btn.setEnabled(False)
        self.eslestir_btn.setText("  Eslestiriliyor…")
        self.durum_lbl.setText("Eslestirme calisiyor…")
        self.durum_lbl.setStyleSheet("color:#1565c0;font-size:11px;padding:4px;")
        self._eslestirme_thread = EslestirmeThread(self._kalemler, self._stoklar)
        self._eslestirme_thread.bitti.connect(self._eslestirme_tamam)
        self._eslestirme_thread.hata.connect(self._eslestirme_hatasi)
        self._eslestirme_thread.start()

    def _eslestirme_tamam(self, temiz_sonuclar: list, kirli_kalemler: list):
        self._temiz_sonuclar = temiz_sonuclar
        self._kirli_kalemler = kirli_kalemler
        self.eslestir_btn.setEnabled(True)
        self.eslestir_btn.setText("🔍  Eslestir")
        self._kalem_listesini_guncelle()
        self.metin_uret_btn.setEnabled(True)

        n_guclu = sum(
            1 for b in temiz_sonuclar
            if not b["operasyon"]
            and b["adaylar"] and b["adaylar"][0]["etiket"] == "GUCLU"
        )
        n_yok = sum(
            1 for b in temiz_sonuclar
            if not b["operasyon"]
            and (not b["adaylar"] or b["adaylar"][0]["etiket"] == "ESLEME YOK")
        )
        self.durum_lbl.setText(
            f"Bitti — temiz: {len(temiz_sonuclar)}, muhtelif: {len(kirli_kalemler)} | "
            f"Guclu: {n_guclu}, Kart yok: {n_yok}"
        )
        self.durum_lbl.setStyleSheet("color:#2e7d32;font-size:11px;padding:4px;")
        self.durum_guncelle.emit(
            f"Fatura Eslestir: {len(temiz_sonuclar)+len(kirli_kalemler)} kalem islendi"
        )

    def _eslestirme_hatasi(self, mesaj: str):
        self.eslestir_btn.setEnabled(True)
        self.eslestir_btn.setText("🔍  Eslestir")
        self.durum_lbl.setText("Eslestirme hatasi.")
        self.durum_lbl.setStyleSheet("color:#c62828;font-size:11px;padding:4px;")
        QMessageBox.critical(self, "Eslestirme Hatasi",
                             f"Eslestirme yapilamadi:\n\n{mesaj}")

    def _kalem_listesini_guncelle(self):
        """Eşleştirme sonuçlarına göre kalem listesi badge'lerini günceller."""
        temiz_by_id = {id(b["kalem"]): b for b in self._temiz_sonuclar}
        kirli_ids   = {id(k) for k in self._kirli_kalemler}

        for i, kalem in enumerate(self._kalemler):
            item    = self.kalem_liste.item(i)
            kid     = id(kalem)
            aciklama  = kalem.get("aciklama", "")
            tedarikci = kalem.get("tedarikci", "")

            if kid in kirli_ids:
                badge = "MUHTELIF"; renk = _RENK_MUHTELIF; frenk = QColor("#616161")
            elif kid in temiz_by_id:
                blok = temiz_by_id[kid]
                if blok["operasyon"]:
                    badge = "ISCILK"; renk = _RENK_ISCILIK; frenk = QColor("#1565c0")
                elif not blok["adaylar"] or blok["adaylar"][0]["etiket"] == "ESLEME YOK":
                    badge = "KART YOK"; renk = _RENK_YOK; frenk = QColor("#b71c1c")
                elif blok["adaylar"][0]["etiket"] == "GOZDEN GECIR":
                    badge = "GOZDEN GECIR"; renk = _RENK_GOZDEN; frenk = QColor("#e65100")
                else:
                    badge = "GUCLU"; renk = _RENK_GUCLU; frenk = QColor("#1b5e20")
            else:
                badge = "---"; renk = QColor("white"); frenk = QColor("#212121")

            item.setText(f"[{badge}]  {tedarikci}: {aciklama}")
            item.setBackground(renk)
            item.setForeground(frenk)

    # ── Kalem seçimi → Öneriler paneli ────────────────────────────────────────

    def _kalem_secildi(self, row: int):
        if row < 0 or row >= len(self._kalemler):
            return
        kalem     = self._kalemler[row]
        aciklama  = kalem.get("aciklama", "")
        tedarikci = kalem.get("tedarikci", "")
        miktar    = kalem.get("miktar", "")
        birim     = kalem.get("birim", "")
        tutar     = float(kalem.get("tutar") or 0)

        self.oneri_baslik.setText(
            f"{tedarikci}:  {aciklama}  —  {miktar} {birim}  —  {tutar:,.2f} TL"
        )
        self.oneri_liste.clear()
        self.dag_tablo.setRowCount(0)
        self.dag_uyari_lbl.setText("")
        self._mevcut_kirli_kalem = None

        from tools.fatura_eslestir import kirli_neden
        kirli = kirli_neden(kalem)
        if kirli:
            it = QListWidgetItem(f"  ELLE DAGITIM GEREKIYOR — {kirli}")
            it.setBackground(_RENK_MUHTELIF)
            it.setForeground(QColor("#616161"))
            self.oneri_liste.addItem(it)
            self._dagitim_hazirla(kalem)
            return

        blok = self._blok_bul(kalem)
        if blok is None:
            msg = (
                "Eslestirme sonucu bulunamadi — yeniden eslestirin."
                if (self._temiz_sonuclar or self._kirli_kalemler)
                else "Eslestirme yapilmadi — 'Eslestir' butonuna basin."
            )
            self.oneri_liste.addItem(QListWidgetItem(msg))
            return

        if blok["operasyon"]:
            it = QListWidgetItem(
                "  ISCILK/OPERASYON — dogru mamul operasyonunu belirleyin"
            )
            it.setBackground(_RENK_ISCILIK)
            it.setForeground(QColor("#1565c0"))
            self.oneri_liste.addItem(it)
            if blok["adaylar"]:
                olasi = ", ".join(
                    f"{a['kodu']} (skor={a['skor']})" for a in blok["adaylar"]
                )
                it2 = QListWidgetItem(f"   Olasi:  {olasi}")
                it2.setForeground(QColor("#37474f"))
                self.oneri_liste.addItem(it2)
            return

        if not blok["adaylar"] or blok["adaylar"][0]["etiket"] == "ESLEME YOK":
            it = QListWidgetItem("  KART YOK — acilmasi gerekebilir")
            it.setBackground(_RENK_YOK)
            it.setForeground(QColor("#b71c1c"))
            self.oneri_liste.addItem(it)
            for a in blok["adaylar"]:
                it2 = QListWidgetItem(
                    f"   {a['kodu']:<18}  skor={a['skor']:5.1f}  [{a['etiket']}]  {a['adi']}"
                )
                it2.setForeground(QColor("#9e9e9e"))
                self.oneri_liste.addItem(it2)
            return

        for i, a in enumerate(blok["adaylar"]):
            if a["etiket"] == "GUCLU":
                renk = _RENK_GUCLU;  frenk = QColor("#1b5e20")
            elif a["etiket"] == "GOZDEN GECIR":
                renk = _RENK_GOZDEN; frenk = QColor("#e65100")
            else:
                renk = QColor("white"); frenk = QColor("#9e9e9e")
            prefix = ">>>" if i == 0 else "   "
            it = QListWidgetItem(
                f"{prefix}  {a['kodu']:<18}  skor={a['skor']:5.1f}"
                f"  [{a['etiket']}]  {a['adi']}"
            )
            it.setBackground(renk)
            it.setForeground(frenk)
            self.oneri_liste.addItem(it)

    def _blok_bul(self, kalem: dict):
        kid = id(kalem)
        for blok in self._temiz_sonuclar:
            if id(blok["kalem"]) == kid:
                return blok
        return None

    # ── Dağıtım ───────────────────────────────────────────────────────────────

    def _dagitim_hazirla(self, kalem: dict):
        self._mevcut_kirli_kalem = kalem
        self.dag_tablo.setRowCount(3)
        for r in range(3):
            self.dag_tablo.setItem(r, 0, QTableWidgetItem(""))
            self.dag_tablo.setItem(r, 1, QTableWidgetItem(""))
            self.dag_tablo.setItem(r, 2, QTableWidgetItem("1"))
            self.dag_tablo.setItem(r, 3, QTableWidgetItem("0.00"))

    def _dagitim_hesapla(self):
        kalem = self._mevcut_kirli_kalem
        if kalem is None:
            return
        toplam = float(kalem.get("tutar") or 0)
        if toplam <= 0:
            self.dag_uyari_lbl.setText("Kalem tutari gecersiz.")
            return

        secili = self._dag_btn_grp.checkedButton()
        yontem = secili.property("yontem") if secili else "esit"

        kalemler = []
        for r in range(self.dag_tablo.rowCount()):
            kodu = (self.dag_tablo.item(r, 0) or QTableWidgetItem("")).text().strip()
            if not kodu:
                continue
            aciklama = (self.dag_tablo.item(r, 1) or QTableWidgetItem("")).text().strip()
            baz_txt  = (self.dag_tablo.item(r, 2) or QTableWidgetItem("1")).text().strip()
            tur_txt  = (self.dag_tablo.item(r, 3) or QTableWidgetItem("0")).text().strip()
            try:
                baz = float(baz_txt.replace(",", "."))
            except ValueError:
                baz = 1.0
            try:
                tur = float(tur_txt.replace(",", "."))
            except ValueError:
                tur = 0.0
            kalemler.append({
                "stok_kodu": kodu, "aciklama": aciklama,
                "agirlik": baz, "miktar": baz, "tutar": tur,
            })

        if not kalemler:
            self.dag_uyari_lbl.setText("En az bir Stok Kodu girilmeli.")
            return

        from tools.fatura_eslestir import dagitim_hesapla, elle_dogrula
        try:
            sonuclar = dagitim_hesapla(toplam, kalemler, yontem)
        except ValueError as exc:
            self.dag_uyari_lbl.setText(str(exc))
            self.dag_uyari_lbl.setStyleSheet("color:#c62828;font-size:11px;padding:2px;")
            return

        uyari = elle_dogrula(toplam, sonuclar) if yontem == "elle" else None
        if uyari:
            self.dag_uyari_lbl.setText(f"Uyari: {uyari}")
            self.dag_uyari_lbl.setStyleSheet("color:#c62828;font-size:11px;padding:2px;")
        else:
            toplam_gosterim = round(sum(k["tutar"] for k in sonuclar), 2)
            self.dag_uyari_lbl.setText(
                f"Toplam: {toplam_gosterim:,.2f} TL = {toplam:,.2f} TL  [OK]"
            )
            self.dag_uyari_lbl.setStyleSheet("color:#2e7d32;font-size:11px;padding:2px;")

        row_idx = 0
        for r in range(self.dag_tablo.rowCount()):
            kodu = (self.dag_tablo.item(r, 0) or QTableWidgetItem("")).text().strip()
            if not kodu:
                continue
            if row_idx < len(sonuclar):
                self.dag_tablo.setItem(
                    r, 3, QTableWidgetItem(f"{sonuclar[row_idx]['tutar']:,.2f}")
                )
            row_idx += 1

    # ── Metin üretimi ──────────────────────────────────────────────────────────

    def _metin_uret(self):
        if not (self._temiz_sonuclar or self._kirli_kalemler):
            QMessageBox.warning(self, "Sonuc Yok", "Once eslestirme yapin.")
            return
        from tools.fatura_eslestir import metin_blogu_olustur
        try:
            metin = metin_blogu_olustur(self._temiz_sonuclar, self._kirli_kalemler)
        except Exception as exc:
            QMessageBox.critical(self, "Metin Uretme Hatasi", str(exc))
            return
        self.metin_alan.setPlainText(metin)
        self.kopyala_btn.setEnabled(True)
        self.kopyala_btn.setStyleSheet(_BTN_MAVI)
        self.kaydet_btn.setEnabled(True)
        self.kaydet_btn.setStyleSheet(_BTN_MAVI)
        self.durum_guncelle.emit("Fatura Eslestir: satinalma notu uretildi")

    def _kopyala(self):
        metin = self.metin_alan.toPlainText()
        if metin:
            QApplication.clipboard().setText(metin)
            self.durum_guncelle.emit("Fatura Eslestir: metin panoya kopyalandi")

    def _dosyaya_kaydet(self):
        metin = self.metin_alan.toPlainText()
        if not metin:
            return
        dosya, _ = QFileDialog.getSaveFileName(
            self, "Satinalma Notu Kaydet",
            str(BASE / "tools" / "satinalma_notu.txt"),
            "Metin Dosyasi (*.txt)",
        )
        if dosya:
            try:
                with open(dosya, "w", encoding="utf-8") as f:
                    f.write(metin)
                self.durum_guncelle.emit(f"Fatura Eslestir: {dosya} kaydedildi")
            except Exception as exc:
                QMessageBox.critical(self, "Kaydetme Hatasi", str(exc))
