"""Public provider adapters. Network I/O only in explicit ingestion, never app startup."""
import json
from datetime import datetime, timezone
import requests
from werkzeug.exceptions import BadGateway
from ..database import get_db
from .common import now

USGS_FEED = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson'
USGS_QUERY = 'https://earthquake.usgs.gov/fdsnws/event/1/query'


def fetch(url, params=None, headers=None):
    try:
        response = requests.get(url, params=params, headers=headers, timeout=(10, 45))
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        raise BadGateway('External data provider unavailable or returned invalid JSON') from None


def earthquake(feature, mode):
    props = feature['properties']
    coords = feature['geometry']['coordinates']
    stamp = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()
    products = {}
    for kind in ('shakemap', 'losspager'):
        products[kind] = [{'source': p.get('source'), 'update_time': p.get('updateTime'),
                           'properties': p.get('properties', {}),
                           'contents': {name: item.get('url') for name, item in p.get('contents', {}).items()}}
                          for p in props.get('products', {}).get(kind, []) if p.get('status') != 'DELETE']
    return dict(id='usgs:' + feature['id'], source='USGS', kind='earthquake', mode=mode,
                title=props.get('title') or props.get('place') or 'Earthquake',
                occurred_at=stamp(props['time']), fetched_at=now(), evidence='Official',
                verification=props.get('status') or 'unknown',
                payload={'geometry': feature['geometry'], 'magnitude': props.get('mag'),
                         'depth_km': coords[2] if len(coords) > 2 else None,
                         'source_url': props.get('url'), 'source_updated_at': stamp(props['updated']) if props.get('updated') else None,
                         'products': products, 'notice': 'Shaking and PAGER are estimates, not confirmed asset damage.'})


def store(items):
    db = get_db()
    with db:
        for item in items:
            previous = db.execute('SELECT payload,title,verification FROM disasters WHERE id=?', (item['id'],)).fetchone()
            payload = json.dumps(item['payload'], sort_keys=True)
            db.execute('''INSERT INTO disasters VALUES(:id,:source,:kind,:mode,:title,:occurred_at,:fetched_at,:evidence,:verification,:payload)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title,fetched_at=excluded.fetched_at,
                verification=excluded.verification,payload=excluded.payload''', dict(item, payload=payload))
            if not previous or (previous['payload'], previous['title'], previous['verification']) != (payload, item['title'], item['verification']):
                db.execute('INSERT INTO events(type,payload,created_at) VALUES(?,?,?)',
                           ('disaster.updated', json.dumps({'id': item['id'], 'source': item['source'], 'mode': item['mode']}), now()))


def ingest_usgs(historical=False):
    if historical:
        data = fetch(USGS_QUERY, {'format': 'geojson', 'eventid': 'ak018fcnsk91'})
        items = [earthquake(data, 'historical')]
    else:
        data = fetch(USGS_FEED)
        items = [earthquake(f, 'live') for f in data['features']]
    store(items)
    return len(items)


def ingest_nws(user_agent):
    data = fetch('https://api.weather.gov/alerts/active', headers={'User-Agent': user_agent, 'Accept': 'application/geo+json'})
    items = []
    for feature in data['features']:
        p = feature['properties']
        items.append(dict(id='nws:' + feature['id'], source='NWS', kind=p.get('event', 'weather'), mode='live',
            title=p.get('headline') or p.get('event', 'Weather alert'), occurred_at=p.get('sent') or now(),
            fetched_at=now(), evidence='Official', verification='provider-issued', payload={
                'geometry': feature.get('geometry'), 'severity': p.get('severity'), 'expires': p.get('expires'),
                'in_active_feed': True,
                'status': p.get('status'), 'message_type': p.get('messageType'),
                'area': p.get('areaDesc'), 'description': p.get('description'), 'instruction': p.get('instruction'),
                'source_url': feature['id']}))
    # A successful current snapshot retires alerts no longer present, even if their
    # previously advertised expiry is still in the future. Failed fetches retain cache.
    active_ids = {item['id'] for item in items}
    with get_db():
        for row in get_db().execute("SELECT id,payload FROM disasters WHERE source='NWS'"):
            if row['id'] not in active_ids:
                payload = json.loads(row['payload'])
                if payload.get('in_active_feed') is False:
                    continue
                payload['in_active_feed'] = False
                get_db().execute('UPDATE disasters SET payload=?,fetched_at=? WHERE id=?', (json.dumps(payload, sort_keys=True), now(), row['id']))
                get_db().execute('INSERT INTO events(type,payload,created_at) VALUES(?,?,?)',
                    ('disaster.updated', json.dumps({'id': row['id'], 'source': 'NWS', 'mode': 'live', 'in_active_feed': False}), now()))
        store(items)
    return len(items)


def tracked(source, function):
    db = get_db()
    attempted = now()
    try:
        count = function()
    except Exception:
        with db:
            db.execute('''INSERT INTO ingestion_status(source,attempted_at,error) VALUES(?,?,?)
                ON CONFLICT(source) DO UPDATE SET attempted_at=excluded.attempted_at,error=excluded.error''',
                       (source, attempted, 'Provider ingestion failed; cached data retained'))
        raise
    with db:
        db.execute('''INSERT INTO ingestion_status VALUES(?,?,?,NULL,?)
            ON CONFLICT(source) DO UPDATE SET attempted_at=excluded.attempted_at,succeeded_at=excluded.succeeded_at,error=NULL,item_count=excluded.item_count''',
                   (source, attempted, now(), count))
    return count
