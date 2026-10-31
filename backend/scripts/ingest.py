"""Run explicitly or as a separate periodic worker; never inside Flask workers."""
import argparse
import json
from pathlib import Path
import signal
import sys
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emergencycore import create_app
from emergencycore.api.intelligence import ingest_source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=['usgs', 'nws', 'anchorage-2018', 'alaska511', 'live'], default='live')
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    app = create_app()
    stopped = Event()
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    while not stopped.is_set():
        failures = 0
        for source in ['usgs', 'nws'] if args.source == 'live' else [args.source]:
            with app.app_context():
                try:
                    print(json.dumps({'source': source, 'imported': ingest_source(source)}), flush=True)
                except Exception as exc:
                    failures += 1
                    print(json.dumps({'source': source, 'error_type': type(exc).__name__, 'message': 'Ingestion failed; check ingestion/status. No cached data was fabricated.'}), flush=True)
        if not args.watch:
            return failures
        stopped.wait(max(60, int(app.config['INGEST_INTERVAL_SECONDS'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
