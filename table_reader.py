from pathlib import Path
import pandas as pd
import re
from files_downloader import DownloadableItemDict
from typing import List


class UniversalTableReader:
    """
    Universal Table Loader for reading files in CSV, XLS, and XLSX formats. The class is designed to extract data from
    tables where one column may contain URLs and another column may contain filenames.
    The prepared data can be used for subsequent file downloading.
    """

    def __init__(self, encoding="utf-8"):
        self.encoding: str = encoding # file encoding
        self.data_frame: pd.DataFrame or None = None   # pandas object is created when a file is read, and all interaction occurs with it.
        self.filenames_column_index: int or None = None # index of the column that contains the rows for generating the file name
        self.urls_column_index: int or None = None  # index of the column that contains the rows for generating the file name
        self.download_dir: str or None = None  # dir path for downloaded files
        self.urls_delimiter: str or None = None  # delimiter for cvs document
        self.headers_column: bool = True  # flag..True - continue first row.

    def read_file(self, file_path, **kwargs) -> None:

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = path.suffix.lower()

        if suffix == ".csv":
            self.data_frame = self._read_csv(path)

        elif suffix in [".xlsx", ".xls"]:
            self.data_frame = self._read_excel(path, **kwargs)

        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _read_excel(self, path, **kwargs):
        return pd.read_excel(path, engine="openpyxl", header=None, **kwargs)

    def _read_csv(self, path):
        separators = [",", ";", "\t", "|"]

        for sep in separators:
            # determine the necessary separator by selection
            try:
                df = pd.read_csv(path, sep=sep, encoding=self.encoding)

                # if more than 1 column — success
                if df.shape[1] > 1:
                    return df
            except Exception:
                continue

        # fallback
        return pd.read_csv(path, encoding=self.encoding)

    def preparing_data(self) -> List[DownloadableItemDict]:
        # Prepares data from user-defined columns.
        result = []

        if self.urls_column_index is None:
            raise ValueError("urls_column_index не задан")

        urls_column = self.data_frame.iloc[:, self.urls_column_index]

        if self.filenames_column_index is not None:
            filenames_column = self.data_frame.iloc[:, self.filenames_column_index]
        else:
            filenames_column = None

        start_i = 1 if self.headers_column else 0

        for i in range(start_i, len(urls_column)):
            urls_value = urls_column[i]

            if not isinstance(urls_value, str):
                continue

            if filenames_column is None:
                filenames_value = str(i)
            else:
                filenames_value = filenames_column[i]
                if not isinstance(filenames_value, str):
                    filenames_value = str(i)
            filenames_value = self.sanitize_filename(filenames_value)
            split_urls = [
                u.strip() for u in urls_value.split(self.urls_delimiter) if u.strip()
            ]

            for j, url in enumerate(split_urls):
                ext = Path(url).suffix
                filename = (
                    f"{filenames_value}_{j + 1}{ext}"
                    if len(split_urls) > 1
                    else f"{filenames_value}{ext}"
                )

                result.append({
                    "file_name": filename,
                    "url": url
                })

        return result

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        # регулярка для поиска запрещённых символов в имени файла
        pattern = r'[<>:"/\\|?*]'
        cleaned_filename = re.sub(pattern, ' ', filename)

        return cleaned_filename