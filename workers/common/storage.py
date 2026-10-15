"""
CompressPro AI - Storage Layer & Blob Management
Adheres to Master Architecture Blueprint Section 15 & 16.
Provides safe object keys, local storage abstraction, and SHA-256 checksums.
"""

import os
import shutil
import hashlib
import uuid
from pathlib import Path
from typing import Optional, BinaryIO, Tuple
from abc import ABC, abstractmethod


class StorageInterface(ABC):
    @abstractmethod
    def save_stream(self, stream: BinaryIO, category: str = "quarantine") -> Tuple[str, str, int]:
        """Save stream and return (object_key, sha256_checksum, byte_count)"""
        pass

    @abstractmethod
    def save_file(self, local_source_path: str, category: str = "artifacts") -> Tuple[str, str, int]:
        """Save a local file into object storage and return (object_key, sha256_checksum, byte_count)"""
        pass

    @abstractmethod
    def get_file_path(self, object_key: str) -> Optional[str]:
        """Get absolute path to local cached or stored object"""
        pass

    @abstractmethod
    def delete(self, object_key: str) -> bool:
        """Delete object from storage"""
        pass

    @abstractmethod
    def exists(self, object_key: str) -> bool:
        """Check if object exists"""
        pass


class LocalDiskStorage(StorageInterface):
    """
    Local filesystem implementation of object storage.
    Follows private object prefix layout:
      storage_root/quarantine/
      storage_root/inputs/
      storage_root/artifacts/
      storage_root/temp/
    """
    def __init__(self, storage_root: Optional[str] = None):
        is_serverless = os.getenv("VERCEL") == "1" or os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
        if storage_root is None:
            if is_serverless:
                self.storage_root = Path("/tmp/storage_vault")
            else:
                base_dir = Path(__file__).resolve().parent.parent.parent
                self.storage_root = base_dir / "storage_vault"
        else:
            self.storage_root = Path(storage_root)

        try:
            for folder in ["quarantine", "inputs", "artifacts", "temp"]:
                (self.storage_root / folder).mkdir(parents=True, exist_ok=True)
        except Exception:
            self.storage_root = Path("/tmp/storage_vault")
            for folder in ["quarantine", "inputs", "artifacts", "temp"]:
                (self.storage_root / folder).mkdir(parents=True, exist_ok=True)

    def _generate_key(self, category: str, extension: str = "") -> str:
        unique_id = uuid.uuid4().hex
        ext = f".{extension.lstrip('.')}" if extension else ""
        return f"{category}/{unique_id}{ext}"

    def save_stream(self, stream: BinaryIO, category: str = "quarantine", extension: str = "") -> Tuple[str, str, int]:
        object_key = self._generate_key(category, extension)
        dest_path = self.storage_root / object_key
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        total_bytes = 0

        with open(dest_path, "wb") as f_out:
            while chunk := stream.read(65536):
                hasher.update(chunk)
                f_out.write(chunk)
                total_bytes += len(chunk)

        return object_key, hasher.hexdigest(), total_bytes

    def save_file(self, local_source_path: str, category: str = "artifacts") -> Tuple[str, str, int]:
        src = Path(local_source_path)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {local_source_path}")

        object_key = self._generate_key(category, src.suffix)
        dest_path = self.storage_root / object_key
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        total_bytes = 0

        with open(src, "rb") as f_in, open(dest_path, "wb") as f_out:
            while chunk := f_in.read(65536):
                hasher.update(chunk)
                f_out.write(chunk)
                total_bytes += len(chunk)

        return object_key, hasher.hexdigest(), total_bytes

    def get_file_path(self, object_key: str) -> Optional[str]:
        # Enforce path traversal protection
        normalized = Path(object_key).as_posix()
        if ".." in normalized or normalized.startswith("/"):
            raise ValueError(f"Invalid object key path traversal: {object_key}")

        target = (self.storage_root / normalized).resolve()
        if not str(target).startswith(str(self.storage_root.resolve())):
            raise PermissionError(f"Access outside storage root denied: {object_key}")

        return str(target) if target.exists() else None

    def delete(self, object_key: str) -> bool:
        path_str = self.get_file_path(object_key)
        if path_str and os.path.exists(path_str):
            os.remove(path_str)
            return True
        return False

    def exists(self, object_key: str) -> bool:
        path_str = self.get_file_path(object_key)
        return path_str is not None and os.path.exists(path_str)


# Global storage singleton
default_storage = LocalDiskStorage()
