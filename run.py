import sys
from qtpy.QtWidgets import QApplication
from gui import MainWindow


# ---------------- RUN ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()

    sys.exit(app.exec())
