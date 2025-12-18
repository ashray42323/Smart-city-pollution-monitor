import json
import pytest

from app import app
from models import db, User
from werkzeug.security import generate_password_hash


@pytest.fixture(autouse=True)
def app_context():
    with app.app_context():
        yield


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture()
def ensure_test_user():
    # Create a test user
    if not User.query.filter_by(username='testuser').first():
        u = User(username='testuser', email='test@example.com', password_hash=generate_password_hash('testpass'))
        db.session.add(u)
        db.session.commit()
    yield


def test_unauthenticated_redirects(client):
    r = client.get('/dashboard')
    assert r.status_code in (301, 302)

    r = client.get('/api/readings')
    assert r.status_code in (301, 302)


def test_login_and_endpoints(client, ensure_test_user, monkeypatch):
    # Patch external weather call to avoid network dependency
    def fake_weather(lat, lon):
        return {'error': False, 'hourly': [{'time': '2025-12-14T00:00', 'temperature_2m': 10, 'relativehumidity_2m': 80}], 'current': {'temperature_2m': 10}}

    def fake_realtime(city):
        return {'error': False, 'city': city, 'pm25': 10.0, 'pm10': 20.0, 'aqi': None, 'temperature': 10}

    monkeypatch.setattr('utils.get_weather_open_meteo', fake_weather)
    monkeypatch.setattr('utils.get_realtime_open_meteo', fake_realtime)

    # Also test missing realtime pm25 handling
    def fake_realtime_missing(city):
        return {'error': False, 'city': city, 'pm25': None, 'pm10': None, 'aqi': None, 'temperature': None}

    monkeypatch.setattr('utils.get_realtime_open_meteo', fake_realtime_missing)

    # perform login
    r = client.post('/login', data={'username': 'testuser', 'password': 'testpass'}, follow_redirects=True)
    assert r.status_code == 200
    assert 'Dashboard' in r.get_data(as_text=True)

    # dashboard access
    r = client.get('/dashboard')
    assert r.status_code == 200
    # New comparison section and chart canvas should be present
    body = r.get_data(as_text=True)
    assert 'Simulated vs Real-Time Comparison' in body
    assert 'id="simRealChart"' in body
    # EPA category badges should be visible
    assert 'EPA:' in body
    # Tooltips for percent diff and trend badges should be present
    assert 'data-bs-toggle="tooltip"' in body
    assert 'Percentage difference shows how much simulated data deviates from real-time data for the metric.' in body
    # Ensure new metric columns are present
    assert 'Temperature (°C)' in body
    assert 'Noise (dB)' in body

    # zone detail
    r = client.get('/zone/1')
    assert r.status_code == 200
    # ensure the page shows the zone name from the DB
    from models import Zone
    with app.app_context():
        zone1 = Zone.query.get(1)
        assert zone1 is not None
        assert zone1.name in r.get_data(as_text=True)

    # api readings
    r = client.get('/api/readings')
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        for key in ('zone_id', 'zone_name', 'pm25', 'pm10', 'temperature', 'timestamp', 'status'):
            assert key in item


def test_realtime_missing_shows_warning(client, ensure_test_user, monkeypatch):
    # Patch realtime to return None for pm25
    def fake_realtime_missing(city):
        return {'error': False, 'city': city, 'pm25': None, 'pm10': None, 'aqi': None, 'temperature': None}

    # Patch the function the app module uses (it imported get_realtime_open_meteo at import time)
    monkeypatch.setattr('app.get_realtime_open_meteo', fake_realtime_missing, raising=True)

    # login and get dashboard
    client.post('/login', data={'username': 'testuser', 'password': 'testpass'}, follow_redirects=True)
    r = client.get('/dashboard')
    body = r.get_data(as_text=True)
    assert 'No real-time PM2.5' in body


def test_admin_access_control(client, monkeypatch):
    # create a normal user and an admin user
    from models import User
    from werkzeug.security import generate_password_hash
    # Clean up if present
    normal = User.query.filter_by(username='normal').first()
    if not normal:
        normal = User(username='normal', email='normal@example.com', password_hash=generate_password_hash('pass'))
        db.session.add(normal)
    admin = User.query.filter_by(username='adminuser').first()
    if not admin:
        admin = User(username='adminuser', email='admin@example.com', password_hash=generate_password_hash('pass'), is_admin=True)
        db.session.add(admin)
    db.session.commit()

    # unauthenticated should redirect to login
    r = client.get('/admin/dashboard')
    assert r.status_code in (301, 302)

    # try access as normal user
    client.post('/login', data={'username': 'normal', 'password': 'pass'}, follow_redirects=True)
    r = client.get('/admin/dashboard')
    assert r.status_code == 403

    # login as admin
    client.get('/logout')
    client.post('/login', data={'username': 'adminuser', 'password': 'pass'}, follow_redirects=True)
    r = client.get('/admin/dashboard')
    assert r.status_code == 200


def test_test_admin_route(client):
    # ensure login
    from models import User
    from werkzeug.security import generate_password_hash
    if not User.query.filter_by(username='testuser').first():
        u = User(username='testuser', email='test@example.com', password_hash=generate_password_hash('testpass'))
        db.session.add(u)
        db.session.commit()

    # login as normal
    client.post('/login', data={'username': 'testuser', 'password': 'testpass'}, follow_redirects=True)
    r = client.get('/test-admin')
    assert r.status_code == 200
    data = r.get_json()
    assert 'is_admin' in data


def test_compare_zones_requires_login(client):
    """Test that compare-zones page requires authentication"""
    r = client.get('/compare-zones')
    assert r.status_code in (301, 302)


def test_compare_zones_page_loads(client, ensure_test_user, monkeypatch):
    """Test that compare-zones page loads with zone dropdowns"""
    # Patch external API calls
    def fake_realtime(city):
        return {'error': False, 'city': city, 'pm25': 25.0, 'pm10': 40.0, 'temperature': 20.0, 'noise': 60.0}
    
    monkeypatch.setattr('app.get_realtime_open_meteo', fake_realtime)
    
    # Login
    client.post('/login', data={'username': 'testuser', 'password': 'testpass'}, follow_redirects=True)
    
    # Access compare zones page
    r = client.get('/compare-zones')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    
    # Check page elements
    assert 'Zone Comparison' in body
    assert 'Select Zones to Compare' in body
    assert 'zone1_id' in body
    assert 'zone2_id' in body


def test_compare_zones_with_selection(client, ensure_test_user, monkeypatch):
    """Test compare-zones page with two zones selected shows comparison"""
    # Patch external API calls
    def fake_realtime(location):
        return {'error': False, 'pm25': 30.0, 'pm10': 50.0, 'temperature': 22.0, 'noise': 65.0}
    
    monkeypatch.setattr('app.get_realtime_open_meteo', fake_realtime)
    
    # Login
    client.post('/login', data={'username': 'testuser', 'password': 'testpass'}, follow_redirects=True)
    
    # Get zones from database
    from models import Zone
    zones = Zone.query.limit(2).all()
    if len(zones) >= 2:
        zone1_id = zones[0].id
        zone2_id = zones[1].id
        
        # Access compare zones with both selected
        r = client.get(f'/compare-zones?zone1_id={zone1_id}&zone2_id={zone2_id}')
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        
        # Check comparison elements are present
        assert 'Detailed Metric Comparison' in body
        assert 'PM2.5' in body
        assert 'PM10' in body
        assert 'Temperature' in body
        assert 'Noise Level' in body
        assert 'EPA Air Quality Index Legend' in body

