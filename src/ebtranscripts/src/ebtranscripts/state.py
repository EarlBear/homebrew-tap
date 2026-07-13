"""Per-file incremental state: byte offsets so only new transcript bytes are processed.

A session file is normally append-only; on each run we read from the stored offset to EOF.
We re-read from 0 (a rewrite happened) when ANY of:
  - the file shrank (size < offset),
  - its inode changed (rotation),
  - the content *up to the stored offset* changed — a `/rewind` can rewrite a transcript in
    place at a similar size, which the first two checks miss. We guard against it with a
    cheap hash of the last PREFIX_BYTES before the offset (the "rewind guard").
State is a single JSON file; writes are atomic (temp + replace).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

# Bytes hashed just before the offset to detect an in-place rewrite (rewind).
PREFIX_BYTES = 4096


@dataclass
class FileState:
    offset: int = 0
    size: int = 0
    inode: int = 0
    session_id: str = ""
    # Hash of the PREFIX_BYTES ending at `offset`. Empty for pre-guard state (treated as
    # "unknown" — we verify by re-reading when set, and backfill it on the next read).
    prefix_hash: str = ""


class State:
    def __init__(self, path: Path):
        self.path = path
        self.files: dict[str, FileState] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        for key, val in data.get("files", {}).items():
            self.files[key] = FileState(**val)

    def get(self, key: str) -> FileState:
        return self.files.get(key, FileState())

    def set(self, key: str, fs: FileState) -> None:
        self.files[key] = fs

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"files": {k: asdict(v) for k, v in self.files.items()}}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        os.replace(tmp, self.path)


def _prefix_hash(f, offset: int) -> str:
    """Hash of the PREFIX_BYTES ending at `offset` (or from 0 if the file is shorter)."""
    lo = max(0, offset - PREFIX_BYTES)
    f.seek(lo)
    data = f.read(offset - lo)
    return hashlib.sha256(data).hexdigest()


def read_new_bytes(path: Path, prior: FileState) -> tuple[str, FileState]:
    """Return (new_text_since_offset, updated_state).

    Reads from prior.offset unless a rewrite is detected, in which case it re-reads from 0.
    A rewrite is: the file shrank, its inode changed, OR — the rewind guard — the content up
    to prior.offset no longer hashes to prior.prefix_hash (an in-place /rewind rewrite).
    new_text is decoded UTF-8 (errors replaced).
    """
    stat = path.stat()
    start = prior.offset
    rewrite = stat.st_size < prior.offset or stat.st_ino != prior.inode
    with path.open("rb") as f:
        # Rewind guard: only meaningful when we have a prior offset and a stored hash.
        if not rewrite and prior.offset > 0 and prior.prefix_hash:
            if _prefix_hash(f, prior.offset) != prior.prefix_hash:
                rewrite = True
        if rewrite:
            start = 0
        f.seek(start)
        chunk = f.read()
        new_size = f.tell()
        new_prefix = _prefix_hash(f, new_size)
    text = chunk.decode("utf-8", errors="replace")
    updated = FileState(
        offset=new_size,
        size=new_size,
        inode=stat.st_ino,
        session_id=prior.session_id,
        prefix_hash=new_prefix,
    )
    return text, updated


def read_full(path: Path) -> str:
    """Read the entire file (used by extract when we always want the whole session)."""
    return path.read_bytes().decode("utf-8", errors="replace")


def file_unchanged(path: Path, prior: FileState) -> bool:
    """True if the file has not changed since `prior` — so a delta-aware sync can skip it.

    Unchanged means: same size, same inode, and the same content-prefix hash (so an
    in-place /rewind that kept the size is still treated as changed). A prior with no
    recorded size/hash (never synced) is always considered changed.
    """
    if prior.size == 0 and not prior.prefix_hash:
        return False
    try:
        stat = path.stat()
    except OSError:
        return False
    if stat.st_size != prior.size or stat.st_ino != prior.inode:
        return False
    with path.open("rb") as f:
        return _prefix_hash(f, stat.st_size) == prior.prefix_hash
