"""
Coordinate Transformation API for Ghana
Flask + PyProj backend for transforming coordinates between WGS84, UTM,
Web Mercator and Ghana's national grids.

All coordinate reference systems use their official EPSG definitions, and
PyProj selects the most accurate datum transformation available. The accuracy
reported to the user comes from the EPSG metadata of the transformation that
was actually applied, not from hard-coded estimates.

Author: Selig Anyawon Amoak
"""

import csv
import io
import os
from functools import lru_cache
from typing import Dict, Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pyproj import CRS, Proj, Transformer
from pyproj.transformer import TransformerGroup

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# ---------------------------------------------------------------------------
# Coordinate reference systems (official EPSG definitions)
# ---------------------------------------------------------------------------
CRS_DEFINITIONS = {
    'WGS84': 'EPSG:4326',             # WGS 84 geographic (lon/lat, degrees)
    'UTM_30N': 'EPSG:32630',          # WGS 84 / UTM zone 30N (metres)
    'UTM_31N': 'EPSG:32631',          # WGS 84 / UTM zone 31N (metres)
    'GHANA_GRID': 'EPSG:2136',        # Accra / Ghana National Grid (Gold Coast feet)
    'GHANA_METRE_GRID': 'EPSG:25000', # Leigon / Ghana Metre Grid (metres)
    'WEB_MERCATOR': 'EPSG:3857',      # WGS 84 / Pseudo-Mercator (metres)
}

CRS_INFO = {
    'WGS84': {
        'name': 'World Geodetic System 1984',
        'type': 'Geographic',
        'units': 'Degrees',
        'epsg': 'EPSG:4326',
        'datum': 'WGS 84',
        'description': 'Global standard used by GPS/GNSS receivers and international mapping.',
    },
    'UTM_30N': {
        'name': 'WGS 84 / UTM Zone 30N',
        'type': 'Projected',
        'units': 'Metres',
        'epsg': 'EPSG:32630',
        'datum': 'WGS 84',
        'projection': 'Transverse Mercator (CM 3°W, k0 = 0.9996)',
        'description': 'UTM zone covering 6°W to 0°, which includes most of Ghana.',
    },
    'UTM_31N': {
        'name': 'WGS 84 / UTM Zone 31N',
        'type': 'Projected',
        'units': 'Metres',
        'epsg': 'EPSG:32631',
        'datum': 'WGS 84',
        'projection': 'Transverse Mercator (CM 3°E, k0 = 0.9996)',
        'description': 'UTM zone covering 0° to 6°E (the eastern strip of Ghana).',
    },
    'GHANA_GRID': {
        'name': 'Accra / Ghana National Grid',
        'type': 'Projected',
        'units': 'Gold Coast feet (1 ft = 0.3047997 m)',
        'epsg': 'EPSG:2136',
        'datum': 'Accra (War Office ellipsoid)',
        'projection': 'Transverse Mercator (lat0 4°40\'N, CM 1°W, k0 = 0.99975, FE 900 000 ft)',
        'description': "Ghana's legacy national grid used on topographic and cadastral maps.",
    },
    'GHANA_METRE_GRID': {
        'name': 'Leigon / Ghana Metre Grid',
        'type': 'Projected',
        'units': 'Metres',
        'epsg': 'EPSG:25000',
        'datum': 'Leigon (Clarke 1880 RGS ellipsoid)',
        'projection': 'Transverse Mercator (lat0 4°40\'N, CM 1°W, k0 = 0.99975, FE 274 319.51 m)',
        'description': 'Metric national grid on the Leigon datum.',
    },
    'WEB_MERCATOR': {
        'name': 'WGS 84 / Pseudo-Mercator',
        'type': 'Projected',
        'units': 'Metres',
        'epsg': 'EPSG:3857',
        'datum': 'WGS 84',
        'projection': 'Spherical Mercator',
        'description': 'Used by web maps (OpenStreetMap, Google Maps). Not suitable for measurement.',
    },
}

