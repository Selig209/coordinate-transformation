"""
Real-Time Coordinate Transformation API
A production-ready Flask application for coordinate transformations
Author: Geomatics Engineering Portfolio Project
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pyproj
from pyproj import Transformer
import pandas as pd
import io
import csv
import math
from typing import Dict, List, Tuple, Optional

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Define coordinate reference systems used in Ghana and internationally
CRS_DEFINITIONS = {
    'WGS84': 'EPSG:4326',  # World Geodetic System 1984
    'UTM_30N': 'EPSG:32630',  # UTM Zone 30N (Western Ghana)
    'UTM_31N': 'EPSG:32631',  # UTM Zone 31N (Eastern Ghana)
    'GHANA_GRID': '+proj=tmerc +lat_0=4.666666666666667 +lon_0=-1 +k=0.99975 +x_0=274319.51 +y_0=0 +ellps=clrk80 +towgs84=-199,32,322,0,0,0,0 +units=m +no_defs',  # Ghana National Grid (War Office)
    'WEB_MERCATOR': 'EPSG:3857',  # Web Mercator (for web maps)
}

# Accuracy information for different transformations
TRANSFORMATION_ACCURACY = {
    'WGS84_to_UTM': {
        'accuracy': '< 1 meter',
        'description': 'High accuracy transformation using standard UTM projection parameters',
        'use_case': 'Engineering surveys, cadastral mapping, GIS applications'
    },
    'WGS84_to_GHANA_GRID': {
        'accuracy': '1-5 meters',
        'description': 'Uses Helmert transformation with 7 parameters. Accuracy depends on the datum shift parameters',
        'use_case': 'Land surveying in Ghana, integration with national mapping systems'
    },
    'UTM_to_GHANA_GRID': {
        'accuracy': '1-5 meters',
        'description': 'Involves datum transformation via WGS84. Compound transformation may introduce small errors',
        'use_case': 'Converting international survey data to Ghana national system'
    },
    'GHANA_GRID_to_WGS84': {
        'accuracy': '1-5 meters',
        'description': 'Reverse Helmert transformation. Accuracy similar to forward transformation',
        'use_case': 'Publishing Ghana survey data in international standard format'
    }
}

def get_utm_zone(longitude: float) -> str:
    """Determine the appropriate UTM zone based on longitude"""
    if -6 <= longitude < 0:
        return 'UTM_30N'
    elif 0 <= longitude <= 6:
        return 'UTM_31N'
    else:
        # Default to UTM 30N for Ghana
        return 'UTM_30N'

def calculate_convergence(lat: float, lon: float, central_meridian: float) -> float:
    """Calculate grid convergence angle for UTM projection"""
    lat_rad = math.radians(lat)
    delta_lon = lon - central_meridian
    convergence = math.atan(math.tan(math.radians(delta_lon)) * math.sin(lat_rad))
    return math.degrees(convergence)

def calculate_scale_factor(lat: float, lon: float, central_meridian: float, k0: float = 0.9996) -> float:
    """Calculate point scale factor for UTM projection"""
    lat_rad = math.radians(lat)
    delta_lon_rad = math.radians(lon - central_meridian)
    
    # Simplified scale factor calculation
    a = 6378137.0  # WGS84 semi-major axis
    e2 = 0.00669438  # WGS84 first eccentricity squared
    
    N = a / math.sqrt(1 - e2 * math.sin(lat_rad)**2)
    T = math.tan(lat_rad)**2
    C = e2 * math.cos(lat_rad)**2 / (1 - e2)
    A = delta_lon_rad * math.cos(lat_rad)
    
    k = k0 * (1 + (1 + C) * A**2 / 2 + (5 - 4*T + 42*C + 13*C**2 - 28*e2) * A**4 / 24)
    
    return k

@app.route('/')
def index():
    """Serve the main application page"""
    return send_from_directory('static', 'index.html')

@app.route('/api/crs-info', methods=['GET'])
def get_crs_info():
    """Get information about available coordinate reference systems"""
    info = {
        'WGS84': {
            'name': 'World Geodetic System 1984',
            'type': 'Geographic',
            'units': 'Degrees',
            'description': 'Global standard for GPS and international mapping',
            'epsg': 'EPSG:4326'
        },
        'UTM_30N': {
            'name': 'UTM Zone 30 North',
            'type': 'Projected',
            'units': 'Meters',
            'description': 'Universal Transverse Mercator projection for Western Ghana (6°W - 0°)',
            'epsg': 'EPSG:32630'
        },
        'UTM_31N': {
            'name': 'UTM Zone 31 North',
            'type': 'Projected',
            'units': 'Meters',
            'description': 'Universal Transverse Mercator projection for Eastern Ghana (0° - 6°E)',
            'epsg': 'EPSG:32631'
        },
        'GHANA_GRID': {
            'name': 'Ghana National Grid (War Office)',
            'type': 'Projected',
            'units': 'Meters',
            'description': 'National coordinate system based on Clarke 1880 ellipsoid',
            'datum': 'Accra Datum',
            'projection': 'Transverse Mercator'
        },
        'WEB_MERCATOR': {
            'name': 'Web Mercator',
            'type': 'Projected',
            'units': 'Meters',
            'description': 'Spherical Mercator projection used by web mapping services',
            'epsg': 'EPSG:3857'
        }
    }
    return jsonify(info)

@app.route('/api/transform', methods=['POST'])
def transform_coordinates():
    """Transform coordinates between different CRS"""
    try:
        data = request.json
        
        # Extract parameters
        source_crs = data.get('source_crs')
        target_crs = data.get('target_crs')
        coordinates = data.get('coordinates')
        
        if not all([source_crs, target_crs, coordinates]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Get CRS definitions
        source_def = CRS_DEFINITIONS.get(source_crs)
        target_def = CRS_DEFINITIONS.get(target_crs)
        
        if not source_def or not target_def:
            return jsonify({'error': 'Invalid CRS specified'}), 400
        
        # Handle auto UTM zone selection for WGS84
        if source_crs == 'WGS84' and target_crs.startswith('UTM'):
            if target_crs == 'UTM_AUTO':
                lon = coordinates.get('lon') or coordinates.get('x')
                target_crs = get_utm_zone(lon)
                target_def = CRS_DEFINITIONS.get(target_crs)
        
        # Create transformer
        transformer = Transformer.from_crs(source_def, target_def, always_xy=True)
        
        # Extract coordinates based on source CRS type
        if source_crs == 'WGS84':
            x, y = coordinates.get('lon'), coordinates.get('lat')
        else:
            x, y = coordinates.get('x'), coordinates.get('y')
        
        if x is None or y is None:
            return jsonify({'error': 'Invalid coordinate values'}), 400
        
        # Perform transformation
        transformed_x, transformed_y = transformer.transform(x, y)
        
        # Prepare result
        result = {
            'source': {
                'crs': source_crs,
                'x': x,
                'y': y
            },
            'target': {
                'crs': target_crs,
                'x': round(transformed_x, 6),
                'y': round(transformed_y, 6)
            }
        }
        
        # Add additional information for specific transformations
        if target_crs in ['UTM_30N', 'UTM_31N']:
            central_meridian = -3 if target_crs == 'UTM_30N' else 3
            if source_crs == 'WGS84':
                result['metadata'] = {
                    'zone': target_crs,
                    'convergence': round(calculate_convergence(y, x, central_meridian), 6),
                    'scale_factor': round(calculate_scale_factor(y, x, central_meridian), 8)
                }
        
        # Add accuracy information
        transform_key = f"{source_crs}_to_{target_crs}"
        if transform_key in TRANSFORMATION_ACCURACY:
            result['accuracy'] = TRANSFORMATION_ACCURACY[transform_key]
        else:
            # Generic accuracy info
            result['accuracy'] = {
                'accuracy': '1-5 meters',
                'description': 'Standard transformation accuracy for properly defined CRS',
                'use_case': 'General GIS and surveying applications'
            }
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transform-batch', methods=['POST'])
def transform_batch():
    """Transform multiple coordinates from CSV file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        source_crs = request.form.get('source_crs')
        target_crs = request.form.get('target_crs')
        
        if not source_crs or not target_crs:
            return jsonify({'error': 'Missing CRS parameters'}), 400
        
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        # Get CRS definitions
        source_def = CRS_DEFINITIONS.get(source_crs)
        target_def = CRS_DEFINITIONS.get(target_crs)
        
        if not source_def or not target_def:
            return jsonify({'error': 'Invalid CRS specified'}), 400
        
        # Create transformer
        transformer = Transformer.from_crs(source_def, target_def, always_xy=True)
        
        results = []
        errors = []
        
        for idx, row in enumerate(csv_input, start=1):
            try:
                # Flexible column name detection
                if source_crs == 'WGS84':
                    x = float(row.get('lon') or row.get('longitude') or row.get('x') or row.get('X'))
                    y = float(row.get('lat') or row.get('latitude') or row.get('y') or row.get('Y'))
                else:
                    x = float(row.get('x') or row.get('X') or row.get('easting'))
                    y = float(row.get('y') or row.get('Y') or row.get('northing'))
                
                # Transform
                tx, ty = transformer.transform(x, y)
                
                # Keep original data and add transformed coordinates
                result_row = dict(row)
                result_row['transformed_x'] = round(tx, 6)
                result_row['transformed_y'] = round(ty, 6)
                result_row['target_crs'] = target_crs
                
                results.append(result_row)
                
            except Exception as e:
                errors.append({'row': idx, 'error': str(e)})
        
        return jsonify({
            'success': True,
            'total_processed': len(results),
            'errors': errors,
            'data': results
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/validate', methods=['POST'])
def validate_coordinates():
    """Validate coordinate values for a given CRS"""
    try:
        data = request.json
        crs = data.get('crs')
        x = data.get('x')
        y = data.get('y')
        
        validation = {'valid': True, 'warnings': [], 'errors': []}
        
        if crs == 'WGS84':
            if not (-180 <= x <= 180):
                validation['valid'] = False
                validation['errors'].append('Longitude must be between -180 and 180 degrees')
            if not (-90 <= y <= 90):
                validation['valid'] = False
                validation['errors'].append('Latitude must be between -90 and 90 degrees')
            
            # Ghana-specific warnings
            if not (-4 <= x <= 2):
                validation['warnings'].append('Longitude outside Ghana bounds (approximately -4° to 2°)')
            if not (4 <= y <= 12):
                validation['warnings'].append('Latitude outside Ghana bounds (approximately 4° to 12°)')
        
        elif crs in ['UTM_30N', 'UTM_31N']:
            if not (160000 <= x <= 840000):
                validation['warnings'].append('Easting outside typical UTM zone range')
            if not (0 <= y <= 10000000):
                validation['warnings'].append('Northing outside typical Northern hemisphere range')
        
        elif crs == 'GHANA_GRID':
            # Ghana Grid typical bounds
            if not (0 <= x <= 500000):
                validation['warnings'].append('Easting outside typical Ghana Grid range')
            if not (0 <= y <= 1000000):
                validation['warnings'].append('Northing outside typical Ghana Grid range')
        
        return jsonify(validation)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accuracy-info', methods=['GET'])
def get_accuracy_info():
    """Get detailed accuracy information for transformations"""
    return jsonify(TRANSFORMATION_ACCURACY)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
