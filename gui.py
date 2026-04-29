from qtpy.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QTableView, QLabel, QMenu, QStackedLayout, QRadioButton, QButtonGroup
)
from qtpy.QtCore import QAbstractTableModel, Qt
from qtpy.QtGui import QColor
from table_reader import UniversalTableReader
from qtpy.QtWidgets import QLineEdit, QTextEdit, QProgressBar
from qtpy.QtCore import QThread, Signal
import asyncio
from files_downloader import FileDownloader


# ---------------- MODEL ----------------
class PandasModel(QAbstractTableModel):
    def __init__(self, df):
        super().__init__()
        self._df = df
        self.url_col = None
        self.name_col = None

    def rowCount(self, parent=None):
        return self._df.shape[0]

    def columnCount(self, parent=None):
        return self._df.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return str(self._df.iloc[index.row(), index.column()])

        if role == Qt.BackgroundRole:
            if index.column() == self.url_col:
                return QColor("#cce5ff")
            if index.column() == self.name_col:
                return QColor("#d4edda")

        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            name = str(self._df.columns[section])

            if section == self.url_col:
                return f"{name} [URL]"
            if section == self.name_col:
                return f"{name} [NAME]"

            return name

        return None


# ---------------- MAIN WINDOW ----------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Loader")
        self.resize(400, 200)

        self.reader = UniversalTableReader()

        self.stack = QStackedLayout()
        self.setLayout(self.stack)

        self.start_screen = self.create_start_screen()
        self.preview_screen = self.create_preview_screen()

        self.stack.addWidget(self.start_screen)
        self.stack.addWidget(self.preview_screen)

        self.stack.setCurrentWidget(self.start_screen)
        ###
        self.process_screen = self.create_process_screen()
        self.stack.addWidget(self.process_screen)
        self.worker = None

    # ---------- START SCREEN ----------
    def create_start_screen(self):
        w = QWidget()
        layout = QVBoxLayout()

        btn = QPushButton("Выбрать файл")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.open_file)

        layout.addStretch()
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)  # Добавляем выравнивание
        layout.addStretch()

        w.setLayout(layout)
        return w

    # ---------- PREVIEW SCREEN ----------
    def create_preview_screen(self):
        w = QWidget()
        layout = QVBoxLayout()

        top = QHBoxLayout()

        self.back_btn = QPushButton("Назад")
        self.back_btn.clicked.connect(self.go_back)

        self.forward_btn = QPushButton("Вперёд")
        self.forward_btn.setEnabled(False)
        self.forward_btn.clicked.connect(self.process_data)

        top.addWidget(self.back_btn)
        top.addStretch()
        top.addWidget(self.forward_btn)

        layout.addSpacing(10)
        layout.addLayout(top)
        layout.addSpacing(20)

        self.table = QTableView()
        layout.addWidget(self.table)

        w.setLayout(layout)
        return w

    # ---------- FILE ----------
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Файл", "", "All (*);;CSV (*.csv);;Excel (*.xlsx)")

        if not path:
            return

        try:
            self.reader.read_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            return

        self.show_preview()

    # ---------- SHOW PREVIEW ----------
    def show_preview(self):
        preview = self.reader.data_frame.head(10)

        self.model = PandasModel(preview)
        self.table.setModel(self.model)

        header = self.table.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.open_menu)

        self.stack.setCurrentWidget(self.preview_screen)

    # ---------- MENU ----------
    def open_menu(self, pos):
        header = self.table.horizontalHeader()
        col = header.logicalIndexAt(pos)

        if col < 0:
            return

        menu = QMenu(self)

        url = menu.addAction("Использовать как ссылки")
        name = menu.addAction("Использовать как имена файлов")

        act = menu.exec(header.mapToGlobal(pos))

        if act == url:
            self.model.url_col = col
            self.reader.urls_column_index = col
            self.forward_btn.setEnabled(True)

        elif act == name:
            self.model.name_col = col
            self.reader.filenames_column_index = col

        self.table.viewport().update()

    # ---------- PROCESS ----------
    def process_data(self):
        # 🔹 сохраняем индексы
        self.reader.urls_column_index = self.model.url_col
        self.reader.filenames_column_index = self.model.name_col

        # 🔹 переходим на новый экран
        self.stack.setCurrentWidget(self.process_screen)

    # ---------- BACK ----------
    def go_back(self):
        self.reader = UniversalTableReader()
        self.table.setModel(None)
        self.forward_btn.setEnabled(False)

        self.stack.setCurrentWidget(self.start_screen)

    def create_process_screen(self):
        w = QWidget()
        layout = QVBoxLayout()

        # ---------------- TOP BAR ----------------
        top_layout = QHBoxLayout()

        self.back_process_btn = QPushButton("Назад")
        self.back_process_btn.setFixedWidth(100)
        self.back_process_btn.clicked.connect(self.go_back_to_preview)

        top_layout.addWidget(self.back_process_btn)
        top_layout.addStretch()

        layout.addLayout(top_layout)
        layout.addSpacing(20)

        # ---------------- SELECT DIR BUTTON (CENTER) ----------------
        center_layout = QHBoxLayout()

        self.dir_button = QPushButton("Выбрать папку для скачивания")
        self.dir_button.setFixedWidth(260)

        self.dir_button.clicked.connect(self.select_directory)

        center_layout.addStretch()
        center_layout.addWidget(self.dir_button)
        center_layout.addStretch()

        layout.addLayout(center_layout)
        layout.addSpacing(20)

        # ---------------- DELIMITER ----------------
        delim_layout = QHBoxLayout()

        delim_label = QLabel("Разделитель ссылок:")

        self.delimiter_input = QLineEdit()
        self.delimiter_input.setFixedWidth(40)

        delim_layout.addStretch()
        delim_layout.addWidget(delim_label)
        delim_layout.addSpacing(10)
        delim_layout.addWidget(self.delimiter_input)
        delim_layout.addStretch()
        layout.addLayout(delim_layout)
        layout.addSpacing(20)

        # ---------------- HEADERS RADIO ----------------
        headers_layout = QHBoxLayout()

        headers_label = QLabel("Пропустить первую строку (заголовки)?")

        self.radio_skip = QRadioButton("Пропустить")
        self.radio_no_skip = QRadioButton("Не пропускать")

        # группировка
        self.headers_group = QButtonGroup()
        self.headers_group.addButton(self.radio_skip)
        self.headers_group.addButton(self.radio_no_skip)

        # дефолт (как в классе)
        self.radio_skip.setChecked(True)

        # обработчик
        self.radio_skip.toggled.connect(self.update_headers_option)

        headers_layout.addStretch()
        headers_layout.addWidget(headers_label)
        headers_layout.addSpacing(10)
        headers_layout.addWidget(self.radio_skip)
        headers_layout.addWidget(self.radio_no_skip)
        headers_layout.addStretch()

        layout.addLayout(headers_layout)
        layout.addSpacing(20)


        # ---------------- START BUTTON ----------------
        start_layout = QHBoxLayout()

        self.start_button = QPushButton("Начать")
        self.start_button.setFixedWidth(260)

        self.start_button.clicked.connect(self.start_processing)

        start_layout.addStretch()
        start_layout.addWidget(self.start_button)
        start_layout.addStretch()

        layout.addLayout(start_layout)
        layout.addSpacing(20)

        # ---------------- PROGRESS ----------------
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setEnabled(False)

        layout.addWidget(self.progress)
        layout.addSpacing(10)

        # ---------------- LOG ----------------
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        layout.addWidget(self.log_output)

        w.setLayout(layout)
        return w

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Выберите папку")

        if not directory:
            return

        self.reader.download_dir = directory

        self.log_output.append(f"Папка для скачивания: {directory}")

    def start_processing(self):
        try:
            delimiter = self.delimiter_input.text().strip()

            if delimiter:
                self.reader.urls_delimiter = delimiter

            if not self.reader.download_dir:
                QMessageBox.warning(self, "Ошибка", "Сначала выберите папку")
                return

            data = self.reader.preparing_data()

            data = [
                {"url": item["url"], "file_name": item["file_name"]}
                for item in data
            ]

            self.progress.setEnabled(True)
            self.progress.setMaximum(len(data))
            self.progress.setValue(0)

            self.log_output.append("Начинаю скачивание файлов по ссылкам...\n")

            # ✅ СОЗДАЁМ worker
            self.worker = DownloadWorker(data, self.reader.download_dir)

            # ✅ ПОДКЛЮЧАЕМ ВСЕ СИГНАЛЫ СРАЗУ ПОСЛЕ СОЗДАНИЯ
            self.worker.progress.connect(self.update_progress)
            self.worker.log_item.connect(self.add_log_item)  # ← ВАЖНО
            self.worker.result.connect(self.show_result)
            self.worker.log.connect(self.add_error_log)
            # ✅ ЗАПУСК
            self.worker.start()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def add_log_item(self, url, success):
        color = "green" if success else "red"

        self.log_output.append(
            f'<span style="color:{color}">{url}</span>'
        )

    def go_back_to_preview(self):
        self.stack.setCurrentWidget(self.preview_screen)

    def update_progress(self, value):
        self.progress.setValue(value)

    def show_result(self, total, errors_count):
        success = total - errors_count

        self.log_output.append("")  # отступ

        self.log_output.append(
            f'<span style="color:black">'
            f'Готово. Успешно скачано файлов: {success} из {total}. '
            f'Ошибок: {errors_count}.'
            f'</span>'
        )

    def add_error_log(self, text):
        self.log_output.append(
            f'<span style="color:black">{text}</span>'
        )

    def update_headers_option(self):
        self.reader.headers_column = self.radio_skip.isChecked()

class DownloadWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    finished = Signal()
    log_item = Signal(str, bool)  # (url, success)
    result = Signal(int, int)  # total, errors_count

    def __init__(self, data, download_dir):
        super().__init__()
        self.data = data
        self.download_dir = download_dir

    def run(self):
        asyncio.run(self.async_run())

    async def async_run(self):
        downloader = FileDownloader()
        downloader.set_download_dir(self.download_dir)

        total = len(self.data)
        downloader.log_callback = lambda url, ok: self.log_item.emit(url, ok)

        async def monitor():
            """Отслеживание прогресса"""
            while downloader.process_items_count < total:
                self.progress.emit(downloader.process_items_count)
                await asyncio.sleep(0.1)

        monitor_task = asyncio.create_task(monitor())

        await downloader.download_files(self.data)

        monitor_task.cancel()

        # финальный прогресс
        self.progress.emit(total)

        total = downloader.total_items_count
        errors_count = len(downloader.errors)
        self.result.emit(total, errors_count)

        if downloader.errors:
            for err in downloader.errors:
                self.log.emit(err)

