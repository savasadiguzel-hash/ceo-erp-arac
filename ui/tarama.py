import time
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QGroupBox,
    QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from db.sorgular import (tarama_istatistikleri,
                         recetesiz_stok_hareketleri, recetesiz_faturali_ozet)
from logic.excel import kesisim_excel_kaydet
from ui.stil import etiket, buton


class TaramaThread(QThread):
    adim  = pyqtSignal(str, int, int)
    bitti = pyqtSignal(list, list)  # (ozet_list, detay_list)
    hata  = pyqtSignal(str)

    def __init__(self, conn, yontem: str, bas_tarih: str, bit_tarih: str):
        super().__init__()
        self.conn = conn
        self.yontem = yontem
        self.bas_tarih = bas_tarih
        self.bit_tarih = bit_tarih

    def run(self):
        try:
            adimlar = tarama_istatistikleri(self.conn)
            for mesaj, toplam in adimlar:
                adim = max(1, toplam // 50)
                for i in range(0, toplam + 1, adim):
                    self.adim.emit(mesaj, min(i, toplam), toplam)
                    time.sleep(0.016)
                self.adim.emit(mesaj, toplam, toplam)
                time.sleep(0.15)
            hareketler = recetesiz_stok_hareketleri(self.conn, self.bas_tarih, self.bit_tarih)
            ozet = recetesiz_faturali_ozet(hareketler, self.yontem)
            self.bitti.emit(ozet, hareketler)
        except Exception as e:
            import traceback
            self.hata.emit(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")


class TaramaSayfasi(QWidget):
    bitti = pyqtSignal(list)   # kesişim stokları

    def __init__(self):
        super().__init__()
        self._toplam_stok = 0
        self._recetesiz   = 0
        ana = QVBoxLayout(self)
        ana.setAlignment(Qt.AlignCenter)
        ana.setSpacing(14)

        self.tarih_lbl = QLabel("")
        self.tarih_lbl.setAlignment(Qt.AlignCenter)
        self.tarih_lbl.setStyleSheet("color:#5c6bc0;font-size:11px;")

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

        self._stoklar  = []
        self._detaylar = []
        self._yontem   = "WA"
        self._tarih_aralik = ""

        self.devam_btn = buton("Eşleştirmeye Geç  →", "#3f51b5", min_w=210, h=42)
        self.devam_btn.hide()

        self.excel_btn = buton("📥  Excel'e Aktar (.xlsx)", "#2e7d32", min_w=210, h=42)
        self.excel_btn.hide()
        self.excel_btn.clicked.connect(self._excel_kaydet)

        self.buton_satiri = QWidget()
        bl = QHBoxLayout(self.buton_satiri)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(12)
        bl.addWidget(self.excel_btn)
        bl.addWidget(self.devam_btn)
        self.buton_satiri.hide()

        ana.addStretch()
        ana.addWidget(etiket("Stok Analizi Yapılıyor...", "#1a237e", size=15),
                      alignment=Qt.AlignCenter)
        ana.addWidget(self.tarih_lbl)
        ana.addWidget(self.adim_lbl)
        ana.addWidget(self.bar, alignment=Qt.AlignCenter)
        ana.addWidget(self.sayac)
        ana.addSpacing(8)
        ana.addWidget(self.ozet_grup, alignment=Qt.AlignCenter)
        ana.addWidget(self.buton_satiri, alignment=Qt.AlignCenter)
        ana.addStretch()

    def baslat(self, conn, yontem: str, bas_tarih: str, bit_tarih: str):
        self._yontem = yontem
        self._tarih_aralik = f"{bas_tarih} – {bit_tarih}"
        self.tarih_lbl.setText(f"Tarih aralığı: {self._tarih_aralik}")
        self.ozet_grup.hide()
        self.buton_satiri.hide()
        self.bar.setValue(0)
        self.thread = TaramaThread(conn, yontem, bas_tarih, bit_tarih)
        self.thread.adim.connect(self._guncelle)
        self.thread.bitti.connect(self._bitti)
        self.thread.hata.connect(self._hata)
        self.thread.start()

    def _guncelle(self, mesaj, mevcut, toplam):
        self.adim_lbl.setText(mesaj)
        self.bar.setValue(int(mevcut / toplam * 100) if toplam else 0)
        self.sayac.setText(f"{mevcut:,} / {toplam:,}")

    def _bitti(self, stoklar: list, detaylar: list):
        self._stoklar  = stoklar
        self._detaylar = detaylar
        self.bar.setValue(100)
        self.adim_lbl.setText("Analiz tamamlandı.")
        self.sayac.setText("")
        self.ozet_lbl.setText(
            f"<b>Reçete/mamül ağacında olmayan stoklar:</b>  {len(stoklar):,}<br>"
            f"<b>Bunlardan alış faturası olanlar (kesişim):</b>  "
            f"<span style='color:#c62828;font-weight:bold;'>{len(stoklar)}</span>"
        )
        self.ozet_grup.show()
        self.buton_satiri.show()
        self.devam_btn.show()
        self.excel_btn.show()
        self.devam_btn.clicked.connect(lambda: self.bitti.emit(stoklar))

    def _hata(self, mesaj: str):
        self.adim_lbl.setText("Hata oluştu.")
        self.bar.setValue(0)
        QMessageBox.critical(self, "Tarama Hatası", mesaj)

    def _excel_kaydet(self):
        dosya, _ = QFileDialog.getSaveFileName(
            self, "Excel Kaydet",
            f"kesisim_kumesi_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "Excel Dosyası (*.xlsx)")
        if not dosya:
            return
        try:
            kesisim_excel_kaydet(dosya, self._stoklar, self._detaylar,
                                  self._tarih_aralik, self._yontem)
            QMessageBox.information(self, "Başarılı", f"Dosya kaydedildi:\n{dosya}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel kaydedilemedi:\n{e}")
