import json
import logging
import os
from datetime import datetime, date as bugun_tipi
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QGridLayout,
    QLineEdit, QPushButton, QRadioButton, QButtonGroup,
    QDoubleSpinBox, QScrollArea, QFrame, QCheckBox, QSizePolicy,
    QMessageBox, QFileDialog, QProgressBar, QInputDialog, QCompleter,
    QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QEvent, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import (
    bom_listesi, proje_kodlari_listele,
    uretim_emri_masraf_maliyet_onizle,
    uretim_emri_masraf_maliyet_uygula,
)
from logic.excel import (
    maliyet_excel_kaydet, maliyet_excel_kaydet_excel_bom,
    proje_fark_excel_kaydet, proje_fark_excel_bom_kaydet,
)
from ui.stil import etiket, buton, ayrac

_BTN_AKTIF = (
    "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2e7d32,stop:1 #43a047);"
    "color:white;border-radius:6px;padding:9px 20px;font-weight:bold;font-size:13px;"
)
_BTN_PASIF = (
    "background:#bdbdbd;color:#757575;"
    "border-radius:6px;padding:9px 20px;font-weight:bold;font-size:13px;"
)
_BTN_EXCEL_AKTIF = (
    "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6a1b9a,stop:1 #8e24aa);"
    "color:white;border-radius:6px;padding:8px 16px;font-weight:bold;font-size:12px;"
)


# ── Bağlantı & BOM Yükleme Thread'i ─────────────────────────────────────────

class BomYuklemeThread(QThread):
    bitti = pyqtSignal(object, dict)   # (conn, bom_dict)
    hata  = pyqtSignal(str)

    def __init__(self, sunucu, veritabani, kullanici, sifre):
        super().__init__()
        self.sunucu     = sunucu
        self.veritabani = veritabani
        self.kullanici  = kullanici
        self.sifre      = sifre

    def run(self):
        try:
            conn = get_connection(self.sunucu, self.veritabani,
                                  self.kullanici, self.sifre)
            bom  = bom_listesi(conn)
            self.bitti.emit(conn, bom)
        except Exception as e:
            logging.error("BomYuklemeThread hatasi: %s", e)
            self.hata.emit(str(e))


# ── Hesaplama Thread'i ────────────────────────────────────────────────────────

class MaliyetHesaplamaThread(QThread):
    """
    Excel üretimini ve maliyet hesabını arka planda çalıştırır;
    ana thread (UI) bloke olmaz.

    Sinyaller
    ---------
    ilerleme(str) : her mamül işlenmeye başlarken yayımlanır
    bitti(str)    : başarı — kaydedilen dosya yolu
    hata(str)     : hata — hata mesajı
    """
    ilerleme = pyqtSignal(str)
    bitti    = pyqtSignal(str)
    hata     = pyqtSignal(str)

    def __init__(self, dosya: str, conn, secili_data: list[tuple[str, float]],
                 metod: str, bas: str, bit: str, bas_g: str, bit_g: str):
        super().__init__()
        self.dosya       = dosya
        self.conn        = conn
        self.secili_data = secili_data   # [(mamul_kodu, iscilik_float), ...]
        self.metod       = metod
        self.bas, self.bit, self.bas_g, self.bit_g = bas, bit, bas_g, bit_g

    def run(self):
        try:
            maliyet_excel_kaydet(
                self.dosya, self.conn, self.secili_data,
                self.metod, self.bas, self.bit, self.bas_g, self.bit_g,
                ilerleme_cb=self.ilerleme.emit,
            )
            self.bitti.emit(self.dosya)
        except Exception as e:
            logging.error("MaliyetHesaplamaThread hatasi: %s", e)
            self.hata.emit(str(e))


# ── Proje Fiili Satınalma Fark Raporu Thread'i ───────────────────────────────

class ProjeFarkThread(QThread):
    """
    Seçilen mamül(ler)in teorik BOM maliyetini, verilen proje koduna fiilen
    kesilmiş alış faturalarıyla karşılaştırıp Excel'e döker. Aynı sinyal
    deseni: ilerleme(str) / bitti(str, float, float) / hata(str).
    """
    ilerleme = pyqtSignal(str)
    bitti    = pyqtSignal(str, float, float)   # (dosya, teorik_toplam, fiili_toplam)
    hata     = pyqtSignal(str)

    def __init__(self, dosya: str, conn, secili_mamul_kodlari: list[str],
                 proje_kodu: str, metod: str, bas: str, bit: str,
                 bas_g: str, bit_g: str):
        super().__init__()
        self.dosya                = dosya
        self.conn                 = conn
        self.secili_mamul_kodlari = secili_mamul_kodlari
        self.proje_kodu           = proje_kodu
        self.metod                = metod
        self.bas, self.bit, self.bas_g, self.bit_g = bas, bit, bas_g, bit_g

    def run(self):
        try:
            teorik, fiili = proje_fark_excel_kaydet(
                self.dosya, self.conn, self.secili_mamul_kodlari, self.proje_kodu,
                self.metod, self.bas, self.bit, self.bas_g, self.bit_g,
                ilerleme_cb=self.ilerleme.emit,
            )
            self.bitti.emit(self.dosya, teorik, fiili)
        except Exception as e:
            logging.error("ProjeFarkThread hatasi: %s", e)
            self.hata.emit(str(e))


# ── Proje Fiili Satınalma Fark Raporu (Excel Taslak BOM) Thread'i ───────────

class ProjeFarkExcelBomThread(QThread):
    """
    CEO ERP'ye henüz işlenmemiş, Excel'de hazırlanmış taslak bir mamül ağacının
    teorik maliyetini bir proje koduna fiilen kesilmiş alış faturalarıyla
    karşılaştırıp Excel'e döker. Sinyal deseni: ilerleme(str) /
    bitti(str, float, float, list) / hata(str).
    """
    ilerleme = pyqtSignal(str)
    bitti    = pyqtSignal(str, float, float, list)   # (dosya, teorik, fiili, uyarilar)
    hata     = pyqtSignal(str)

    def __init__(self, dosya: str, conn, excel_bom_dosyasi: str, proje_kodu: str,
                 metod: str, bas: str, bit: str, bas_g: str, bit_g: str):
        super().__init__()
        self.dosya              = dosya
        self.conn                = conn
        self.excel_bom_dosyasi   = excel_bom_dosyasi
        self.proje_kodu          = proje_kodu
        self.metod               = metod
        self.bas, self.bit, self.bas_g, self.bit_g = bas, bit, bas_g, bit_g

    def run(self):
        try:
            teorik, fiili, uyarilar = proje_fark_excel_bom_kaydet(
                self.dosya, self.conn, self.excel_bom_dosyasi, self.proje_kodu,
                self.metod, self.bas, self.bit, self.bas_g, self.bit_g,
                ilerleme_cb=self.ilerleme.emit,
            )
            self.bitti.emit(self.dosya, teorik, fiili, uyarilar)
        except Exception as e:
            logging.error("ProjeFarkExcelBomThread hatasi: %s", e)
            self.hata.emit(str(e))


