# app/services/storage_service.py

import os
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


class AzureBlobStorage:
    """Azure Blob Storage wrapper"""

    def __init__(self, conn_str: str, container: str):
        from azure.storage.blob import BlobServiceClient

        self._service = BlobServiceClient.from_connection_string(conn_str)
        self._container = self._service.get_container_client(container)
        self._container_name = container

    def upload_bytes(self, storage_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        """
        Azure SDK의 upload_blob(content_settings=...)는
        azure.storage.blob.ContentSettings 객체를 기대
        """
        if not storage_key:
            raise ValueError("storage_key is required")

        from azure.storage.blob import ContentSettings

        blob = self._container.get_blob_client(storage_key)

        content_settings = (
            ContentSettings(content_type=content_type) if content_type else None
        )

        blob.upload_blob(
            data,
            overwrite=True,
            content_settings=content_settings, 
        )
        logger.info(f"[AzureBlobStorage] uploaded: {storage_key}")

    def download(self, storage_key: str) -> bytes:
        """스트리밍용 전체 파일 다운로드"""
        if not storage_key:
            raise ValueError("storage_key is required")
        blob = self._container.get_blob_client(storage_key)
        data = blob.download_blob().readall()
        logger.info(f"[AzureBlobStorage] downloaded: {storage_key}, size={len(data)}")
        return data
    
    # 파일 크기 조회
    def get_size(self, storage_key: str) -> int:
        if not storage_key:
            raise ValueError("storage_key is required")
        blob = self._container.get_blob_client(storage_key)
        props = blob.get_blob_properties()
        return int(props.size)

    # 범위 다운로드 (Azure 진짜 Range)
    def download_range(self, storage_key: str, start: int, end: int) -> bytes:
        if not storage_key:
            raise ValueError("storage_key is required")
        if start < 0 or end < start:
            raise ValueError(f"invalid range: {start}-{end}")

        blob = self._container.get_blob_client(storage_key)
        length = end - start + 1

        # Azure SDK: offset/length로 부분 다운로드 가능
        stream = blob.download_blob(offset=start, length=length)
        data = stream.readall()
        logger.info(f"[AzureBlobStorage] downloaded range: {storage_key}, {start}-{end}, size={len(data)}")
        return data

    def delete(self, storage_key: str) -> None:
        if not storage_key:
            return
        try:
            self._container.delete_blob(storage_key)
            logger.info(f"[AzureBlobStorage] deleted: {storage_key}")
        except Exception as e:
            logger.warning(f"[AzureBlobStorage] delete failed (ignored): {storage_key} err={e}")

    def delete_prefix(self, prefix: str) -> int:
        """prefix 아래 모든 blob 삭제"""
        if not prefix:
            return 0
        deleted = 0
        try:
            blobs = self._container.list_blobs(name_starts_with=prefix)
            for b in blobs:
                try:
                    self._container.delete_blob(b.name)
                    deleted += 1
                except Exception as e:
                    logger.warning(f"[AzureBlobStorage] delete blob failed (ignored): {b.name} err={e}")
            logger.info(f"[AzureBlobStorage] deleted {deleted} blobs under prefix={prefix}")
            return deleted
        except Exception as e:
            logger.error(f"[AzureBlobStorage] delete_prefix failed: prefix={prefix} err={e}")
            raise


class LocalStorage:
    """로컬 파일시스템 기반 스토리지"""

    def upload_bytes(self, storage_key: str, data: bytes, content_type: Optional[str] = None) -> None:
        os.makedirs(os.path.dirname(storage_key), exist_ok=True)
        with open(storage_key, "wb") as f:
            f.write(data)
        logger.info(f"[LocalStorage] uploaded: {storage_key}")

    def download(self, storage_key: str) -> bytes:
        """스트리밍용 전체 파일 다운로드"""
        if not os.path.exists(storage_key):
            raise FileNotFoundError(f"File not found: {storage_key}")
        with open(storage_key, "rb") as f:
            data = f.read()
        logger.info(f"[LocalStorage] downloaded: {storage_key}, size={len(data)}")
        return data
    
    # 파일 크기
    def get_size(self, storage_key: str) -> int:
        if not os.path.exists(storage_key):
            raise FileNotFoundError(f"File not found: {storage_key}")
        return os.path.getsize(storage_key)

    # 범위 읽기
    def download_range(self, storage_key: str, start: int, end: int) -> bytes:
        if not os.path.exists(storage_key):
            raise FileNotFoundError(f"File not found: {storage_key}")
        if start < 0 or end < start:
            raise ValueError(f"invalid range: {start}-{end}")
        with open(storage_key, "rb") as f:
            f.seek(start)
            return f.read(end - start + 1)

    def delete(self, storage_key: str) -> None:
        if not storage_key:
            return
        try:
            if os.path.exists(storage_key):
                os.remove(storage_key)
                logger.info(f"[LocalStorage] deleted file: {storage_key}")
        except Exception as e:
            logger.error(f"[LocalStorage] delete failed: {storage_key} err={e}")
            raise

    def delete_prefix(self, prefix: str) -> int:
        # 로컬에서는 디렉토리 통째로 삭제 (간단한 구현)
        import shutil
        if os.path.exists(prefix) and os.path.isdir(prefix):
            shutil.rmtree(prefix)
            logger.info(f"[LocalStorage] deleted directory: {prefix}")
            return 1
        return 0


def get_storage():
    backend = settings.storage_backend

    if backend == "local":
        return LocalStorage()

    if backend == "azure":
        return AzureBlobStorage(
            conn_str=settings.azure_storage_connection_string,
            container=settings.azure_storage_container,
        )

    raise RuntimeError(f"Invalid STORAGE_BACKEND={backend}")