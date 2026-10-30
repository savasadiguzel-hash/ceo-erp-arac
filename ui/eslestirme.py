"""Tarama sonuçlarını toplu olarak mevcut mamül reçetelerine bağlama ekranı."""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from PyQt5.QtCore import QEvent, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QProgressBar, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from db.sorgular import (
    kartlari_receteye_toplu_bagla, mamul_agaci_listesi, mamul_hat_planlari,
)
from logic.excel import eslestirme_listesi_excel_kaydet
from ui.stil import etiket


class SiraliHucre(QTableWidgetItem):
    """Sayı sütunlarını metin yerine sayısal değerle sıralar."""

    def __lt__(self, diger):
        sutun = self.column()
        if sutun == 0:
            return self.checkState() < diger.checkState()
        if sutun in (5, 6, 7, 8):
            def sayi(item):
                try:
                    deger = Decimal(item.text().strip().replace(",", "."))
                    return deger if deger.is_finite() else Decimal("-Infinity")
                except InvalidOperation:
                    return Decimal("-Infinity")
            return sayi(self) < sayi(diger)
        return self.text().casefold() < diger.text().casefold()


class TopluBaglamaThread(QThread):
    ilerleme = pyqtSignal(int, int)
    bitti = pyqtSignal(list)
    hata = pyqtSignal(str)

    def __init__(self, conn, kartlar, mamul_kodu, grup_id):
        super().__init__()
        self.conn = conn
        self.kartlar = kartlar
        self.mamul_kodu = mamul_kodu
        self.grup_id = grup_id

    def run(self):
        try:
            ids = kartlari_receteye_toplu_bagla(
                self.conn, self.kartlar, self.mamul_kodu, self.grup_id,
                lambda sira, toplam: self.ilerleme.emit(sira, toplam),
            )
            self.bitti.emit(ids)
        except Exception as exc:
            self.hata.emit(str(exc))


