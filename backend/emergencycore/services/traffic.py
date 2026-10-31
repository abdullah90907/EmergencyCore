import json
from werkzeug.exceptions import ServiceUnavailable
from ..database import get_db
from .common import now
from .disasters import fetch
from .geospatial import nearest_edge


def ingest(key):
    if not key:
        raise ServiceUnavailable('Set ALASKA_511_API_KEY in backend/.env')
    rows = fetch('https://511.alaska.gov/api/v2/get/event', {'key': key, 'format': 'json'})
    if not isinstance(rows, list) or any(not isinstance(row, dict) or 'ID' not in row for row in rows):
        raise ValueError('Invalid Alaska 511 response')
    stamp = now()
    with get_db():
        get_db().execute('DELETE FROM traffic_snapshots')
        for row in rows:
            get_db().execute('INSERT INTO traffic_snapshots VALUES(?,?,?)', (str(row['ID']), stamp, json.dumps(row)))
        get_db().execute('INSERT INTO events(type,payload,created_at) VALUES(?,?,?)',
                         ('traffic.updated', json.dumps({'source': 'Alaska 511', 'count': len(rows)}), stamp))
    return len(rows)


def candidates(region_id):
    items = []
    for row in get_db().execute('SELECT * FROM traffic_snapshots'):
        item = json.loads(row['payload'])
        match = None
        if item.get('Latitude') is not None and item.get('Longitude') is not None:
            from werkzeug.exceptions import HTTPException
            try:
                match = nearest_edge(region_id, [item['Longitude'], item['Latitude']], 100)
            except HTTPException:
                pass
        items.append({'id': row['source_id'], 'fetched_at': row['fetched_at'], 'evidence': 'Official',
                      'source_url': 'https://511.alaska.gov/', 'event': item, 'matching': match,
                      'notice': 'Candidate edge match is unverified. Full closure flag alone is not auto-applied to routing.'})
    return items
