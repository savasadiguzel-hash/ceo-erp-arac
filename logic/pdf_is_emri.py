"""İş emri PDF formu — ISO doküman stili, A5."""

import os
import sys
from fpdf import FPDF

SIRKET_ADI   = "Gempa Elektro Mekanik Mühendislik Ltd. Şti"
FORM_BASLIGI = "ÜRETİM İŞ EMRİ"
FORM_NO      = "SRCF.06.01.01/05.06.2026/REV02"

DURUM_ETIKET = {
    1: "Başlamadı",
    2: "Tasarım Aşamasında",
    3: "Devam Ediyor",
    4: "Beklemeye Alındı",
    5: "Tamamlandı",
}

# ── Renk paleti ──────────────────────────────────────────────────────────────
NAVY      = (26,  35,  126)   # #1A237E
NAVY_MID  = (57,  73,  171)   # #3949AB  — ince çizgiler
LABEL_BG  = (240, 242, 252)   # hafif lacivert ton, etiket zemini
BEYAZ     = (255, 255, 255)
KOYU      = (33,  33,  33)
CIZGI     = (160, 165, 200)   # açık gri-mavi, tablo iç çizgileri
SATIR_ALT = (246, 247, 253)   # çift satır zemini

_MARGIN  = 15         # sol/sağ kenar boşluğu (mm)  — A4
_W       = 180        # A4 yazılabilir genişlik (210 − 2×15)
_HDR_H   = 30         # ISO başlık kutusu yüksekliği (mm)
_W_LOGO  = 40         # sol sütun — logo
_W_TITLE = 100        # orta sütun — başlık
_W_FRMNO = _W - _W_LOGO - _W_TITLE   # 40mm — form no

_WIN_FONTS  = r"C:\Windows\Fonts"
_FONT_PAIRS = [
    ("calibri.ttf",  "calibrib.ttf"),
    ("arial.ttf",    "arialbd.ttf"),
    ("segoeui.ttf",  "segoeuib.ttf"),
]


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _sec_font(font_pairs=_FONT_PAIRS, fonts_dir=_WIN_FONTS):
    for n, b in font_pairs:
        np, bp = os.path.join(fonts_dir, n), os.path.join(fonts_dir, b)
        if os.path.isfile(np) and os.path.isfile(bp):
            return np, bp
    raise RuntimeError("TTF font bulunamadı.")


def _logo_yolu():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dirs = []
    if getattr(sys, "_MEIPASS", None):
        dirs.append(os.path.join(sys._MEIPASS, "assets"))
    dirs.append(os.path.join(base, "assets"))
    for d in dirs:
        for f in ("logo.png", "logo.jpeg", "logo.jpg"):
            p = os.path.join(d, f)
            if os.path.isfile(p):
                return p
    return None


def _kes(pdf, metin: str, max_mm: float) -> str:
    """Metin hücreye sığmıyorsa sağdan '…' ile kırpar."""
    if not metin:
        return ""
    if pdf.get_string_width(metin) <= max_mm - 1:
        return metin
    while metin and pdf.get_string_width(metin + "…") > max_mm - 1:
        metin = metin[:-1]
    return metin + "…"


# ── PDF sınıfı ────────────────────────────────────────────────────────────────