class EslestirmeSayfasi(QWidget):
    rapor_signal = pyqtSignal(list)
    geri_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.conn = None
        self.stoklar = []
        self.sonuclar = []
        self.secilen_mamul = None
        self._mamul_listesi_cache = []
        self._aktif_secim = []
        self._secim_itemleri = []
        self.worker = None
        self._kur()

    def _kur(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(12, 10, 12, 8)
        ana.setSpacing(8)
        ana.addWidget(self._ilerleme())

        bolucu = QSplitter(Qt.Horizontal)
        bolucu.addWidget(self._kart_paneli())
        bolucu.addWidget(self._mamul_paneli())
        bolucu.setSizes([700, 360])
        bolucu.setChildrenCollapsible(False)
        ana.addWidget(bolucu, 1)
        ana.addWidget(self._buton_bar())

    def _ilerleme(self):
        frame = QFrame()
        frame.setStyleSheet("background:white;border:1px solid #c5cae9;border-radius:7px;")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(12, 7, 12, 7)
        self.ilerleme_lbl = QLabel("Tarama sonucu")
        self.ilerleme_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.ilerleme_lbl.setStyleSheet("color:#3949ab;border:none;")
        self.prog = QProgressBar()
        self.prog.setTextVisible(False)
        self.prog.setFixedHeight(9)
        self.kalan_lbl = QLabel("")
        self.kalan_lbl.setStyleSheet("color:#5c6bc0;border:none;")
        lay.addWidget(self.ilerleme_lbl)
        lay.addWidget(self.prog, 1)
        lay.addWidget(self.kalan_lbl)
        return frame

    def _kart_paneli(self):
        grup = QGroupBox("Taranan Kartlar")
        lay = QVBoxLayout(grup)
        lay.setSpacing(7)
        filtre = QHBoxLayout()
        self.kart_arama = QLineEdit()
        self.kart_arama.setPlaceholderText("Kod, kart adı veya tedarikçi ara...")
        self.kart_arama.textChanged.connect(self._kartlari_filtrele)
        self.tur_filtre = QComboBox()
        self.tur_filtre.addItem("Tüm türler", "hepsi")
        self.tur_filtre.addItem("Stok", "stok")
        self.tur_filtre.addItem("Masraf", "masraf")
        self.tur_filtre.currentIndexChanged.connect(self._kartlari_filtrele)
        self.durum_filtre = QComboBox()
        self.durum_filtre.addItem("Bekleyenler", "Bekliyor")
        self.durum_filtre.addItem("Tüm durumlar", "hepsi")
        self.durum_filtre.addItem("Bağlananlar", "Bağlandı")
        self.durum_filtre.currentIndexChanged.connect(self._kartlari_filtrele)
        filtre.addWidget(self.kart_arama, 1)
        filtre.addWidget(self.tur_filtre)
        filtre.addWidget(self.durum_filtre)
        lay.addLayout(filtre)

        secim = QHBoxLayout()
        self.sec_btn = QPushButton("Görünen Bekleyenleri Seç")
        self.sec_btn.clicked.connect(lambda: self._gorunenleri_isaretle(True))
        self.temizle_btn = QPushButton("Seçimi Temizle")
        self.temizle_btn.clicked.connect(lambda: self._gorunenleri_isaretle(False))
        self.tablo_ozet = QLabel("")
        secim.addWidget(self.sec_btn)
        secim.addWidget(self.temizle_btn)
        secim.addStretch()
        secim.addWidget(self.tablo_ozet)
        lay.addLayout(secim)

        self.tablo = QTableWidget(0, 10)
        self.tablo.setHorizontalHeaderLabels([
            "Seç", "Tür", "Kart Kodu", "Kart Adı", "Birim",
            "Güncel Stok", "Fatura", "Birim Fiyat", "Reçete Miktarı", "Durum",
        ])
        self.tablo.setAlternatingRowColors(True)
        self.tablo.setSortingEnabled(True)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tablo.installEventFilter(self)
        self.tablo.setToolTip("Ok tuşlarıyla satıra gelin; Boşluk ile işaretleyin veya kaldırın.")
        self.tablo.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.horizontalHeader().setStretchLastSection(True)
        self.tablo.setColumnWidth(0, 42)
        self.tablo.setColumnWidth(1, 62)
        self.tablo.setColumnWidth(2, 138)
        self.tablo.setColumnWidth(3, 230)
        self.tablo.setColumnWidth(4, 62)
        self.tablo.setColumnWidth(5, 100)
        self.tablo.setColumnWidth(6, 58)
        self.tablo.setColumnWidth(7, 86)
        self.tablo.setColumnWidth(8, 105)
        self.tablo.itemChanged.connect(self._secim_ozeti)
        self.tablo.currentCellChanged.connect(self._kart_detayi)
        self.tablo.horizontalHeader().sortIndicatorChanged.connect(self._kartlari_filtrele)
        lay.addWidget(self.tablo, 1)

        self.detay_lbl = QLabel("Bir kartı seçerek fatura ve stok ayrıntılarını görebilirsiniz.")
        self.detay_lbl.setWordWrap(True)
        self.detay_lbl.setStyleSheet("color:#555;background:#f5f7fb;padding:7px;")
        lay.addWidget(self.detay_lbl)
        return grup

    def eventFilter(self, nesne, olay):
        if (nesne is self.tablo and olay.type() == QEvent.KeyPress
                and olay.key() == Qt.Key_Space
                and olay.modifiers() == Qt.NoModifier):
            satir = self.tablo.currentRow()
            idx = self._kart_indexi(satir)
            if (self.tablo.isEnabled() and self.worker is None
                    and idx is not None
                    and not self.tablo.isRowHidden(satir)
                    and self.sonuclar[idx]["islem"] == "Bekliyor"):
                sec = self.tablo.item(satir, 0)
                sec.setCheckState(
                    Qt.Unchecked if sec.checkState() == Qt.Checked else Qt.Checked
                )
            return True
        return super().eventFilter(nesne, olay)

    def _kart_indexi(self, satir):
        """Ekranda sıralanmış satırın tarama listesindeki sabit indeksini döner."""
        if satir < 0 or satir >= self.tablo.rowCount():
            return None
        sec = self.tablo.item(satir, 0)
        if sec is None:
            return None
        idx = sec.data(Qt.UserRole)
        return idx if isinstance(idx, int) and 0 <= idx < len(self.stoklar) else None

    def _mamul_paneli(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        grup = QGroupBox("Hangi Mamül Ağacına Eklenecek?")
        gl = QVBoxLayout(grup)
        self.arama = QLineEdit()
        self.arama.setPlaceholderText("Mamül kodu veya adı ile filtrele...")
        self.arama.textChanged.connect(self._mamul_filtrele)
        self.mamul_widget = QListWidget()
        self.mamul_widget.itemClicked.connect(self._mamul_secildi)
        self.secilen_lbl = QLabel("Seçim yapılmadı")
        self.secilen_lbl.setWordWrap(True)
        self.secilen_lbl.setStyleSheet("color:#777;background:#f5f5f5;padding:7px;")
        self.hat_secimi = QComboBox()
        self.hat_secimi.setEnabled(False)
        self.hat_secimi.setToolTip("Kartların ekleneceği mevcut reçete grubunu seçin.")
        gl.addWidget(etiket("Mamül ara:", bold=False, renk="#555"))
        gl.addWidget(self.arama)
        gl.addWidget(self.mamul_widget, 1)
        gl.addWidget(self.secilen_lbl)
        gl.addWidget(etiket("Reçete grubu:", bold=False, renk="#555"))
        gl.addWidget(self.hat_secimi)
        miktar_bilgi = QLabel(
            "Her kartın reçete miktarını soldaki tabloda çift tıklayarak değiştirin."
        )
        miktar_bilgi.setWordWrap(True)
        miktar_bilgi.setStyleSheet("color:#5c6bc0;font-size:11px;")
        gl.addWidget(miktar_bilgi)
        lay.addWidget(grup, 1)

        gecmis = QGroupBox("İşlem Geçmişi")
        gh = QVBoxLayout(gecmis)
        self.gecmis_liste = QListWidget()
        self.gecmis_liste.setMaximumHeight(125)
        gh.addWidget(self.gecmis_liste)
        lay.addWidget(gecmis)
        return w

    def _buton_bar(self):
        frame = QFrame()
        lay = QHBoxLayout(frame)
        self.geri_btn = QPushButton("← Tarama Sonucuna Dön")
        self.geri_btn.clicked.connect(self.geri_signal.emit)
        self.rapor_btn = QPushButton("Raporu Göster")
        self.rapor_btn.clicked.connect(lambda: self.rapor_signal.emit(list(self.sonuclar)))
        self.excel_btn = QPushButton("Listeyi Excel'e Aktar")
        self.excel_btn.setToolTip("Görünen listeyi ve tüm tarama sonuçlarını ayrı Excel sayfalarına kaydeder.")
        self.excel_btn.clicked.connect(self._excel_kaydet)
        self.kaydet_btn = QPushButton("Seçilen Kartları Reçeteye Bağla")
        self.kaydet_btn.setStyleSheet(
            "background:#3f51b5;color:white;border-radius:6px;"
            "padding:9px 20px;font-weight:bold;"
        )
        self.kaydet_btn.clicked.connect(self._kaydet)
        lay.addWidget(self.geri_btn)
        lay.addWidget(self.rapor_btn)
        lay.addWidget(self.excel_btn)
        lay.addStretch()
        lay.addWidget(self.kaydet_btn)
        return frame

    def _excel_kaydet(self):
        dosya, _ = QFileDialog.getSaveFileName(
            self, "Eşleştirme Listesini Excel'e Aktar",
            f"ceo_erp_eslestirme_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "Excel Dosyası (*.xlsx)",
        )
        if not dosya:
            return
        if not dosya.lower().endswith(".xlsx"):
            dosya += ".xlsx"

        gorunen, tumu = [], []
        for satir in range(self.tablo.rowCount()):
            idx = self._kart_indexi(satir)
            if idx is None:
                continue
            kayit = {
                **self.sonuclar[idx],
                "secili": self.tablo.item(satir, 0).checkState() == Qt.Checked,
                "recete_miktari": self.tablo.item(satir, 8).text(),
            }
            tumu.append(kayit)
            if not self.tablo.isRowHidden(satir):
                gorunen.append(kayit)
        try:
            eslestirme_listesi_excel_kaydet(dosya, gorunen, tumu)
            QMessageBox.information(self, "Excel Hazır", f"Dosya kaydedildi:\n{dosya}")
        except Exception as exc:
            QMessageBox.critical(self, "Excel Hatası", f"Dosya kaydedilemedi:\n{exc}")

    def baslat(self, conn, stoklar: list):
        self.conn = conn
        self.stoklar = stoklar
        self.sonuclar = [
            {**s, "mamul_kodu": "—", "mamul_adi": "—", "islem": "Bekliyor"}
            for s in stoklar
        ]
        self._aktif_secim = []
        self.gecmis_liste.clear()
        self.kart_arama.clear()
        self.tur_filtre.setCurrentIndex(0)
        self.durum_filtre.setCurrentIndex(0)
        self.arama.clear()
        self._mamul_sifirla()
        self._mamul_listesi_cache = mamul_agaci_listesi(conn)
        self._mamul_doldur()
        self._tablo_doldur()
        self._secim_ozeti()

    def _tablo_doldur(self):
        self.tablo.blockSignals(True)
        self.tablo.setSortingEnabled(False)
        self.tablo.setRowCount(len(self.stoklar))
        self._secim_itemleri = []
        for i, kart in enumerate(self.stoklar):
            sec = SiraliHucre()
            sec.setData(Qt.UserRole, i)
            sec.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            sec.setCheckState(Qt.Unchecked)
            self.tablo.setItem(i, 0, sec)
            self._secim_itemleri.append(sec)
            guncel_miktar = kart.get("guncel_miktar")
            stok_miktari = (
                "—" if kart.get("kart_tipi") == "masraf" or guncel_miktar is None
                else str(guncel_miktar)
            )
            degerler = [
                "Masraf" if kart.get("kart_tipi") == "masraf" else "Stok",
                kart.get("stok_kodu", ""), kart.get("stok_adi", ""),
                kart.get("birim") or "—", stok_miktari,
                str(kart.get("fatura_sayisi") or 0),
                str(kart.get("birim_fiyat") or "—"), "1", "Bekliyor",
            ]
            for col, deger in enumerate(degerler, 1):
                item = SiraliHucre(str(deger))
                bayrak = Qt.ItemIsEnabled | Qt.ItemIsSelectable
                if col == 8:
                    bayrak |= Qt.ItemIsEditable
                    item.setBackground(QColor("#fffde7"))
                item.setFlags(bayrak)
                self.tablo.setItem(i, col, item)
        self.tablo.setSortingEnabled(True)
        self.tablo.sortByColumn(2, Qt.AscendingOrder)
        self.tablo.blockSignals(False)
        self._kartlari_filtrele()

    def _kartlari_filtrele(self, *_):
        arama = self.kart_arama.text().casefold().strip()
        tur = self.tur_filtre.currentData()
        durum = self.durum_filtre.currentData()
        for satir in range(self.tablo.rowCount()):
            idx = self._kart_indexi(satir)
            if idx is None:
                self.tablo.setRowHidden(satir, True)
                continue
            kart = self.stoklar[idx]
            icerik = " ".join(str(kart.get(k) or "") for k in
                               ("stok_kodu", "stok_adi", "tedarikci")).casefold()
            goster = (
                (not arama or arama in icerik)
                and (tur == "hepsi" or kart.get("kart_tipi", "stok") == tur)
                and (durum == "hepsi" or self.sonuclar[idx]["islem"] == durum)
            )
            self.tablo.setRowHidden(satir, not goster)
        self._secim_ozeti()

    def _gorunenleri_isaretle(self, sec):
        self.tablo.blockSignals(True)
        for satir in range(self.tablo.rowCount()):
            if self.tablo.isRowHidden(satir):
                continue
            idx = self._kart_indexi(satir)
            if idx is not None and self.sonuclar[idx]["islem"] == "Bekliyor":
                self.tablo.item(satir, 0).setCheckState(
                    Qt.Checked if sec else Qt.Unchecked
                )
        self.tablo.blockSignals(False)
        self._secim_ozeti()

    def _secim_ozeti(self, *_):
        secili = sum(
            self.tablo.item(i, 0).checkState() == Qt.Checked
            for i in range(self.tablo.rowCount())
        )
        gorunen = sum(not self.tablo.isRowHidden(i)
                      for i in range(self.tablo.rowCount()))
        baglanan = sum(s["islem"] == "Bağlandı" for s in self.sonuclar)
        toplam = len(self.stoklar)
        self.tablo_ozet.setText(f"Görünen: {gorunen} / {toplam}   Seçili: {secili}")
        self.ilerleme_lbl.setText(f"{toplam} kart · {baglanan} bağlandı")
        self.kalan_lbl.setText(f"{toplam - baglanan} bekliyor")
        self.prog.setRange(0, max(toplam, 1))
        self.prog.setValue(baglanan)
        self.kaydet_btn.setText(f"Seçilen {secili} Kartı Reçeteye Bağla")
        self.kaydet_btn.setEnabled(secili > 0 and self.worker is None)

    def _kart_detayi(self, satir, _sutun, *_):
        idx = self._kart_indexi(satir)
        if idx is None:
            return
        s = self.stoklar[idx]
        self.detay_lbl.setText(
            f"{s.get('stok_kodu', '')} — {s.get('stok_adi', '')}  |  "
            f"Güncel miktar: {s.get('guncel_miktar') if s.get('guncel_miktar') is not None else '—'}  |  "
            f"İlk fatura: {s.get('ilk_fatura') or '—'}  |  "
            f"Son fatura: {s.get('son_fatura') or '—'}  |  "
            f"Tedarikçi: {s.get('tedarikci') or '—'}"
        )

    def _mamul_doldur(self, filtre=""):
        self.mamul_widget.clear()
        metin = filtre.casefold().strip()
        for kod, ad in self._mamul_listesi_cache:
            if metin and metin not in kod.casefold() and metin not in ad.casefold():
                continue
            item = QListWidgetItem(f"{kod}   {ad}")
            item.setData(Qt.UserRole, (kod, ad))
            self.mamul_widget.addItem(item)

    def _mamul_filtrele(self, txt):
        self._mamul_sifirla()
        self._mamul_doldur(txt)

    def _mamul_sifirla(self):
        self.secilen_mamul = None
        self.hat_secimi.clear()
        self.hat_secimi.setEnabled(False)
        self.secilen_lbl.setText("Seçim yapılmadı")
        self.secilen_lbl.setStyleSheet("color:#777;background:#f5f5f5;padding:7px;")

    def _mamul_secildi(self, item):
        kod, ad = item.data(Qt.UserRole)
        try:
            planlar = mamul_hat_planlari(self.conn, kod)
        except Exception as exc:
            self._mamul_sifirla()
            QMessageBox.critical(self, "Reçete Hatası", str(exc))
            return
        self.secilen_mamul = (kod, ad)
        self.secilen_lbl.setText(f"✓  {kod} — {ad}")
        self.secilen_lbl.setStyleSheet("color:#2e7d32;background:#e8f5e9;padding:7px;")
        self.hat_secimi.clear()
        if len(planlar) > 1:
            self.hat_secimi.addItem("Reçete grubunu seçin...", None)
        for plan in planlar:
            self.hat_secimi.addItem(
                f"{plan['kod']} — {plan['ad'].strip()} (Grup #{plan['id']})", plan
            )
        self.hat_secimi.setEnabled(bool(planlar))
        if not planlar:
            QMessageBox.warning(self, "Reçete Hatası", "Bu mamülün aktif reçetesinde grup yok.")

    def _secili_kartlar(self):
        secilen = []
        for satir in range(self.tablo.rowCount()):
            idx = self._kart_indexi(satir)
            if (idx is None or self.sonuclar[idx]["islem"] != "Bekliyor"
                    or self.tablo.item(satir, 0).checkState() != Qt.Checked):
                continue
            kart = self.stoklar[idx]
            ham = self.tablo.item(satir, 8).text().strip().replace(",", ".")
            try:
                miktar = Decimal(ham)
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(f"{kart['stok_kodu']}: geçerli bir reçete miktarı girin.") from exc
            if not miktar.is_finite() or miktar <= 0 or miktar > Decimal("999999999"):
                raise ValueError(f"{kart['stok_kodu']}: miktar 0 ile 999999999 arasında olmalı.")
            secilen.append((idx, {
                "kart_kodu": kart["stok_kodu"],
                "kart_tipi": kart.get("kart_tipi", "stok"),
                "miktar": miktar,
            }))
        return secilen

    def _kaydet(self):
        if self.worker is not None:
            return
        if not self.secilen_mamul:
            QMessageBox.warning(self, "Uyarı", "Sağ listeden bir mamül seçin.")
            return
        plan = self.hat_secimi.currentData()
        if plan is None:
            QMessageBox.warning(self, "Uyarı", "Reçete grubunu seçin.")
            return
        try:
            self._aktif_secim = self._secili_kartlar()
        except ValueError as exc:
            QMessageBox.warning(self, "Miktar Hatası", str(exc))
            return
        if not self._aktif_secim:
            QMessageBox.warning(self, "Uyarı", "Bağlanacak kartları işaretleyin.")
            return
        self._aktif_mamul = self.secilen_mamul
        self._aktif_plan = plan
        self._islem_kilidi(True)
        self.worker = TopluBaglamaThread(
            self.conn, [kart for _, kart in self._aktif_secim],
            self._aktif_mamul[0], plan["id"],
        )
        self.worker.ilerleme.connect(self._yazma_ilerlemesi)
        self.worker.bitti.connect(self._kayit_bitti)
        self.worker.hata.connect(self._kayit_hatasi)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _islem_kilidi(self, kilitli):
        for w in (self.tablo, self.kart_arama, self.tur_filtre, self.durum_filtre,
                  self.sec_btn, self.temizle_btn, self.arama, self.mamul_widget,
                  self.hat_secimi, self.kaydet_btn, self.geri_btn, self.rapor_btn,
                  self.excel_btn):
            w.setEnabled(not kilitli)

    def _yazma_ilerlemesi(self, sira, toplam):
        self.kalan_lbl.setText(f"Kaydediliyor: {sira} / {toplam}")

    def _kayit_bitti(self, ids):
        kod, ad = self._aktif_mamul
        plan = self._aktif_plan
        self.tablo.blockSignals(True)
        self.tablo.setSortingEnabled(False)
        for (idx, kart), girdi_id in zip(self._aktif_secim, ids):
            sonuc = self.sonuclar[idx]
            sonuc.update({
                "mamul_kodu": kod, "mamul_adi": ad,
                "hat_kodu": plan["kod"], "hat_plani_id": plan["id"],
                "recete_miktari": float(kart["miktar"]),
                "girdi_id": girdi_id, "islem": "Bağlandı",
            })
            sec = self._secim_itemleri[idx]
            satir = sec.row()
            sec.setCheckState(Qt.Unchecked)
            sec.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            durum = self.tablo.item(satir, 9)
            durum.setText("Bağlandı")
            durum.setForeground(QColor("#2e7d32"))
            self.tablo.item(satir, 8).setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.tablo.setSortingEnabled(True)
        self.tablo.blockSignals(False)
        gecmis = QListWidgetItem(
            f"✓ {len(ids)} kart → {kod} / {plan['kod']}"
        )
        gecmis.setForeground(QColor("#2e7d32"))
        self.gecmis_liste.insertItem(0, gecmis)
        self.worker = None
        self._aktif_secim = []
        self._islem_kilidi(False)
        self.durum_filtre.setCurrentIndex(0)
        self._kartlari_filtrele()
        self.tablo.clearSelection()
        self.detay_lbl.setText(
            f"{len(ids)} kart reçeteye bağlandı ve bekleyenler listesinden çıkarıldı. "
            "İsterseniz 'Bağlananlar' filtresinden kaydı görebilirsiniz."
        )

    def _kayit_hatasi(self, hata):
        self.worker = None
        self._aktif_secim = []
        self._islem_kilidi(False)
        self._secim_ozeti()
        QMessageBox.critical(
            self, "Toplu Bağlama Hatası",
            f"Hiçbir seçili kart kaydedilmedi.\n\n{hata}",
        )
