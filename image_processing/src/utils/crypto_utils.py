# ===== src/utils/crypto_utils.py =====
import hashlib
from pathlib import Path
from typing import Tuple


def calculate_file_checksums(file_path: Path) -> Tuple[str, str]:
    """
    Calculate MD5 and SHA256 checksums for a file.

    Args:
        file_path: Path to the file

    Returns:
        Tuple of (md5_hash, sha256_hash)
    """
    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
            sha256_hash.update(chunk)

    return md5_hash.hexdigest(), sha256_hash.hexdigest()


def generate_file_id(file_path: Path, checksum: str) -> str:
    """
    Generate a unique file ID based on path and checksum.

    Args:
        file_path: Path to the file
        checksum: File checksum

    Returns:
        Unique file identifier
    """
    path_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
    checksum_short = checksum[:8]
    return f"{path_hash}_{checksum_short}"