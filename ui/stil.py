from PyQt5.QtWidgets import QLabel, QPushButton, QFrame
from PyQt5.QtGui import QFont

STIL = """
QMainWindow,QWidget{font-family:'Segoe UI';font-size:12px;background:#f0f2f5;}
QGroupBox{border:1.5px solid #c5cae9;border-radius:8px;
    margin-top:8px;padding:10px 8px 8px 8px;background:white;}
QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;
    color:#3949ab;font-weight:bold;font-size:12px;}
QLineEdit{border:1.5px solid #9fa8da;border-radius:6px;
    padding:6px 10px;background:white;font-size:12px;}
QLineEdit:focus{border-color:#3f51b5;}
QDoubleSpinBox{border:1.5px solid #9fa8da;border-radius:6px;
    padding:4px 8px;background:white;font-size:12px;}
QDoubleSpinBox:focus{border-color:#3f51b5;}
QDateEdit{border:1.5px solid #9fa8da;border-radius:6px;
    padding:5px 8px;background:white;font-size:12px;}
QDateEdit:focus{border-color:#3f51b5;}
QPushButton{border-radius:6px;padding:8px 20px;font-size:12px;font-weight:bold;border:none;}
QListWidget{border:1px solid #e8eaf6;border-radius:6px;background:white;font-size:12px;}
QListWidget::item{padding:7px 10px;border-bottom:1px solid #f3f3f3;}
QListWidget::item:selected{background:#e8eaf6;color:#1a237e;}
QListWidget::item:hover{background:#f3f4ff;}
QProgressBar{border:none;border-radius:5px;background:#e8eaf6;}
QProgressBar::chunk{border-radius:5px;
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3f51b5,stop:1 #5c6bc0);}
QCheckBox{spacing:8px;}
QCheckBox::indicator{width:16px;height:16px;border-radius:3px;
    border:2px solid #9fa8da;background:white;}
QCheckBox::indicator:checked{background:#3f51b5;border-color:#3f51b5;}
QRadioButton{spacing:8px;}
QRadioButton::indicator{width:15px;height:15px;border-radius:7px;
    border:2px solid #9fa8da;background:white;}
QRadioButton::indicator:checked{background:#3f51b5;border-color:#3f51b5;}
QScrollArea{border:none;background:transparent;}
"""


def etiket(txt, renk="#7986cb", bold=True, size=12):
    w = QLabel(txt)
    s = f"color:{renk};"
    if bold:
        s += "font-weight:bold;"
    s += f"font-size:{size}px;"
    w.setStyleSheet(s)
    return w


def buton(txt, bg, fg="white", min_w=None, h=None):
    b = QPushButton(txt)
    b.setStyleSheet(f"background:{bg};color:{fg};")
    if min_w:
        b.setMinimumWidth(min_w)
    if h:
        b.setFixedHeight(h)
    return b


def ayrac():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color:#e0e0e0;")
    return f
