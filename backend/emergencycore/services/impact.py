"""Geometric exposure is distinct from observed or predicted damage."""
from shapely.geometry import shape, mapping
from shapely.validation import explain_validity
from werkzeug.exceptions import BadRequest
from .common import point
from .geospatial import assets, metric_transform, transform


def exposure(region_id, geometry):
    if not isinstance(geometry, dict) or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
        raise BadRequest('hazard_geometry must be a WGS84 Polygon or MultiPolygon')
    try:
        hazard = shape(geometry)
        if hazard.is_empty or not hazard.is_valid:
            raise ValueError(explain_validity(hazard))
        west, south, east, north = hazard.bounds
        point([west, south]); point([east, north])
    except (ValueError, TypeError, KeyError, IndexError):
        raise BadRequest('Invalid hazard polygon') from None
    project = metric_transform(region_id)
    polygon = transform(project, hazard)
    layer = assets(region_id)
    matches = []
    for feature in layer['features']:
        geom = transform(project, shape(feature['geometry']))
        if geom.intersects(polygon):
            matches.append({'asset_id': str(feature['id']), 'properties': feature['properties'],
                            'intersected_area_m2': round(geom.intersection(polygon).area, 2)})
    return {'evidence': 'Simulated', 'method': 'geometric_intersection',
            'hazard_evidence': 'Simulated', 'hazard_geometry': mapping(hazard), 'items': matches,
            'assets_scanned': len(layer['features']), 'layer_notice': layer.get('notice'),
            'notice': 'User-supplied hazard footprint. Intersection indicates modeled exposure, not damage or causation. No damage model was run.'}
