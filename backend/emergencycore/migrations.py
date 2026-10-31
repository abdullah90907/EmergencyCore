"""Additive, transactional schema migrations preserving the original tables."""
from .database import connect, run_schema
from contextlib import closing


def migrate(app):
    with app.app_context(), closing(connect(migrations=True)) as db:
        run_schema(db, '''
        CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY, applied_at TEXT);
        CREATE TABLE IF NOT EXISTS region_datasets(
            region_id TEXT NOT NULL, layer TEXT NOT NULL, payload TEXT NOT NULL,
            updated_at TEXT NOT NULL, PRIMARY KEY(region_id,layer));
        CREATE TABLE IF NOT EXISTS disasters(
            id TEXT PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL, mode TEXT NOT NULL,
            title TEXT NOT NULL, occurred_at TEXT NOT NULL, fetched_at TEXT NOT NULL,
            evidence TEXT NOT NULL, verification TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ingestion_status(
            source TEXT PRIMARY KEY, attempted_at TEXT NOT NULL, succeeded_at TEXT,
            error TEXT, item_count INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS scenarios(
            id TEXT PRIMARY KEY, name TEXT NOT NULL, region_id TEXT NOT NULL,
            mode TEXT NOT NULL, disaster_id TEXT, graph_version TEXT NOT NULL,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS observations(
            id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, asset_id TEXT NOT NULL,
            state TEXT NOT NULL, evidence TEXT NOT NULL, verification TEXT NOT NULL,
            observed_at TEXT NOT NULL, recorded_at TEXT NOT NULL,
            source_url TEXT, note TEXT NOT NULL,
            FOREIGN KEY(scenario_id) REFERENCES scenarios(id));
        CREATE INDEX IF NOT EXISTS observation_timeline ON observations(scenario_id,observed_at,recorded_at);
        CREATE TABLE IF NOT EXISTS route_results(
            id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, created_at TEXT NOT NULL,
            payload TEXT NOT NULL, FOREIGN KEY(scenario_id) REFERENCES scenarios(id));
        CREATE TABLE IF NOT EXISTS traffic_snapshots(
            source_id TEXT PRIMARY KEY, fetched_at TEXT NOT NULL, payload TEXT NOT NULL);
        INSERT INTO schema_versions VALUES(1,CURRENT_TIMESTAMP) ON CONFLICT(version) DO NOTHING;
        ''')