UTM_CENTRAL_MERIDIAN = {'UTM_30N': -3.0, 'UTM_31N': 3.0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@lru_cache(maxsize=64)
def get_transformer(source_crs: str, target_crs: str) -> Transformer:
    """Return a cached transformer. PyProj picks the most accurate available operation."""
    return Transformer.from_crs(
        CRS_DEFINITIONS[source_crs], CRS_DEFINITIONS[target_crs], always_xy=True
    )


@lru_cache(maxsize=64)
def get_transformer_group(source_crs: str, target_crs: str) -> TransformerGroup:
    """All candidate operations between two CRS, ordered best (most accurate) first."""
    return TransformerGroup(CRS_DEFINITIONS[source_crs], CRS_DEFINITIONS[target_crs], always_xy=True)


def pick_transformer(source_crs: str, target_crs: str, lon: float, lat: float) -> Transformer:
    """Pick the most accurate operation whose area of use contains the point.

    For example, Accra -> WGS 84 has an onshore variant (about 6 m) and offshore
    variants (about 25 m); the right one depends on where the point is.
    """
    group = get_transformer_group(source_crs, target_crs)
    for candidate in group.transformers:
        area = candidate.area_of_use
        if area is None or (area.west <= lon <= area.east and area.south <= lat <= area.north):
            return candidate
    return group.transformers[0] if group.transformers else get_transformer(source_crs, target_crs)


def get_utm_zone(longitude: float) -> str:
    """Return the UTM zone key for a longitude in Ghana."""
    return 'UTM_31N' if longitude >= 0 else 'UTM_30N'


def same_datum(source_crs: str, target_crs: str) -> bool:
    src = CRS(CRS_DEFINITIONS[source_crs]).geodetic_crs
    tgt = CRS(CRS_DEFINITIONS[target_crs]).geodetic_crs
    return src.datum == tgt.datum


def describe_accuracy(source_crs: str, target_crs: str, transformer: Transformer) -> Dict:
    """Describe accuracy from the EPSG metadata of the operation actually used."""
    if same_datum(source_crs, target_crs):
        return {
            'accuracy': 'Exact (mathematical conversion)',
            'accuracy_m': 0.0,
            'description': 'Both systems share the same datum, so only a map projection '
                           'conversion is applied. Numerical error is well below 1 mm.',
            'operation': transformer.description,
            'use_case': 'Engineering surveys, GIS, cadastral mapping',
        }
    acc = transformer.accuracy
    if acc is None or acc < 0:
        text = 'Unknown (no published accuracy for this datum shift)'
        acc_m = None
    else:
        text = f'About {acc:g} m (EPSG published accuracy of the datum transformation)'
        acc_m = acc
    return {
        'accuracy': text,
        'accuracy_m': acc_m,
        'description': 'The datums differ, so a datum transformation is applied. Its accuracy '
                       'is limited by the published transformation parameters. For survey-grade '
                       'work in Ghana, use locally determined parameters and control points.',
        'operation': transformer.description,
        'use_case': 'Mapping, GIS integration, approximate positioning on legacy grids',
    }


def to_wgs84(crs_key: str, x: float, y: float) -> Optional[Dict]:
    """Return lon/lat for map display."""
    if crs_key == 'WGS84':
        return {'lon': x, 'lat': y}
    lon, lat = get_transformer(crs_key, 'WGS84').transform(x, y)
    return {'lon': lon, 'lat': lat}


def decimal_to_dms(decimal_degrees: float, is_latitude: bool = True) -> Dict:
    """Convert decimal degrees to degrees, minutes, seconds."""
    direction = ('N' if decimal_degrees >= 0 else 'S') if is_latitude else ('E' if decimal_degrees >= 0 else 'W')
    value = abs(decimal_degrees)
    degrees = int(value)
    minutes_decimal = (value - degrees) * 60
    minutes = int(minutes_decimal)
    seconds = (minutes_decimal - minutes) * 60
    if round(seconds, 4) >= 60:  # carry rounding overflow (e.g. 59.99999")
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        degrees += 1
    return {
        'degrees': degrees,
        'minutes': minutes,
        'seconds': round(seconds, 4),
        'direction': direction,
        'formatted': f"{degrees}° {minutes}' {seconds:.4f}\" {direction}",
    }


def decimal_to_dm(decimal_degrees: float, is_latitude: bool = True) -> Dict:
    """Convert decimal degrees to degrees and decimal minutes."""
    direction = ('N' if decimal_degrees >= 0 else 'S') if is_latitude else ('E' if decimal_degrees >= 0 else 'W')
    value = abs(decimal_degrees)
    degrees = int(value)
    minutes = (value - degrees) * 60
    return {
        'degrees': degrees,
        'minutes': round(minutes, 6),
        'direction': direction,
        'formatted': f"{degrees}° {minutes:.6f}' {direction}",
    }


def format_coordinate(value: float, is_latitude: bool, format_type: str) -> Dict:
    result = {'decimal': round(value, 8)}
    if format_type == 'dms':
        result['dms'] = decimal_to_dms(value, is_latitude)
        result['formatted'] = result['dms']['formatted']
    elif format_type == 'dm':
        result['dm'] = decimal_to_dm(value, is_latitude)
        result['formatted'] = result['dm']['formatted']
    else:
        result['formatted'] = f"{value:.8f}°"
    return result


def utm_factors(zone: str, lon: float, lat: float) -> Dict:
    """Exact point scale factor and grid convergence from PyProj."""
    factors = Proj(CRS_DEFINITIONS[zone]).get_factors(lon, lat)
    return {
        'zone': zone,
        'central_meridian': UTM_CENTRAL_MERIDIAN[zone],
        'convergence': round(factors.meridian_convergence, 6),
        'scale_factor': round(factors.meridional_scale, 8),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/crs-info', methods=['GET'])
def get_crs_info():
    return jsonify(CRS_INFO)


@app.route('/api/transform', methods=['POST'])
def transform_coordinates():
    try:
        data = request.get_json(silent=True) or {}
        source_crs = data.get('source_crs')
        target_crs = data.get('target_crs')
        coordinates = data.get('coordinates') or {}
        output_format = data.get('format', 'decimal')

        if not source_crs or not target_crs or not coordinates:
            return jsonify({'error': 'Missing required parameters'}), 400

        if source_crs == 'WGS84':
            x, y = coordinates.get('lon'), coordinates.get('lat')
        else:
            x, y = coordinates.get('x'), coordinates.get('y')
        if x is None or y is None:
            return jsonify({'error': 'Invalid coordinate values'}), 400
        x, y = float(x), float(y)

        # Automatic UTM zone selection (needs a longitude)
        if target_crs == 'UTM_AUTO':
            lon = x if source_crs == 'WGS84' else to_wgs84(source_crs, x, y)['lon']
            target_crs = get_utm_zone(lon)

        if source_crs not in CRS_DEFINITIONS or target_crs not in CRS_DEFINITIONS:
            return jsonify({'error': 'Invalid CRS specified'}), 400

        position = to_wgs84(source_crs, x, y)
        transformer = pick_transformer(source_crs, target_crs, position['lon'], position['lat'])
        tx, ty = transformer.transform(x, y)
        if tx == float('inf') or ty == float('inf'):
            return jsonify({'error': 'Coordinates are outside the valid area of the transformation'}), 400

        result = {
            'source': {'crs': source_crs, 'x': x, 'y': y, 'units': CRS_INFO[source_crs]['units']},
            'target': {'crs': target_crs, 'x': round(tx, 6), 'y': round(ty, 6),
                       'units': CRS_INFO[target_crs]['units']},
        }

        if target_crs == 'WGS84' and output_format != 'decimal':
            result['target']['longitude'] = format_coordinate(tx, False, output_format)
            result['target']['latitude'] = format_coordinate(ty, True, output_format)

        result['wgs84'] = position

        if target_crs in UTM_CENTRAL_MERIDIAN:
            result['metadata'] = utm_factors(target_crs, position['lon'], position['lat'])

        result['accuracy'] = describe_accuracy(source_crs, target_crs, transformer)
        return jsonify(result)

    except Exception as e:  # pragma: no cover - defensive
        return jsonify({'error': str(e)}), 500


@app.route('/api/transform-batch', methods=['POST'])
def transform_batch():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        source_crs = request.form.get('source_crs')
        target_crs = request.form.get('target_crs')
        if source_crs not in CRS_DEFINITIONS or target_crs not in CRS_DEFINITIONS:
            return jsonify({'error': 'Missing or invalid CRS parameters'}), 400

        stream = io.StringIO(file.stream.read().decode('utf-8-sig'), newline=None)
        reader = csv.DictReader(stream)
        def pick(row, *names):
            lowered = {k.strip().lower(): v for k, v in row.items() if k}
            for name in names:
                value = lowered.get(name)
                if value not in (None, ''):
                    return float(value)
            raise ValueError(f"missing column (expected one of: {', '.join(names)})")

        results, errors, accuracies = [], [], set()
        for idx, row in enumerate(reader, start=1):
            try:
                if source_crs == 'WGS84':
                    x = pick(row, 'lon', 'longitude', 'x')
                    y = pick(row, 'lat', 'latitude', 'y')
                else:
                    x = pick(row, 'x', 'easting', 'e')
                    y = pick(row, 'y', 'northing', 'n')
                position = to_wgs84(source_crs, x, y)
                transformer = pick_transformer(source_crs, target_crs, position['lon'], position['lat'])
                tx, ty = transformer.transform(x, y)
                accuracy = describe_accuracy(source_crs, target_crs, transformer)
                out = dict(row)
                out['transformed_x'] = round(tx, 6)
                out['transformed_y'] = round(ty, 6)
                out['target_crs'] = target_crs
                out['accuracy_m'] = accuracy['accuracy_m']
                accuracies.add(accuracy['accuracy'])
                results.append(out)
            except Exception as e:
                errors.append({'row': idx, 'error': str(e)})

        return jsonify({
            'success': True,
            'total_processed': len(results),
            'errors': errors,
            'accuracy_summary': sorted(accuracies),
            'data': results,
        })

    except Exception as e:  # pragma: no cover - defensive
        return jsonify({'error': str(e)}), 500


@app.route('/api/validate', methods=['POST'])
def validate_coordinates():
    try:
        data = request.get_json(silent=True) or {}
        crs = data.get('crs')
        x, y = float(data.get('x')), float(data.get('y'))
        validation = {'valid': True, 'warnings': [], 'errors': []}

        if crs == 'WGS84':
            if not -180 <= x <= 180:
                validation['valid'] = False
                validation['errors'].append('Longitude must be between -180 and 180 degrees')
            if not -90 <= y <= 90:
                validation['valid'] = False
                validation['errors'].append('Latitude must be between -90 and 90 degrees')
            if not -3.5 <= x <= 1.5:
                validation['warnings'].append('Longitude outside Ghana (about 3.3°W to 1.2°E)')
            if not 4.5 <= y <= 11.5:
                validation['warnings'].append('Latitude outside Ghana (about 4.7°N to 11.2°N)')
        elif crs in ('UTM_30N', 'UTM_31N'):
            if not 160000 <= x <= 840000:
                validation['warnings'].append('Easting outside typical UTM zone range')
            if not 0 <= y <= 10000000:
                validation['warnings'].append('Northing outside Northern Hemisphere range')
        elif crs == 'GHANA_GRID':  # Gold Coast feet
            if not 0 <= x <= 1700000:
                validation['warnings'].append('Easting outside typical Ghana National Grid range (feet)')
            if not 0 <= y <= 2500000:
                validation['warnings'].append('Northing outside typical Ghana National Grid range (feet)')
        elif crs == 'GHANA_METRE_GRID':
            if not 0 <= x <= 520000:
                validation['warnings'].append('Easting outside typical Ghana Metre Grid range')
            if not 0 <= y <= 760000:
                validation['warnings'].append('Northing outside typical Ghana Metre Grid range')

        return jsonify(validation)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/accuracy-info', methods=['GET'])
def get_accuracy_info():
    """Accuracy of each supported datum transformation, taken from EPSG metadata."""
    info = {}
    accra_onshore = (-0.1870, 5.6037)
    for target in ('UTM_30N', 'GHANA_GRID', 'GHANA_METRE_GRID'):
        t = pick_transformer('WGS84', target, *accra_onshore)
        info[f'WGS84_to_{target}'] = describe_accuracy('WGS84', target, t)
    return jsonify(info)


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', port=5000)
