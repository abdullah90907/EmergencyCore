"""Consistent online SQLite backup including committed WAL transactions."""
import argparse
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emergencycore.config import load_config

parser = argparse.ArgumentParser()
parser.add_argument('destination', type=Path)
args = parser.parse_args()
config = load_config()
if config.get('DATABASE_URL'):
    raise SystemExit('PostgreSQL configured: use pg_dump with the direct connection, not the SQLite backup script')
source = Path(config['DATABASE_PATH']).resolve()
destination = args.destination.resolve()
if not source.exists() or source == destination or destination.exists():
    raise SystemExit('Source must exist; destination must be a new, different file')
destination.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(destination) as dst:
    src.backup(dst)
    if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise SystemExit('Backup integrity check failed')
print('Consistent backup created. Store an encrypted copy outside the service disk.')
