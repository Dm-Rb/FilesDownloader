import sys
from qtpy.QtWidgets import QApplication
from gui import MainWindow
import multiprocessing


if __name__ == "__main__":
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()

    sys.exit(app.exec())