class _IsEmriPDF(FPDF):
    def __init__(self, logo: str | None, fn: str, fb: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._logo = logo
        # Üst marjin başlık kutusunu + boşluğu hesaba katar
        self.set_margins(_MARGIN, _MARGIN + _HDR_H + 4, _MARGIN)
        self.set_auto_page_break(auto=True, margin=35)
        self.add_font("Ana",          fname=fn)
        self.add_font("Ana", style="B", fname=fb)

    # ── Header (her sayfada otomatik çizilir) ─────────────────────────────────
    def header(self):
        self.set_line_width(0.5)
        self.set_draw_color(*NAVY)

        # Dış dikdörtgen
        self.rect(_MARGIN, _MARGIN, _W, _HDR_H, "D")

        # Dikey bölücüler
        x1 = _MARGIN + _W_LOGO
        x2 = x1 + _W_TITLE
        self.line(x1, _MARGIN,        x1, _MARGIN + _HDR_H)
        self.line(x2, _MARGIN,        x2, _MARGIN + _HDR_H)

        # ── Sol sütun: Logo ───────────────────────────────────────────────────
        if self._logo:
            try:
                self.image(self._logo,
                           x=_MARGIN + 2,
                           y=_MARGIN + (_HDR_H - 24) / 2,
                           h=24, w=_W_LOGO - 4)
            except Exception:
                pass

        # ── Orta sütun: Başlık ───────────────────────────────────────────────
        self.set_text_color(*NAVY)
        self.set_font("Ana", "B", 13)
        self.set_xy(x1, _MARGIN + 5)
        self.cell(_W_TITLE, 9, FORM_BASLIGI, align="C")

        self.set_font("Ana", "", 6.5)
        self.set_xy(x1, _MARGIN + 15)
        self.cell(_W_TITLE, 5, _kes(self, SIRKET_ADI, _W_TITLE), align="C")

        # ── Sağ sütun: Form No ───────────────────────────────────────────────
        self.set_font("Ana", "B", 6)
        parts = FORM_NO.split("/")
        y_fn = _MARGIN + 5
        for p in parts:
            self.set_xy(x2, y_fn)
            self.cell(_W_FRMNO, 6, p.strip(), align="C")
            y_fn += 7

        self.set_text_color(*KOYU)
        # fpdf2 bu versiyonunda header() sonrası kursörü sıfırlamıyor; elle düzeltiyoruz
        self.set_xy(self.l_margin, self.t_margin)

    # ── Footer (her sayfada otomatik çizilir) ─────────────────────────────────
    def footer(self):
        self.set_y(-32)
        self.set_line_width(0.3)
        self.set_draw_color(*CIZGI)
        self.line(_MARGIN, self.get_y(), 210 - _MARGIN, self.get_y())
        self.ln(3)

        col_w = _W / 3          # ~44mm
        imzalar = ["Hazırlayan", "Onaylayan", "Teslim Alan"]
        self.set_font("Ana", "B", 7)
        self.set_text_color(*NAVY_MID)
        y0 = self.get_y()
        for i, etiket in enumerate(imzalar):
            self.set_xy(_MARGIN + i * col_w, y0)
            self.cell(col_w, 5, etiket + ":", ln=False)
        self.ln(6)
        y1 = self.get_y()
        self.set_draw_color(*NAVY_MID)
        for i in range(3):
            self.set_xy(_MARGIN + i * col_w, y1)
            self.cell(col_w - 6, 5, "", border="B", ln=False)
        self.set_text_color(*KOYU)


# ── Bölüm çiziciler ──────────────────────────────────────────────────────────

def _bilgi_izgarasi(pdf: _IsEmriPDF, emir: dict, durum_str: str):
    """2×2 bilgi ızgarası: Emir No/Tarih + Durum/Açıklama."""
    LBL = 26   # etiket sütun genişliği  — A4: (26+64)×2 = 180mm
    VAL = 64   # değer sütun genişliği
    H   = 8    # satır yüksekliği

    pdf.set_line_width(0.3)
    pdf.set_draw_color(*NAVY_MID)

    satirlar = [
        ("Emir No:",  emir.get("Kodu") or "",          "Tarih:",     emir.get("EmirTarihi") or ""),
        ("Durum:",    durum_str,                        "Açıklama:",  emir.get("Aciklama") or "—"),
    ]
    for lbl1, val1, lbl2, val2 in satirlar:
        # Etiket 1
        pdf.set_fill_color(*LABEL_BG)
        pdf.set_font("Ana", "B", 8)
        pdf.cell(LBL, H, lbl1, border=1, fill=True)
        # Değer 1
        pdf.set_font("Ana", "", 8)
        pdf.cell(VAL, H, _kes(pdf, val1, VAL), border=1)
        # Etiket 2
        pdf.set_fill_color(*LABEL_BG)
        pdf.set_font("Ana", "B", 8)
        pdf.cell(LBL, H, lbl2, border=1, fill=True)
        # Değer 2
        pdf.set_font("Ana", "", 8)
        pdf.cell(VAL, H, _kes(pdf, val2, VAL), border=1, ln=True)


def _bolum_baslik(pdf: _IsEmriPDF, metin: str):
    """Lacivert zemin + beyaz yazı bölüm başlığı."""
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(*BEYAZ)
    pdf.set_font("Ana", "B", 8)
    pdf.cell(_W, 6, "  " + metin, fill=True, border=0, ln=True)
    pdf.set_text_color(*KOYU)


def _tablo(pdf: _IsEmriPDF, malzemeler: list[dict]):
    """Ürün tablosu: No | Kodu | Adı | Talep Miktarı."""
    col = [10, 42, 108, 20]   # toplam 180mm  — A4
    bas = [("No", "C"), ("Kodu", "L"), ("Adı", "L"), ("Talep Miktarı", "R")]

    # Başlık satırı
    pdf.set_font("Ana", "B", 7)
    pdf.set_fill_color(*LABEL_BG)
    pdf.set_draw_color(*NAVY_MID)
    pdf.set_line_width(0.3)
    pdf.set_text_color(*NAVY)
    for (etiket, hiza), w in zip(bas, col):
        pdf.cell(w, 6, etiket, border=1, fill=True, align=hiza)
    pdf.ln()
    pdf.set_text_color(*KOYU)

    # Veri satırları
    pdf.set_font("Ana", "", 7)
    for i, m in enumerate(malzemeler, 1):
        fill = (i % 2 == 0)
        pdf.set_fill_color(*SATIR_ALT) if fill else pdf.set_fill_color(*BEYAZ)
        miktar = m.get("Miktar") or 0
        try:
            mstr = f"{float(miktar):,.4f}".rstrip("0").rstrip(".")
        except (ValueError, TypeError):
            mstr = str(miktar)
        pdf.cell(col[0], 5.5, str(i),                      border=1, fill=fill, align="C")
        pdf.cell(col[1], 5.5, _kes(pdf, m.get("Kodu",""), col[1]), border=1, fill=fill, align="L")
        pdf.cell(col[2], 5.5, _kes(pdf, m.get("Adi", ""), col[2]), border=1, fill=fill, align="L")
        pdf.cell(col[3], 5.5, mstr,                        border=1, fill=fill, align="R")
        pdf.ln()

    if not malzemeler:
        pdf.set_text_color(150, 150, 150)
        pdf.set_font("Ana", "", 8)
        pdf.cell(_W, 8, "  Kayıt bulunamadı.", ln=True)
        pdf.set_text_color(*KOYU)


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def is_emri_pdf_olustur(dosya_yolu: str, emir: dict, malzemeler: list) -> None:
    """
    emir       — DB dict: Kodu, EmirTarihi, DurumId, Aciklama
    malzemeler — list of dict: Kodu, Adi, Miktar
    """
    fn, fb = _sec_font()
    logo   = _logo_yolu()

    pdf = _IsEmriPDF(logo, fn, fb)
    pdf.add_page()

    durum_id  = emir.get("DurumId") or emir.get("durum_id") or 0
    durum_str = DURUM_ETIKET.get(durum_id, f"Durum {durum_id}")

    # Bilgi ızgarası
    _bilgi_izgarasi(pdf, emir, durum_str)
    pdf.ln(4)

    # Ürün tablosu
    _bolum_baslik(pdf, "ÜRETİLECEK ÜRÜNLER")
    pdf.ln(1)
    _tablo(pdf, malzemeler)

    pdf.output(dosya_yolu)