# ── Excel Taslak BOM Hesaplama Thread'i ──────────────────────────────────────

class ExcelBomMaliyetThread(QThread):
    """
    CEO ERP'ye henüz işlenmemiş, Excel'de hazırlanmış taslak bir mamül ağacını
    hesaplar. MaliyetHesaplamaThread ile aynı sinyal deseni.

    Sinyaller
    ---------
    ilerleme(str)      : her mamül işlenmeye başlarken yayımlanır
    bitti(str, list)   : başarı — (kaydedilen dosya yolu, uyarılar listesi)
    hata(str)          : hata — hata mesajı
    """
    ilerleme = pyqtSignal(str)
    bitti    = pyqtSignal(str, list)
    hata     = pyqtSignal(str)

    def __init__(self, dosya_cikti: str, conn, excel_bom_dosyasi: str,
                 metod: str, bas: str, bit: str, bas_g: str, bit_g: str,
                 iscilik: float):
        super().__init__()
        self.dosya_cikti       = dosya_cikti
        self.conn              = conn
        self.excel_bom_dosyasi = excel_bom_dosyasi
        self.metod              = metod
        self.bas, self.bit, self.bas_g, self.bit_g = bas, bit, bas_g, bit_g
        self.iscilik            = iscilik

    def run(self):
        try:
            uyarilar = maliyet_excel_kaydet_excel_bom(
                self.dosya_cikti, self.conn, self.excel_bom_dosyasi,
                self.metod, self.bas, self.bit, self.bas_g, self.bit_g,
                iscilik=self.iscilik, ilerleme_cb=self.ilerleme.emit,
            )
            self.bitti.emit(self.dosya_cikti, uyarilar)
        except Exception as e:
            logging.error("ExcelBomMaliyetThread hatasi: %s", e)
            self.hata.emit(str(e))


# ── Üretim emri masraf maliyeti ──────────────────────────────────────────────

def _masraf_maliyet_yedekle(veri: dict) -> Path:
    """Uygulama öncesi masraf ön izlemesini kullanıcı verisine yedekler."""
    kok = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    klasor = kok / "CEO ERP Araclar" / "yedekler"
    klasor.mkdir(parents=True, exist_ok=True)
    kod = (
        veri["emir"]["kodu"]
        .replace("\\", "_")
        .replace("/", "_")
        .replace(":", "_")
    )
    yol = klasor / (
        f"masraf_maliyet_yedek_{kod}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    icerik = {
        "olusturma": datetime.now().isoformat(timespec="seconds"),
        "emir": veri["emir"],
        "satirlar": veri["satirlar"],
    }
    yol.write_text(json.dumps(icerik, ensure_ascii=False, indent=2), encoding="utf-8")
    return yol


class UretimMasrafMaliyetThread(QThread):
    """Üretim emri masraf maliyeti ön izleme/uygulama iş parçacığı."""

    bitti = pyqtSignal(object)
    hata = pyqtSignal(str)

    def __init__(self, conn, emir_kodu: str, uygula: bool = False):
        super().__init__()
        self.conn = conn
        self.emir_kodu = emir_kodu
        self.uygula = uygula

    def run(self):
        try:
            if not self.uygula:
                self.bitti.emit(
                    uretim_emri_masraf_maliyet_onizle(self.conn, self.emir_kodu)
                )
                return

            onizleme = uretim_emri_masraf_maliyet_onizle(self.conn, self.emir_kodu)
            uygun = [
                satir for satir in onizleme["satirlar"]
                if satir["durum"] == "uygulanabilir"
            ]
            yedek = str(_masraf_maliyet_yedekle(onizleme)) if uygun else None
            sonuc = uretim_emri_masraf_maliyet_uygula(self.conn, self.emir_kodu)
            sonuc["yedek"] = yedek
            self.bitti.emit(sonuc)
        except Exception as e:
            logging.error("Üretim emri masraf maliyet işlemi hatası: %s", e)
            self.hata.emit(str(e))


class UretimMasrafMaliyetDialog(QDialog):
    """Masraf maliyetlerini uygulamadan önce satır bazında gösterir."""

    uygula_istendi = pyqtSignal()

    def __init__(self, veri: dict, parent=None):
        super().__init__(parent)
        self.veri = veri
        self.setWindowTitle("Üretim Emri Masraf Maliyetleri")
        self.resize(940, 470)
        self._kur()

    @staticmethod
    def _sayi(deger, ondalik=6):
        return "-" if deger is None else f"{deger:,.{ondalik}f}"

    def _kur(self):
        ana = QVBoxLayout(self)
        bilgi = self.veri["emir"]
        baslik = QLabel(
            f"{bilgi['kodu']}  —  {bilgi['aciklama']}\n"
            f"Üretim emri tarihi: {bilgi['tarih']} | "
            "Fiyat kaynağı: bu tarihe kadar olan son masraf alış hareketi"
        )
        baslik.setStyleSheet("color:#37474f;font-size:12px;padding:4px;")
        baslik.setWordWrap(True)
        ana.addWidget(baslik)

        self.tablo = QTableWidget(0, 7)
        self.tablo.setHorizontalHeaderLabels([
            "Masraf Kodu", "İhtiyaç", "Mevcut Tutar", "Son Alış Tarihi",
            "Birim Fiyat", "Yeni Tutar", "Durum",
        ])
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.verticalHeader().setVisible(False)
        basliklar = self.tablo.horizontalHeader()
        basliklar.setSectionResizeMode(0, QHeaderView.Stretch)
        basliklar.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        basliklar.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        basliklar.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        basliklar.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        basliklar.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        basliklar.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        uygulanabilir = 0
        toplam = 0.0
        for satir in self.veri["satirlar"]:
            row = self.tablo.rowCount()
            self.tablo.insertRow(row)
            degerler = [
                f"{satir['kod']} — {satir['ad']}",
                self._sayi(satir["talep_miktari"]),
                self._sayi(satir["eski_tutar"]),
                satir["kaynak_tarihi"] or "-",
                self._sayi(satir["birim_fiyat"]),
                self._sayi(satir["yeni_tutar"]),
                {
                    "uygulanabilir": "Uygulanacak",
                    "fiyat_yok": "Fiyat bulunamadı — değiştirilmez",
                    "zaten_dolu": "Zaten dolu — değiştirilmez",
                }.get(satir["durum"], satir["durum"]),
            ]
            for col, deger in enumerate(degerler):
                self.tablo.setItem(row, col, QTableWidgetItem(str(deger)))
            if satir["durum"] == "uygulanabilir":
                uygulanabilir += 1
                toplam += satir["yeni_tutar"] or 0.0
        ana.addWidget(self.tablo, stretch=1)

        self.durum = QLabel(
            f"{uygulanabilir} satır uygulanabilir | "
            f"Yeni toplam: {toplam:,.6f} ₺"
        )
        self.durum.setStyleSheet("color:#455a64;font-size:11px;padding:4px;")
        ana.addWidget(self.durum)

        butonlar = QHBoxLayout()
        butonlar.addStretch()
        self.uygula_btn = QPushButton(
            f"💾  Fiyatı bulunanları uygula ({uygulanabilir})"
        )
        self.uygula_btn.setEnabled(uygulanabilir > 0)
        self.uygula_btn.setStyleSheet(_BTN_AKTIF if uygulanabilir else _BTN_PASIF)
        self.uygula_btn.clicked.connect(self.uygula_istendi.emit)
        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.reject)
        butonlar.addWidget(self.uygula_btn)
        butonlar.addWidget(kapat)
        ana.addLayout(butonlar)

    def uygulama_basladi(self):
        self.uygula_btn.setEnabled(False)
        self.uygula_btn.setText("⏳  Uygulanıyor…")
        self.durum.setText("Masraf tutarları üretim emrine yazılıyor…")


