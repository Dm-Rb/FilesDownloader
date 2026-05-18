import aiohttp
import aiofiles
import asyncio
import os
from typing import List, TypedDict


class DownloadableItemDict(TypedDict):
    url: str
    file_name: str
    brand: str or None


class FileDownloader:
    """
    Asynchronous file downloader with optional brand-based subfolder support.
    """

    __batch_size = 10

    def __init__(self):
        self.path2download_dir: str or None = None
        self.errors: list = []
        self.total_items_count: int = 0
        self.process_items_count: int = 0
        self.log_callback = None
        self.is_cancelled: bool = False

    def set_download_dir(self, path: str):
        full_path = os.path.abspath(path)
        if not os.path.exists(full_path):
            os.makedirs(full_path)
        self.path2download_dir = full_path

    def __reset_counters(self):
        self.errors.clear()
        self.total_items_count = 0
        self.process_items_count = 0
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    async def __download_file(self, session, item: DownloadableItemDict):
        """
        Download single file (with optional brand folder).
        """
        if self.is_cancelled:
            return

        if not self.path2download_dir:
            raise ValueError("FileDownloader.path2download_dir is None")

        url = item["url"]
        file_name = item["file_name"]
        brand = item.get("brand")

        # -------- PATH LOGIC --------
        if brand:
            safe_brand = brand.strip().replace("/", "_")
            folder = os.path.join(self.path2download_dir, safe_brand)
            os.makedirs(folder, exist_ok=True)
            filepath = os.path.join(folder, file_name)
        else:
            filepath = os.path.join(self.path2download_dir, file_name)

        try:
            async with session.get(url) as response:

                if self.is_cancelled:
                    self.process_items_count += 1
                    return

                if response.status != 200:
                    msg = f"{url} -> HTTP {response.status}"
                    self.errors.append(f"> {msg}")

                    if self.log_callback:
                        self.log_callback(url, False)

                    self.process_items_count += 1
                    return

                async with aiofiles.open(filepath, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024):

                        if self.is_cancelled:
                            self.process_items_count += 1
                            try:
                                if os.path.exists(filepath):
                                    os.remove(filepath)
                            except Exception:
                                pass
                            return

                        await f.write(chunk)

            if not self.is_cancelled and self.log_callback:
                self.log_callback(url, True)

        except asyncio.TimeoutError:
            self.errors.append(f"> {url} -> Timeout")
            if self.log_callback:
                self.log_callback(url, False)

        except asyncio.CancelledError:
            self.errors.append(f"> {url} -> Cancelled")
            if self.log_callback:
                self.log_callback(url, False)
            raise

        except Exception as e:
            self.errors.append(f"> {url} -> Exception: {e}")
            if self.log_callback:
                self.log_callback(url, False)

        finally:
            self.process_items_count += 1

    async def download_files(self, data: List[DownloadableItemDict]):
        """
        Download files in batches with cancellation support.
        """
        self.__reset_counters()
        self.total_items_count = len(data)

        timeout = aiohttp.ClientTimeout(total=20)

        async def process_batch(batch: List[DownloadableItemDict]):
            async with aiohttp.ClientSession(timeout=timeout) as session:
                tasks = [
                    self.__download_file(session, item)
                    for item in batch
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

        batch_tasks = []

        for item in data:
            if self.is_cancelled:
                break

            batch_tasks.append(item)

            if len(batch_tasks) >= self.__batch_size:
                await process_batch(batch_tasks)
                batch_tasks = []

        if batch_tasks and not self.is_cancelled:
            await process_batch(batch_tasks)