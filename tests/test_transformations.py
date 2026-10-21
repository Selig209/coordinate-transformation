"""
Geodetic validation tests.

Run with:  pip install pytest && pytest -q
"""
import io

import pytest
from pyproj import Transformer

from app import CRS_DEFINITIONS, app, decimal_to_dms

GOLD_COAST_FOOT = 0.3047997101815088  # metres per Gold Coast foot (EPSG unit 9094)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


def transform(client, src, tgt, coords, **extra):
    payload = {'source_crs': src, 'target_crs': tgt, 'coordinates': coords, **extra}
    response = client.post('/api/transform', json=payload)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


# --- Projection definitions checked against their defining parameters ---------

@pytest.mark.parametrize('zone, cm', [('UTM_30N', -3.0), ('UTM_31N', 3.0)])
def test_utm_central_meridian_on_equator_maps_to_false_origin(zone, cm):
    t = Transformer.from_crs('EPSG:4326', CRS_DEFINITIONS[zone], always_xy=True)
    e, n = t.transform(cm, 0.0)
    assert e == pytest.approx(500000.0, abs=1e-6)
    assert n == pytest.approx(0.0, abs=1e-6)


def test_ghana_national_grid_origin_is_900000_feet_east():
    # Natural origin: 4°40'N, 1°W on the Accra datum (EPSG:4168); false easting 900 000 ft.
    t = Transformer.from_crs('EPSG:4168', CRS_DEFINITIONS['GHANA_GRID'], always_xy=True)
    e, n = t.transform(-1.0, 4 + 40 / 60)
    assert e == pytest.approx(900000.0, abs=1e-4)
    assert n == pytest.approx(0.0, abs=1e-4)


def test_ghana_metre_grid_origin():
    # Natural origin: 4°40'N, 1°W on the Leigon datum (EPSG:4250); false easting 274 319.51 m.
    t = Transformer.from_crs('EPSG:4250', CRS_DEFINITIONS['GHANA_METRE_GRID'], always_xy=True)
    e, n = t.transform(-1.0, 4 + 40 / 60)
    assert e == pytest.approx(274319.51, abs=1e-4)
    assert n == pytest.approx(0.0, abs=1e-4)


def test_ghana_grid_false_easting_matches_metre_value_in_feet():
    # 900 000 Gold Coast feet must equal 274 319.739 m (the EPSG:2136 definition).
    assert 900000 * GOLD_COAST_FOOT == pytest.approx(274319.739163, abs=1e-3)


# --- API behaviour --------------------------------------------------------------

@pytest.mark.parametrize('target', ['UTM_30N', 'UTM_31N', 'GHANA_GRID', 'GHANA_METRE_GRID', 'WEB_MERCATOR'])
def test_round_trip_through_api_is_sub_millimetre(client, target):
    lon, lat = -0.1870, 5.6037  # Accra
    fwd = transform(client, 'WGS84', target, {'lon': lon, 'lat': lat})
    back = transform(client, target, 'WGS84', {'x': fwd['target']['x'], 'y': fwd['target']['y']})
    # 1e-8 degrees is about 1 mm
    assert back['target']['x'] == pytest.approx(lon, abs=1e-8)
    assert back['target']['y'] == pytest.approx(lat, abs=1e-8)


def test_same_datum_reported_as_exact(client):
    r = transform(client, 'WGS84', 'UTM_30N', {'lon': -1.6163, 'lat': 6.6885})
    assert r['accuracy']['accuracy_m'] == 0.0


def test_datum_shift_reports_published_accuracy(client):
    r = transform(client, 'WGS84', 'GHANA_GRID', {'lon': -1.6163, 'lat': 6.6885})
    assert r['accuracy']['accuracy_m'] and r['accuracy']['accuracy_m'] > 0
    assert 'feet' in r['target']['units'].lower()


def test_ghana_grid_output_is_in_feet_not_metres(client):
    # Accra lies roughly 90 km east of the false origin -> about 1.19 million feet easting.
    r = transform(client, 'WGS84', 'GHANA_GRID', {'lon': -0.1870, 'lat': 5.6037})
    assert 1_150_000 < r['target']['x'] < 1_250_000


def test_utm_auto_selects_zone_by_longitude(client):
    assert transform(client, 'WGS84', 'UTM_AUTO', {'lon': -1.6, 'lat': 6.7})['target']['crs'] == 'UTM_30N'
    assert transform(client, 'WGS84', 'UTM_AUTO', {'lon': 0.5, 'lat': 6.1})['target']['crs'] == 'UTM_31N'


def test_utm_metadata_scale_factor_on_central_meridian_is_k0(client):
    r = transform(client, 'WGS84', 'UTM_30N', {'lon': -3.0, 'lat': 6.0})
    assert r['metadata']['scale_factor'] == pytest.approx(0.9996, abs=1e-7)
    assert r['metadata']['convergence'] == pytest.approx(0.0, abs=1e-6)


def test_non_wgs84_pair_still_returns_map_position(client):
    r = transform(client, 'UTM_30N', 'GHANA_METRE_GRID', {'x': 811654.2, 'y': 620144.5})
    assert r['wgs84']['lon'] == pytest.approx(-0.187, abs=1e-4)


def test_invalid_crs_rejected(client):
    r = client.post('/api/transform', json={'source_crs': 'WGS84', 'target_crs': 'NOPE',
                                            'coordinates': {'lon': 0, 'lat': 0}})
    assert r.status_code == 400


def test_batch_csv(client):
    csv_data = 'lon,lat,name\n-0.1870,5.6037,Accra\n-1.6163,6.6885,Kumasi\nbad,row,x\n'
    r = client.post('/api/transform-batch', data={
        'file': (io.BytesIO(csv_data.encode()), 'points.csv'),
        'source_crs': 'WGS84', 'target_crs': 'UTM_30N'}, content_type='multipart/form-data')
    body = r.get_json()
    assert body['total_processed'] == 2
    assert len(body['errors']) == 1


def test_dms_rounding_does_not_produce_60_seconds():
    assert decimal_to_dms(5.999999999)['formatted'].startswith('6° 0\' 0.0000"')


def test_onshore_point_uses_6m_accra_transformation(client):
    r = transform(client, 'WGS84', 'GHANA_GRID', {'lon': -1.6163, 'lat': 6.6885})  # Kumasi
    assert r['accuracy']['accuracy_m'] == pytest.approx(6.0)


def test_offshore_point_uses_offshore_transformation(client):
    r = transform(client, 'WGS84', 'GHANA_GRID', {'lon': -2.9, 'lat': 4.5})  # Jubilee field area
    assert r['accuracy']['accuracy_m'] == pytest.approx(25.0)
