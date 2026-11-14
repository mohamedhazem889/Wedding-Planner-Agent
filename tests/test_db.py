import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "resources" / "Chinook.db"


def test_music_catalog_exists():
    with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM Track").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM Genre").fetchone()[0] > 0
