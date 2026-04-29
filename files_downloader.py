"""
Asynchronous File Downloader Module
===================================

This module provides an asynchronous file downloading utility that supports
batch processing, error handling, progress tracking, and logging callbacks.

The main class :class:`FileDownloader` allows downloading multiple files
concurrently with configurable batch sizes and timeout settings.

Typical usage example:

    downloader = FileDownloader()
    downloader.set_download_dir("./downloads")

    files_to_download = [
        {"url": "https://example.com/file1.pdf", "file_name": "doc1.pdf"},
        {"url": "https://example.com/file2.jpg", "file_name": "image2.jpg"},
    ]

    await downloader.download_files(files_to_download)

    if downloader.errors:
        print(f"Errors occurred: {downloader.errors}")
"""


import aiohttp
import aiofiles
import asyncio
import os
from typing import List, TypedDict


class DownloadableItemDict(TypedDict):
    """
    Typing class.
    Type hint dictionary for a single downloadable item.
    Attributes:
        url (str): The source URL of the file to download.
        file_name (str): The desired name for the saved file.
    """
    url: str
    file_name: str


class FileDownloader:
    """
    A class for asynchronous downloading of files from web links.
    The main method 'download_files' takes a list of dictionaries containing a web link/file name pair

    Attributes:
        path2download_dir (str | None): Absolute path to the download directory.
                                        Must be set via :meth:`set_download_dir` before downloading.

        errors (list): Collection of error messages accumulated during downloads.

        total_items_count (int): Total number of items scheduled for download.

        process_items_count (int): Number of items that have been processed.

        log_callback (Optional[Callable]): Callback function for download status updates.
                                        The function should accept (url: str, success: bool) as parameters.

        is_cancelled (bool): Flag to indicate if the download process has been cancelled.
    """

    __batch_size = 10  # limiting the number of file downloads per session

    def __init__(self):
        self.path2download_dir: str or None = None  # full path directory for downloaded files
        self.errors: list = []
        self.total_items_count: int = 0
        self.process_items_count: int = 0
        self.log_callback = None  # for displaying information in gui
        self.is_cancelled: bool = False  # flag to stop downloads

    def set_download_dir(self, path):
        full_path = os.path.abspath(path)  # convert to full path
        if not os.path.exists(full_path):
            os.makedirs(full_path)  # ✅ Fixed: use full_path instead of path
        self.path2download_dir = full_path

        return

    def __reset_counters(self):
        self.errors.clear()
        self.total_items_count = 0
        self.process_items_count = 0
        self.is_cancelled = False

        return

    def cancel(self):
        """
        Cancel the download process.
        Sets the is_cancelled flag to True, which will stop all ongoing downloads.
        """
        self.is_cancelled = True

    async def __download_file(self, session, url, file_name):
        """
        Download a single file from URL with cancellation support.

        Args:
            session: aiohttp ClientSession
            url (str): URL of the file to download
            file_name (str): Name to save the file as
        """
        # Check if cancellation was requested before starting
        if self.is_cancelled:
            return

        if not self.path2download_dir:
            raise ValueError('FileDownloader.path2download_dir is None')

        filepath = os.path.join(self.path2download_dir, file_name)

        try:
            async with session.get(url) as response:
                # Check for cancellation
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
                        # Check for cancellation during download
                        if self.is_cancelled:
                            self.process_items_count += 1
                            # Try to delete partially downloaded file
                            try:
                                if os.path.exists(filepath):
                                    os.remove(filepath)
                            except Exception:
                                pass
                            return

                        await f.write(chunk)

            # success (if not cancelled)
            if not self.is_cancelled and self.log_callback:
                self.log_callback(url, True)

        except asyncio.TimeoutError:
            self.errors.append(f"> {url} -> Timeout")
            if self.log_callback:
                self.log_callback(url, False)

        except asyncio.CancelledError:
            # Handle task cancellation gracefully
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
        Download multiple files with batch processing and cancellation support.

        Args:
            data (List[DownloadableItemDict]): List of dicts with 'url' and 'file_name'
        """
        self.__reset_counters()
        self.total_items_count = len(data)

        timeout = aiohttp.ClientTimeout(total=20)

        async def process_batch(batch: List[DownloadableItemDict]):
            """Create and run tasks for a batch of downloads"""
            async with aiohttp.ClientSession(timeout=timeout) as session:
                tasks = [self.__download_file(session, item['url'], item['file_name']) for item in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

        # split list into parts and execute them in portions
        batch_tasks = []
        for item in data:
            # Check for cancellation before processing each batch
            if self.is_cancelled:
                break

            batch_tasks.append(item)
            if len(batch_tasks) >= self.__batch_size:
                await process_batch(batch_tasks)
                batch_tasks = []

        # Process remaining items
        if batch_tasks and not self.is_cancelled:
            await process_batch(batch_tasks)

        return