# ── Maliyet Sayfası ───────────────────────────────────────────────────────────

class MaliyetSayfasi(QWidget):
    def __init__(self):
        super().__init__()
        self.conn = None
        self._mamul_satirlari: dict[str, tuple] = {}
        self._thread: MaliyetHesaplamaThread | None = None
        self._excel_thread: ExcelBomMaliyetThread | None = None
        self._proje_fark_thread: ProjeFarkThread | None = None
        self._proje_fark_excel_thread: ProjeFarkExcelBomThread | None = None
        self._masraf_maliyet_thread: UretimMasrafMaliyetThread | None = None
        self._masraf_maliyet_dialog: UretimMasrafMaliyetDialog | None = None
        self._spinner_timer: QTimer | None = None
        self._spinner_sayac = 0
        self._kur()

    def _kur(self):
        ana = QHBoxLayout(self)
        ana.setContentsMargins(16, 12, 16, 12)
        ana.setSpacing(16)
        ana.addWidget(self._sol_panel(), stretch=4)
        ana.addWidget(self._sag_panel(), stretch=5)

    def _sol_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        bas = QLabel("Maliyet Hesaplama")
        bas.setFont(QFont("Segoe UI", 13, QFont.Bold))
        bas.setStyleSheet("color:#1a237e;")
        lay.addWidget(bas)

        # Veritabanı
        db_grup = QGroupBox("Veritabanı Bağlantısı")
        dg = QGridLayout(db_grup)
        dg.setSpacing(8)
        self.m_sunucu    = QLineEdit(DB_DEFAULTS["sunucu"])
        self.m_db        = QLineEdit(DB_DEFAULTS["veritabani"])
        self.m_kullanici = QLineEdit(DB_DEFAULTS["kullanici"])
        self.m_sifre     = QLineEdit(DB_DEFAULTS.get("sifre", ""))
        self.m_sifre.setEchoMode(QLineEdit.Password)
        self.m_sifre.setPlaceholderText("••••••••")
        for i, (k, v) in enumerate([("Sunucu:", self.m_sunucu), ("Veritabanı:", self.m_db),
                                     ("Kullanıcı:", self.m_kullanici), ("Şifre:", self.m_sifre)]):
            dg.addWidget(etiket(k), i, 0)
            dg.addWidget(v, i, 1)
        lay.addWidget(db_grup)

        # Bağlan butonu
        self.baglan_btn = QPushButton("🔌  Bağlan ve Mamülleri Yükle")
        self.baglan_btn.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1565c0,stop:1 #1976d2);"
            "color:white;border-radius:6px;padding:8px 16px;font-weight:bold;font-size:12px;"
        )
        self.baglan_btn.clicked.connect(self._baglan)
        lay.addWidget(self.baglan_btn)

        # Tarih aralığı
        tarih_grup = QGroupBox("Tarih Aralığı")
        tg = QGridLayout(tarih_grup)
        tg.setSpacing(8)
        self.tarih_bas = QLineEdit()
        self.tarih_bas.setPlaceholderText("GG.AA.YYYY")
        self.tarih_bit = QLineEdit()
        self.tarih_bit.setPlaceholderText("GG.AA.YYYY")
        hint = QLabel("Geçersiz veya gelecek tarih girilirse kutu temizlenir.  "
                      "Bitiş kutusunda Ctrl+N → bugün.")
        hint.setStyleSheet("color:#9e9e9e;font-size:10px;")
        hint.setWordWrap(True)
        tg.addWidget(etiket("Başlangıç:"), 0, 0)
        tg.addWidget(self.tarih_bas,       0, 1)
        tg.addWidget(etiket("Bitiş:"),     1, 0)
        tg.addWidget(self.tarih_bit,       1, 1)
        tg.addWidget(hint,                 2, 0, 1, 2)
        self.tarih_bas.editingFinished.connect(self._bas_validate)
        self.tarih_bit.editingFinished.connect(self._bit_validate)
        self.tarih_bit.installEventFilter(self)
        lay.addWidget(tarih_grup)

        # Maliyet yöntemi
        yontem_grup = QGroupBox("Maliyet Yöntemi")
        yg = QVBoxLayout(yontem_grup)
        self.metod_grup = QButtonGroup(self)
        for metin, deger_m in [("Ağırlıklı Ortalama", "WA"),
                                ("FIFO (İlk Giren İlk Çıkar)", "FIFO"),
                                ("LIFO (Son Giren İlk Çıkar)", "LIFO")]:
            rb = QRadioButton(metin)
            rb.setProperty("metod", deger_m)
            if deger_m == "WA":
                rb.setChecked(True)
            self.metod_grup.addButton(rb)
            yg.addWidget(rb)
        lay.addWidget(yontem_grup)

        # Proje fiili satınalma karşılaştırması
        proje_grup = QGroupBox("Proje Fiili Satınalma Karşılaştırması")
        pg = QVBoxLayout(proje_grup)
        pg.setSpacing(8)
        self.proje_kodu_kutusu = QLineEdit()
        self.proje_kodu_kutusu.setPlaceholderText("Proje Kodu (CEO ERP)")
        pg.addWidget(self.proje_kodu_kutusu)
        proje_hint = QLabel(
            "Soldaki mamül listesinden karşılaştırılacak mamül(ler)i işaretleyin "
            "(1 birim üretim varsayılır). Teorik BOM maliyeti ile bu proje "
            "koduna kesilmiş alış faturaları kalem bazında karşılaştırılıp "
            "Excel'e dökülür."
        )
        proje_hint.setStyleSheet("color:#9e9e9e;font-size:10px;")
        proje_hint.setWordWrap(True)
        pg.addWidget(proje_hint)
        self.proje_fark_btn = QPushButton("📊  Proje Fark Raporu (Excel)")
        self.proje_fark_btn.setStyleSheet(_BTN_EXCEL_AKTIF)
        self.proje_fark_btn.setToolTip(
            "Soldaki mamül listesinden CEO ERP'ye zaten işlenmiş (reçetesi "
            "yüklü) mamülleri seçip karşılaştırır."
        )
        self.proje_fark_btn.clicked.connect(self._proje_fark_hesapla)
        pg.addWidget(self.proje_fark_btn)

        self.proje_fark_excel_btn = QPushButton("📄  Excel BOM ile Fark Raporu")
        self.proje_fark_excel_btn.setStyleSheet(_BTN_EXCEL_AKTIF)
        self.proje_fark_excel_btn.setToolTip(
            "CEO ERP'ye henüz işlenmemiş, Excel'de hazırlanmış taslak bir "
            "mamül ağacı seçip aynı proje koduyla karşılaştırır."
        )
        self.proje_fark_excel_btn.clicked.connect(self._proje_fark_excelden_hesapla)
        pg.addWidget(self.proje_fark_excel_btn)

        lay.addWidget(proje_grup)

        # Üretim emri masraf maliyetleri
        masraf_grup = QGroupBox("Üretim Emri Masraf Maliyetleri")
        masraf_lay = QVBoxLayout(masraf_grup)
        masraf_lay.setSpacing(8)
        self.masraf_emir_kodu = QLineEdit()
        self.masraf_emir_kodu.setPlaceholderText("Üretim emri kodu (örn. ŞİRKET.1862026-8)")
        masraf_lay.addWidget(self.masraf_emir_kodu)
        masraf_hint = QLabel(
            "Masraf kartlarının üretim emri tarihine kadar bulunan son alış fiyatlarını "
            "ön izleyip, fiyatı bulunan ve mevcut tutarı sıfır olan satırlara aktarır."
        )
        masraf_hint.setStyleSheet("color:#9e9e9e;font-size:10px;")
        masraf_hint.setWordWrap(True)
        masraf_lay.addWidget(masraf_hint)
        self.masraf_maliyet_btn = QPushButton("🔧  Üretim Emri Masraflarını Doldur")
        self.masraf_maliyet_btn.setStyleSheet(_BTN_EXCEL_AKTIF)
        self.masraf_maliyet_btn.setToolTip(
            "Masraf maliyetlerini satır bazında ön izler; onaydan sonra yalnızca "
            "üretim emri Tutar alanlarını günceller."
        )
        self.masraf_maliyet_btn.clicked.connect(self._masraf_maliyet_hesapla)
        masraf_lay.addWidget(self.masraf_maliyet_btn)
        lay.addWidget(masraf_grup)

        lay.addStretch()

        self.excelden_hesapla_btn = QPushButton("📄  Excel'den Maliyet Hesapla")
        self.excelden_hesapla_btn.setStyleSheet(_BTN_EXCEL_AKTIF)
        self.excelden_hesapla_btn.setToolTip(
            "CEO ERP'ye henüz işlenmemiş, Excel'de hazırlanmış taslak bir mamül "
            "ağacını (Stok Kodu + Miktar listesi) seçip aynı yöntemle maliyetlendirir."
        )
        self.excelden_hesapla_btn.clicked.connect(self._excelden_hesapla)
        lay.addWidget(self.excelden_hesapla_btn)

        alt = QHBoxLayout()
        geri_btn = QPushButton("← Ana Menü")
        geri_btn.setStyleSheet("background:#eceff1;color:#37474f;border:1px solid #cfd8dc;"
                               "border-radius:6px;padding:7px 16px;font-weight:bold;")
        geri_btn.clicked.connect(lambda: self.window().sayfa_gec(0))
        self.hesapla_btn = QPushButton("📊  Hesapla ve Excel'e Aktar")
        self.hesapla_btn.setStyleSheet(_BTN_AKTIF)
        self.hesapla_btn.clicked.connect(self._hesapla)
        alt.addWidget(geri_btn)
        alt.addStretch()
        alt.addWidget(self.hesapla_btn)
        lay.addLayout(alt)
        return w

    def _sag_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        mamul_grup = QGroupBox("Mamüller ve İşçilik Tutarları")
        mg = QVBoxLayout(mamul_grup)

        # Arama çubuğu
        self.arama_kutusu = QLineEdit()
        self.arama_kutusu.setPlaceholderText("🔍  Kod veya ada göre filtrele…")
        self.arama_kutusu.setStyleSheet(
            "border:1px solid #c5cae9;border-radius:6px;padding:6px 10px;font-size:12px;"
            "background:white;"
        )
        self.arama_kutusu.textChanged.connect(self._filtrele)
        mg.addWidget(self.arama_kutusu)

        btn_satir = QHBoxLayout()
        tum_sec = QPushButton("Tümünü Seç")
        tum_sec.setStyleSheet("background:#e8eaf6;color:#3949ab;border-radius:5px;"
                              "padding:5px 12px;font-size:11px;font-weight:bold;")
        tum_kaldir = QPushButton("Tümünü Kaldır")
        tum_kaldir.setStyleSheet("background:#fce4ec;color:#c62828;border-radius:5px;"
                                 "padding:5px 12px;font-size:11px;font-weight:bold;")
        tum_sec.clicked.connect(lambda: self._tum_sec(True))
        tum_kaldir.clicked.connect(lambda: self._tum_sec(False))
        btn_satir.addWidget(tum_sec)
        btn_satir.addWidget(tum_kaldir)
        btn_satir.addStretch()
        mg.addLayout(btn_satir)

        baslik_satir = QHBoxLayout()
        baslik_satir.addWidget(QLabel(""), stretch=1)
        lbl_iscilik = QLabel("İşçilik (₺)")
        lbl_iscilik.setStyleSheet("color:#7986cb;font-weight:bold;font-size:11px;")
        lbl_iscilik.setFixedWidth(110)
        lbl_iscilik.setAlignment(Qt.AlignCenter)
        baslik_satir.addWidget(lbl_iscilik)
        mg.addLayout(baslik_satir)
        mg.addWidget(ayrac())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background:white;")
        self.mamul_layout = QVBoxLayout(scroll_widget)
        self.mamul_layout.setSpacing(4)
        self.mamul_layout.setContentsMargins(4, 4, 4, 4)
        self.mamul_layout.addStretch()
        scroll.setWidget(scroll_widget)
        mg.addWidget(scroll, stretch=1)

        lay.addWidget(mamul_grup, stretch=1)

        self.yukleme_bar = QProgressBar()
        self.yukleme_bar.setRange(0, 0)
        self.yukleme_bar.setFixedHeight(6)
        self.yukleme_bar.setTextVisible(False)
        self.yukleme_bar.setStyleSheet(
            "QProgressBar{background:#e8eaf6;border-radius:3px;border:none;}"
            "QProgressBar::chunk{background:#3f51b5;border-radius:3px;}"
        )
        self.yukleme_bar.setVisible(False)
        lay.addWidget(self.yukleme_bar)

        self.durum_lbl = QLabel("")
        self.durum_lbl.setStyleSheet("color:#555;font-size:11px;padding:4px;")
        self.durum_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.durum_lbl)
        return w

    # ── Kısayol & tarih doğrulama ────────────────────────────────────────────
    def eventFilter(self, obj, event):
        if (obj is self.tarih_bit
                and event.type() == QEvent.KeyPress
                and event.key() == Qt.Key_N
                and event.modifiers() == Qt.ControlModifier):
            self.tarih_bit.setText(bugun_tipi.today().strftime("%d.%m.%Y"))
            return True
        return super().eventFilter(obj, event)

    @staticmethod
    def _parse(metin: str):
        metin = metin.strip()
        if len(metin) == 8 and metin.isdigit():
            metin = f"{metin[:2]}.{metin[2:4]}.{metin[4:]}"
        try:
            dt = datetime.strptime(metin, "%d.%m.%Y").date()
            return None if dt > bugun_tipi.today() else dt
        except ValueError:
            return None

    def _bas_validate(self):
        dt = self._parse(self.tarih_bas.text())
        if dt is None:
            self.tarih_bas.clear()
            return
        self.tarih_bas.setText(dt.strftime("%d.%m.%Y"))
        bit_dt = self._parse(self.tarih_bit.text())
        if bit_dt is not None and dt > bit_dt:
            self.tarih_bit.setText(dt.strftime("%d.%m.%Y"))

    def _bit_validate(self):
        dt = self._parse(self.tarih_bit.text())
        if dt is None:
            self.tarih_bit.clear()
            return
        self.tarih_bit.setText(dt.strftime("%d.%m.%Y"))
        bas_dt = self._parse(self.tarih_bas.text())
        if bas_dt is not None and dt < bas_dt:
            self.tarih_bit.setText(bas_dt.strftime("%d.%m.%Y"))

    # ── Bağlantı ─────────────────────────────────────────────────────────────
    def _baglan(self):
        self.baglan_btn.setEnabled(False)
        self.baglan_btn.setText("⏳  Bağlanıyor…")
        self.yukleme_bar.setVisible(True)
        self.yukleme_bar.setRange(0, 0)   # belirsiz animasyon

        self._bom_thread = BomYuklemeThread(
            self.m_sunucu.text(), self.m_db.text(),
            self.m_kullanici.text(), self.m_sifre.text(),
        )
        self._bom_thread.bitti.connect(self._bom_yuklendi)
        self._bom_thread.hata.connect(self._bom_hatasi)
        self._bom_thread.start()

    def _bom_yuklendi(self, conn, bom: dict):
        self.yukleme_bar.setRange(0, len(bom))
        self.yukleme_bar.setValue(0)

        self.conn = conn
        self._mamul_satirlari.clear()
        while self.mamul_layout.count() > 1:
            item = self.mamul_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, (kod, veri) in enumerate(bom.items(), 1):
            self._mamul_satiri_ekle(kod, veri["ad"])
            self.yukleme_bar.setValue(i)

        self.yukleme_bar.setVisible(False)
        self.baglan_btn.setEnabled(True)
        self.baglan_btn.setText(f"✅  {len(self._mamul_satirlari)} mamül yüklendi")
        self.baglan_btn.setStyleSheet(
            "background:#2e7d32;color:white;border-radius:6px;"
            "padding:8px 16px;font-weight:bold;font-size:12px;"
        )

        # Proje kodu serbest metin olarak girildiğinden ufak bir yazım farkı
        # (ör. "ADLAS MKE" yerine gerçek kod "ADLAS-MKE") sessizce 0 satırla
        # sonuçlanabilir. Gerçek kodlardan otomatik tamamlama listesi kurar.
        try:
            proje_kodlari = proje_kodlari_listele(conn)
            tamamlayici = QCompleter(proje_kodlari, self.proje_kodu_kutusu)
            tamamlayici.setCaseSensitivity(Qt.CaseInsensitive)
            tamamlayici.setFilterMode(Qt.MatchContains)
            self.proje_kodu_kutusu.setCompleter(tamamlayici)
        except Exception as e:
            logging.warning("Proje kodlari listelenemedi (otomatik tamamlama devre disi): %s", e)

    def _bom_hatasi(self, mesaj: str):
        logging.error("Maliyet baglanti hatasi: %s", mesaj)
        self.yukleme_bar.setVisible(False)
        self.baglan_btn.setEnabled(True)
        self.baglan_btn.setText("🔌  Bağlan ve Mamülleri Yükle")
        QMessageBox.critical(self, "Bağlantı Hatası",
                             f"Veritabanına bağlanılamadı:\n\n{mesaj}")

    # ── Mamül listesi ────────────────────────────────────────────────────────
    def baslat(self, conn):
        """Dışarıdan bağlantı verildiğinde direkt yükler (test/programatik kullanım)."""
        bom = bom_listesi(conn)
        self._bom_yuklendi(conn, bom)

    def _mamul_satiri_ekle(self, kod: str, ad: str):
        satir = QFrame()
        satir.setStyleSheet("QFrame{background:white;border-radius:5px;}"
                            "QFrame:hover{background:#f5f5f5;}")
        satir_lay = QHBoxLayout(satir)
        satir_lay.setContentsMargins(4, 4, 4, 4)
        satir_lay.setSpacing(8)

        cb = QCheckBox(f"{kod}  —  {ad}")
        cb.setChecked(True)
        cb.setStyleSheet("font-size:12px;color:#212121;")
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        spin = QDoubleSpinBox()
        spin.setRange(0, 9_999_999)
        spin.setDecimals(2)
        spin.setSuffix(" ₺")
        spin.setValue(0.00)
        spin.setFixedWidth(110)
        spin.setAlignment(Qt.AlignRight)

        satir_lay.addWidget(cb, stretch=1)
        satir_lay.addWidget(spin)
        self.mamul_layout.insertWidget(self.mamul_layout.count() - 1, satir)
        self._mamul_satirlari[kod] = (cb, spin, satir, kod.lower(), ad.lower())

    def _filtrele(self, metin: str):
        metin = metin.strip().lower()
        for kod, (cb, spin, satir, kod_l, ad_l) in self._mamul_satirlari.items():
            eslesir = not metin or metin in kod_l or metin in ad_l
            satir.setVisible(eslesir)

    def _tum_sec(self, durum: bool):
        for cb, spin, satir, *_ in self._mamul_satirlari.values():
            if satir.isVisible():
                cb.setChecked(durum)

    def _secili_metod(self) -> str:
        for btn_w in self.metod_grup.buttons():
            if btn_w.isChecked():
                return btn_w.property("metod")
        return "WA"

    # ── Üretim emri masraf maliyeti akışı ────────────────────────────────────
    def _masraf_maliyet_hesapla(self):
        if self.conn is None:
            QMessageBox.warning(
                self, "Bağlantı Yok",
                "Önce 'Bağlan ve Mamülleri Yükle' butonuna basın.",
            )
            return

        emir_kodu = self.masraf_emir_kodu.text().strip()
        if not emir_kodu:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir üretim emri kodu girin.")
            return

        self.masraf_maliyet_btn.setEnabled(False)
        self.masraf_maliyet_btn.setStyleSheet(_BTN_PASIF)
        self.masraf_maliyet_btn.setText("⏳  Masraflar taranıyor…")
        self.durum_lbl.setText("Üretim emri masraf fiyatları sorgulanıyor…")
        self.durum_lbl.setStyleSheet("color:#1565c0;font-size:11px;padding:4px;")

        self._masraf_maliyet_thread = UretimMasrafMaliyetThread(
            self.conn, emir_kodu, uygula=False
        )
        self._masraf_maliyet_thread.bitti.connect(self._masraf_onizleme_bitti)
        self._masraf_maliyet_thread.hata.connect(self._masraf_maliyet_hatasi)
        self._masraf_maliyet_thread.start()

    def _masraf_butonunu_serbest_birak(self):
        self.masraf_maliyet_btn.setEnabled(True)
        self.masraf_maliyet_btn.setText("🔧  Üretim Emri Masraflarını Doldur")
        self.masraf_maliyet_btn.setStyleSheet(_BTN_EXCEL_AKTIF)

    def _masraf_onizleme_bitti(self, veri: dict):
        self._masraf_butonunu_serbest_birak()
        satirlar = veri.get("satirlar", [])
        if not satirlar:
            QMessageBox.information(
                self, "Masraf Satırı Yok",
                f"{veri['emir']['kodu']} üretim emrinde masraf satırı bulunamadı.",
            )
            return

        self._masraf_maliyet_dialog = UretimMasrafMaliyetDialog(veri, self)
        self._masraf_maliyet_dialog.uygula_istendi.connect(
            self._masraf_maliyet_uygula
        )
        self._masraf_maliyet_dialog.exec_()
        self._masraf_maliyet_dialog = None

    def _masraf_maliyet_uygula(self):
        dialog = self._masraf_maliyet_dialog
        if dialog is None:
            return
        cevap = QMessageBox.question(
            dialog,
            "Masraf Tutarlarını Uygula",
            "Fiyatı bulunan masraf satırlarının toplam tutarları üretim emrine yazılsın mı?\n\n"
            "Fatura, irsaliye ve stok hareketleri değiştirilmeyecek.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if cevap != QMessageBox.Yes:
            return

        dialog.uygulama_basladi()
        self.masraf_maliyet_btn.setEnabled(False)
        self.masraf_maliyet_btn.setStyleSheet(_BTN_PASIF)
        self._masraf_maliyet_thread = UretimMasrafMaliyetThread(
            self.conn, dialog.veri["emir"]["kodu"], uygula=True
        )
        self._masraf_maliyet_thread.bitti.connect(self._masraf_uygulama_bitti)
        self._masraf_maliyet_thread.hata.connect(self._masraf_maliyet_hatasi)
        self._masraf_maliyet_thread.start()

    def _masraf_uygulama_bitti(self, sonuc: dict):
        guncellenen = sonuc.get("guncellenen", [])
        atlanan = sonuc.get("atlanan", [])
        yedek = sonuc.get("yedek")
        if self._masraf_maliyet_dialog is not None:
            self._masraf_maliyet_dialog.accept()
        self._masraf_butonunu_serbest_birak()
        self.durum_lbl.setText(
            f"Masraf maliyeti uygulandı: {len(guncellenen)} satır güncellendi."
        )
        self.durum_lbl.setStyleSheet("color:#2e7d32;font-size:11px;padding:4px;")

        mesaj = f"{len(guncellenen)} masraf satırı üretim emrine yazıldı."
        if atlanan:
            mesaj += f"\n{len(atlanan)} satır başka bir işlem nedeniyle atlandı."
        if yedek:
            mesaj += f"\n\nYedek dosyası:\n{yedek}"
        QMessageBox.information(self, "Başarılı", mesaj)

    def _masraf_maliyet_hatasi(self, mesaj: str):
        self._masraf_butonunu_serbest_birak()
        if self._masraf_maliyet_dialog is not None:
            self._masraf_maliyet_dialog.uygula_btn.setEnabled(True)
            self._masraf_maliyet_dialog.uygula_btn.setText(
                "💾  Fiyatı bulunanları uygula"
            )
            self._masraf_maliyet_dialog.durum.setText(
                "İşlem başarısız oldu; değişiklik yapılmadı."
            )
        self.durum_lbl.setText("Masraf maliyeti işlemi başarısız.")
        self.durum_lbl.setStyleSheet("color:#c62828;font-size:11px;padding:4px;")
        QMessageBox.critical(self, "Hata", f"Masraf maliyeti işlemi başarısız:\n{mesaj}")

    # ── Hesaplama akışı ──────────────────────────────────────────────────────
    def _hesapla(self):
        if self.conn is None:
            QMessageBox.warning(self, "Bağlantı Yok",
                                "Önce 'Bağlan ve Mamülleri Yükle' butonuna basın.")
            return
        secili = [(kod, cb, spin)
                  for kod, (cb, spin, *_) in self._mamul_satirlari.items()
                  if cb.isChecked()]
        if not secili:
            QMessageBox.warning(self, "Uyarı", "Lütfen en az bir mamül seçin.")
            return

        dosya, _ = QFileDialog.getSaveFileName(
            self, "Excel Kaydet",
            f"ceo_erp_maliyet_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "Excel Dosyası (*.xlsx)")
        if not dosya:
            return

        bas_dt = self._parse(self.tarih_bas.text())
        bit_dt = self._parse(self.tarih_bit.text())
        if bas_dt is None or bit_dt is None:
            QMessageBox.warning(self, "Eksik Bilgi",
                                "Lütfen geçerli bir başlangıç ve bitiş tarihi girin.\n\n"
                                "Format: GG.AA.YYYY  (örn: 01.01.2025)")
            return

        metod = self._secili_metod()
        bas   = bas_dt.strftime("%Y-%m-%d")
        bit   = bit_dt.strftime("%Y-%m-%d")
        bas_g = bas_dt.strftime("%d.%m.%Y")
        bit_g = bit_dt.strftime("%d.%m.%Y")

        # Widget değerlerini thread başlamadan önce çıkar (thread-safe)
        secili_data: list[tuple[str, float]] = [
            (kod, spin.value()) for kod, cb, spin in secili
        ]

        self._ui_kilitle()
        self._thread = MaliyetHesaplamaThread(
            dosya, self.conn, secili_data, metod, bas, bit, bas_g, bit_g
        )
        self._thread.ilerleme.connect(self._ilerleme_guncelle)
        self._thread.bitti.connect(self._hesaplama_bitti)
        self._thread.hata.connect(self._hesaplama_hatasi)
        self._thread.finished.connect(self._ui_serbest_birak)
        self._thread.start()

    # ── Excel taslak BOM'dan hesaplama akışı ─────────────────────────────────
    def _excelden_hesapla(self):
        if self.conn is None:
            QMessageBox.warning(self, "Bağlantı Yok",
                                "Önce 'Bağlan ve Mamülleri Yükle' butonuna basın.")
            return

        kaynak, _ = QFileDialog.getOpenFileName(
            self, "Taslak Mamül Ağacı Excel'i Seç", "",
            "Excel Dosyası (*.xlsx *.xls)")
        if not kaynak:
            return

        bas_dt = self._parse(self.tarih_bas.text())
        bit_dt = self._parse(self.tarih_bit.text())
        if bas_dt is None or bit_dt is None:
            QMessageBox.warning(self, "Eksik Bilgi",
                                "Lütfen geçerli bir başlangıç ve bitiş tarihi girin.\n\n"
                                "Format: GG.AA.YYYY  (örn: 01.01.2025)")
            return

        iscilik, tamam = QInputDialog.getDouble(
            self, "İşçilik", "İşçilik tutarı (₺, opsiyonel):", 0.0, 0, 9_999_999, 2)
        if not tamam:
            return

        dosya, _ = QFileDialog.getSaveFileName(
            self, "Excel Kaydet",
            f"ceo_erp_maliyet_taslak_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "Excel Dosyası (*.xlsx)")
        if not dosya:
            return

        metod = self._secili_metod()
        bas   = bas_dt.strftime("%Y-%m-%d")
        bit   = bit_dt.strftime("%Y-%m-%d")
        bas_g = bas_dt.strftime("%d.%m.%Y")
        bit_g = bit_dt.strftime("%d.%m.%Y")

        self._ui_kilitle()
        self._excel_thread = ExcelBomMaliyetThread(
            dosya, self.conn, kaynak, metod, bas, bit, bas_g, bit_g, iscilik
        )
        self._excel_thread.ilerleme.connect(self._ilerleme_guncelle)
        self._excel_thread.bitti.connect(self._excel_hesaplama_bitti)
        self._excel_thread.hata.connect(self._hesaplama_hatasi)
        self._excel_thread.finished.connect(self._ui_serbest_birak)
        self._excel_thread.start()

    def _excel_hesaplama_bitti(self, dosya: str, uyarilar: list):
        self.durum_lbl.setText(f"Rapor olusturuldu: {dosya}")
        self.durum_lbl.setStyleSheet("color:#2e7d32;font-size:11px;padding:4px;")
        mesaj = f"Maliyet raporu kaydedildi:\n{dosya}"
        if uyarilar:
            ornekler = "\n".join(f"• {u}" for u in uyarilar[:10])
            fazla = f"\n… ve {len(uyarilar) - 10} uyarı daha" if len(uyarilar) > 10 else ""
            mesaj += f"\n\n⚠ {len(uyarilar)} uyarı:\n{ornekler}{fazla}"
        QMessageBox.information(self, "Basarili", mesaj)

    # ── Proje fiili satınalma fark raporu akışı ──────────────────────────────
    def _proje_fark_hesapla(self):
        if self.conn is None:
            QMessageBox.warning(self, "Bağlantı Yok",
                                "Önce 'Bağlan ve Mamülleri Yükle' butonuna basın.")
            return

        proje_kodu = self.proje_kodu_kutusu.text().strip()
        if not proje_kodu:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir Proje Kodu girin.")
            return

        secili_kodlar = [kod for kod, (cb, spin, *_) in self._mamul_satirlari.items()
                         if cb.isChecked()]
        if not secili_kodlar:
            QMessageBox.warning(self, "Uyarı",
                                "Lütfen karşılaştırılacak en az bir mamül seçin "
                                "(soldaki mamül listesinden işaretleyin).")
            return

        bas_dt = self._parse(self.tarih_bas.text())
        bit_dt = self._parse(self.tarih_bit.text())
        if bas_dt is None or bit_dt is None:
            QMessageBox.warning(self, "Eksik Bilgi",
                                "Lütfen geçerli bir başlangıç ve bitiş tarihi girin.\n\n"
                                "Format: GG.AA.YYYY  (örn: 01.01.2025)")
            return

        dosya, _ = QFileDialog.getSaveFileName(
            self, "Excel Kaydet",
            f"proje_fark_{proje_kodu}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "Excel Dosyası (*.xlsx)")
        if not dosya:
            return

        metod = self._secili_metod()
        bas   = bas_dt.strftime("%Y-%m-%d")
        bit   = bit_dt.strftime("%Y-%m-%d")
        bas_g = bas_dt.strftime("%d.%m.%Y")
        bit_g = bit_dt.strftime("%d.%m.%Y")

        self._ui_kilitle()
        self._proje_fark_thread = ProjeFarkThread(
            dosya, self.conn, secili_kodlar, proje_kodu, metod, bas, bit, bas_g, bit_g
        )
        self._proje_fark_thread.ilerleme.connect(self._ilerleme_guncelle)
        self._proje_fark_thread.bitti.connect(self._proje_fark_bitti)
        self._proje_fark_thread.hata.connect(self._hesaplama_hatasi)
        self._proje_fark_thread.finished.connect(self._ui_serbest_birak)
        self._proje_fark_thread.start()

    def _proje_fark_bitti(self, dosya: str, teorik: float, fiili: float):
        fark = fiili - teorik
        self.durum_lbl.setText(f"Proje fark raporu olusturuldu: {dosya}")
        self.durum_lbl.setStyleSheet("color:#2e7d32;font-size:11px;padding:4px;")
        mesaj = (
            f"Proje fark raporu kaydedildi:\n{dosya}\n\n"
            f"Teorik (BOM): {teorik:,.2f} ₺\n"
            f"Fiili (Satınalma): {fiili:,.2f} ₺\n"
            f"Fark: {fark:,.2f} ₺"
        )
        if fiili == 0.0:
            mesaj += (
                "\n\n⚠ Bu proje kodu için CEO ERP'de hiç satınalma hareketi "
                "bulunamadı. Proje kodunu kontrol edin — kutuya yazarken "
                "açılan otomatik tamamlama listesinden seçmeniz önerilir "
                "(ör. 'ADLAS MKE' değil, gerçek kod 'ADLAS-MKE' olabilir)."
            )
        QMessageBox.information(self, "Basarili", mesaj)

    # ── Proje fiili satınalma fark raporu akışı (Excel taslak BOM) ───────────
    def _proje_fark_excelden_hesapla(self):
        if self.conn is None:
            QMessageBox.warning(self, "Bağlantı Yok",
                                "Önce 'Bağlan ve Mamülleri Yükle' butonuna basın.")
            return

        proje_kodu = self.proje_kodu_kutusu.text().strip()
        if not proje_kodu:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir Proje Kodu girin.")
            return

        kaynak, _ = QFileDialog.getOpenFileName(
            self, "Taslak Mamül Ağacı Excel'i Seç", "",
            "Excel Dosyası (*.xlsx *.xls)")
        if not kaynak:
            return

        bas_dt = self._parse(self.tarih_bas.text())
        bit_dt = self._parse(self.tarih_bit.text())
        if bas_dt is None or bit_dt is None:
            QMessageBox.warning(self, "Eksik Bilgi",
                                "Lütfen geçerli bir başlangıç ve bitiş tarihi girin.\n\n"
                                "Format: GG.AA.YYYY  (örn: 01.01.2025)")
            return

        dosya, _ = QFileDialog.getSaveFileName(
            self, "Excel Kaydet",
            f"proje_fark_excelbom_{proje_kodu}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "Excel Dosyası (*.xlsx)")
        if not dosya:
            return

        metod = self._secili_metod()
        bas   = bas_dt.strftime("%Y-%m-%d")
        bit   = bit_dt.strftime("%Y-%m-%d")
        bas_g = bas_dt.strftime("%d.%m.%Y")
        bit_g = bit_dt.strftime("%d.%m.%Y")

        self._ui_kilitle()
        self._proje_fark_excel_thread = ProjeFarkExcelBomThread(
            dosya, self.conn, kaynak, proje_kodu, metod, bas, bit, bas_g, bit_g
        )
        self._proje_fark_excel_thread.ilerleme.connect(self._ilerleme_guncelle)
        self._proje_fark_excel_thread.bitti.connect(self._proje_fark_excelden_bitti)
        self._proje_fark_excel_thread.hata.connect(self._hesaplama_hatasi)
        self._proje_fark_excel_thread.finished.connect(self._ui_serbest_birak)
        self._proje_fark_excel_thread.start()

    def _proje_fark_excelden_bitti(self, dosya: str, teorik: float, fiili: float,
                                    uyarilar: list):
        fark = fiili - teorik
        self.durum_lbl.setText(f"Proje fark raporu olusturuldu: {dosya}")
        self.durum_lbl.setStyleSheet("color:#2e7d32;font-size:11px;padding:4px;")
        mesaj = (
            f"Proje fark raporu kaydedildi:\n{dosya}\n\n"
            f"Teorik (BOM): {teorik:,.2f} ₺\n"
            f"Fiili (Satınalma): {fiili:,.2f} ₺\n"
            f"Fark: {fark:,.2f} ₺"
        )
        if fiili == 0.0:
            mesaj += (
                "\n\n⚠ Bu proje kodu için CEO ERP'de hiç satınalma hareketi "
                "bulunamadı. Proje kodunu kontrol edin — kutuya yazarken "
                "açılan otomatik tamamlama listesinden seçmeniz önerilir."
            )
        if uyarilar:
            ornekler = "\n".join(f"• {u}" for u in uyarilar[:10])
            fazla = f"\n… ve {len(uyarilar) - 10} uyarı daha" if len(uyarilar) > 10 else ""
            mesaj += f"\n\n⚠ {len(uyarilar)} uyarı (rapordaki 'Uyarılar' sayfasına bakın):\n{ornekler}{fazla}"
        QMessageBox.information(self, "Basarili", mesaj)

    # ── UI durum yönetimi ────────────────────────────────────────────────────
    def _ui_kilitle(self):
        """Hesaplama süresince butonları devre dışı bırakır, spinner başlatır."""
        self.hesapla_btn.setEnabled(False)
        self.hesapla_btn.setStyleSheet(_BTN_PASIF)
        self.hesapla_btn.setText("⏳  Hesaplanıyor.")
        self.excelden_hesapla_btn.setEnabled(False)
        self.excelden_hesapla_btn.setStyleSheet(_BTN_PASIF)
        self.proje_fark_btn.setEnabled(False)
        self.proje_fark_btn.setStyleSheet(_BTN_PASIF)
        self.proje_fark_excel_btn.setEnabled(False)
        self.proje_fark_excel_btn.setStyleSheet(_BTN_PASIF)
        self.masraf_maliyet_btn.setEnabled(False)
        self.masraf_maliyet_btn.setStyleSheet(_BTN_PASIF)
        self.durum_lbl.setText("Hesaplama başlatıldı, lütfen bekleyin...")
        self.durum_lbl.setStyleSheet("color:#1565c0;font-size:11px;padding:4px;")
        self._spinner_sayac = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._spinner_adim)
        self._spinner_timer.start(400)

    def _spinner_adim(self):
        noktalar = "." * ((self._spinner_sayac % 3) + 1)
        self.hesapla_btn.setText(f"⏳  Hesaplanıyor{noktalar}")
        self._spinner_sayac += 1

    def _ilerleme_guncelle(self, mesaj: str):
        self.durum_lbl.setText(f"⚙  {mesaj}")

    def _ui_serbest_birak(self):
        """Thread bittikten sonra UI'ı normale döndürür."""
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer.deleteLater()
            self._spinner_timer = None
        self.hesapla_btn.setEnabled(True)
        self.hesapla_btn.setText("📊  Hesapla ve Excel'e Aktar")
        self.hesapla_btn.setStyleSheet(_BTN_AKTIF)
        self.excelden_hesapla_btn.setEnabled(True)
        self.excelden_hesapla_btn.setStyleSheet(_BTN_EXCEL_AKTIF)
        self.proje_fark_btn.setEnabled(True)
        self.proje_fark_btn.setStyleSheet(_BTN_EXCEL_AKTIF)
        self.proje_fark_excel_btn.setEnabled(True)
        self.proje_fark_excel_btn.setStyleSheet(_BTN_EXCEL_AKTIF)
        self._masraf_butonunu_serbest_birak()

    def _hesaplama_bitti(self, dosya: str):
        self.durum_lbl.setText(f"Rapor olusturuldu: {dosya}")
        self.durum_lbl.setStyleSheet("color:#2e7d32;font-size:11px;padding:4px;")
        QMessageBox.information(self, "Basarili", f"Maliyet raporu kaydedildi:\n{dosya}")

    def _hesaplama_hatasi(self, mesaj: str):
        self.durum_lbl.setText("Hesaplama basarisiz.")
        self.durum_lbl.setStyleSheet("color:#c62828;font-size:11px;padding:4px;")
        QMessageBox.critical(self, "Hata", f"Excel olusturulamadi:\n{mesaj}")
