import sys
from PyQt5.QtWidgets import QApplication
from ui.ana_pencere import AnaPencere

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    AnaPencere().show()
    sys.exit(app.exec_())
