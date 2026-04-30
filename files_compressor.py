from typing import Optional
import zipfile
import os
from pathlib import Path


class Compressor:

    def __init__(self):
        self.path2dir: Optional[str] = None
        self.pack: Optional[int] = None
        self.all_files_count: Optional[int] = None
        self.files_count: Optional[int] = 0
        self.archive_name: Optional[str] = None

    def _split_into_chunks_batch(self) -> list[list]:
        if not self.path2dir:
            raise ValueError('self.path2dir is None')
        file_list = os.listdir(self.path2dir)
        if not self.pack:
            raise ValueError('self.pack_files is None')
        self.all_files_count = len(file_list)

        if self.all_files_count <= self.pack:
            return [[os.path.join(self.path2dir, file_name) for file_name in file_list]]

        result = []
        start_i = 0
        stop_i = start_i + self.pack
        while start_i < self.all_files_count:
            if stop_i > self.all_files_count:
                stop_i = self.all_files_count
            result.append([os.path.join(self.path2dir, file_name) for file_name in file_list[start_i: stop_i]])

            start_i += self.pack
            stop_i += self.pack
        return result

    def _pack_files(self, files:list, archive_name:str):
        with zipfile.ZipFile(os.path.join(self.path2dir, archive_name), 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files:
                # Добавляем файл в архив (сохраняя только имя файла)
                zipf.write(file_path, arcname=Path(file_path).name)

    def reset_values(self):
        self.path2dir: Optional[str] = None
        self.pack: Optional[int] = None
        self.all_files_count: Optional[int] = None
        self.files_count: Optional[int] = 0
        self.archive_name: Optional[str] = None

    def run(self):
        files: list[list] = self._split_into_chunks_batch()
        if len(files) == 1:
            archive_path = os.path.join(self.path2dir, f"{self.archive_name}.zip")
            self._pack_files(files[0], archive_path)
            self.reset_values()
            return
        for i in range(len(files)):
            archive_path = os.path.join(self.path2dir, f"{self.archive_name}_{str(i)}.zip")
            self._pack_files(files[i], archive_path)
        self.reset_values()
        return

