import hashlib
from pathlib import Path
import pandas as pd

def sha256_file(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()

def read_csv(path):
    """Read fields as strings so identifiers and original values are preserved."""
    return pd.read_csv(path, dtype="string", keep_default_na=True)

def discover_csv_files(raw_dir):
    return sorted(Path(raw_dir).glob("*.csv"))
