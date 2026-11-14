import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_langgraph_config():
    config = json.loads((ROOT / 'langgraph.json').read_text(encoding='utf-8'))
    assert config['graphs']['wedding_planner'] == './app/graph.py:graph'
    assert (ROOT / 'app' / 'graph.py').is_file()


def test_database_integrity():
    db = ROOT / 'resources' / 'Chinook.db'
    with sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True) as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert conn.execute('SELECT COUNT(*) FROM Track').fetchone()[0] > 0


def test_gitignore_protects_secrets():
    ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
    assert '.env' in ignore.splitlines()
    assert '.venv/' in ignore.splitlines()
    assert (ROOT / '.env.example').is_file()
