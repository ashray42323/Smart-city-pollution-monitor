"""
Utility functions for Smart City Pollution Monitoring
Includes data simulation and external API integration
"""

import logging
import random
from datetime import datetime, timedelta
import requests
import os
from models import db, PollutionReading
from config import Config
from functools import wraps
from flask import abort
from flask_login import current_user, login_required

# Logger for utils module
logger = logging.getLogger(__name__)
logger.debug("utils module loaded from %s", __file__)


def simulate_pollution_data(zones, num_readings=5):
    """
    Simulate realistic pollution readings for all zones
    """
    zone_characteristics = {
        'Kathmandu': {'pm25_base': 35, 'pm10_base': 50, 'noise_base': 75},
        'Bhaktapur': {'pm25_base': 25, 'pm10_base': 40, 'noise_base': 55},
        'Pokhara': {'pm25_base': 28, 'pm10_base': 42, 'noise_base': 58},
        'Gulmikot': {'pm25_base': 55, 'pm10_base': 80, 'noise_base': 85},
        'Lalitpur': {'pm25_base': 15, 'pm10_base': 25, 'noise_base': 45},
        'Biratnagar': {'pm25_base': 30, 'pm10_base': 45, 'noise_base': 65}
    }
    for zone in zones:
        characteristics = zone_characteristics.get(zone.name, {
            'pm25_base': 30,
            'pm10_base': 45,
            'noise_base': 60
        })

        for i in range(num_readings):
            timestamp = datetime.utcnow() - timedelta(minutes=10 * (num_readings - i - 1))

            # Simulate time-of-day effect
            hour = timestamp.hour
            time_factor = 1.0
            if 7 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
                time_factor = 1.3
            elif 22 <= hour or hour <= 5:  # Night time
                time_factor = 0.7
            
            # Generate PM2.5 with variation
            pm25 = characteristics['pm25_base'] * time_factor + random.uniform(-10, 15)
            pm25 = max(5, pm25)
            
            # Generate PM10
            pm10 = pm25 * random.uniform(1.5, 2.0) + random.uniform(-5, 10)
            pm10 = max(10, pm10)
            
            # Generate noise level
            noise_level = characteristics['noise_base'] + random.uniform(-10, 10)
            noise_level = max(40, min(100, noise_level))
            
            # Generate temperature
            base_temp = 20
            temp = base_temp + random.uniform(-5, 15)
            
            reading = PollutionReading(
                zone_id=zone.id,
                timestamp=timestamp,
                pm25=round(pm25, 2),
                pm10=round(pm10, 2),
                noise_level=round(noise_level, 1),
                temperature=round(temp, 1),
                aqi=calculate_aqi(pm25)
            )
            
            db.session.add(reading)
        
    db.session.commit()
    print(f"Simulated {num_readings} readings for {len(zones)} zones")

def calculate_aqi(pm25):
    """Calculate AQI from PM2.5 value using EPA formula"""
    
    breakpoints = [
        (0, 12.0, 0, 50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300),
        (250.5, 350.4, 301, 400),
        (350.5, 500.4, 401, 500)
    ]
    
    for bp_lo, bp_hi, aqi_lo, aqi_hi in breakpoints:
        if bp_lo <= pm25 <= bp_hi:
            aqi = ((aqi_hi - aqi_lo) / (bp_hi - bp_lo)) * (pm25 - bp_lo) + aqi_lo
            return int(round(aqi))
    
    return 500

def calculate_aqi_status(pm25):
    """Get human-readable status from PM2.5 value"""
    
    if pm25 <= 12.0:
        return {
            'level': 'Good',
            'color': 'success',
            'description': 'Air quality is satisfactory'
        }
    elif pm25 <= 35.4:
        return {
            'level': 'Moderate',
            'color': 'warning',
            'description': 'Air quality is acceptable'
        }
    elif pm25 <= 55.4:
        return {
            'level': 'Unhealthy for Sensitive Groups',
            'color': 'orange',
            'description': 'Sensitive individuals should limit outdoor activity'
        }
    elif pm25 <= 150.4:
        return {
            'level': 'Unhealthy',
            'color': 'danger',
            'description': 'Everyone may experience health effects'
        }
    elif pm25 <= 250.4:
        return {
            'level': 'Very Unhealthy',
            'color': 'purple',
            'description': 'Health alert: serious effects possible'
        }
    else:
        return {
            'level': 'Hazardous',
            'color': 'dark',
            'description': 'Health warning of emergency conditions'
        }

def get_realtime_air_quality(city_name='Kathmandu'):
    """Fetch real-time air quality data from OpenWeatherMap API"""
    
    api_key = Config.API_KEY
    
    if not api_key or api_key == 'YOUR_API_KEY_HERE':
        return {
            'error': True,
            'message': 'API key not configured. App works with simulated data.',
            'pm25': 0,
            'pm10': 0,
            'aqi': 0,
            'temperature': 0
        }
    
    try:
        # Get coordinates
        geo_url = f'http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=1&appid={api_key}'
        geo_response = requests.get(geo_url, timeout=5)
        
        if geo_response.status_code != 200:
            raise Exception(f'Geocoding API error: {geo_response.status_code}')
        
        geo_data = geo_response.json()
        if not geo_data:
            raise Exception(f'City {city_name} not found')
        
        lat = geo_data[0]['lat']
        lon = geo_data[0]['lon']
        
        # Get air pollution data
        pollution_url = f'{Config.API_BASE_URL}?lat={lat}&lon={lon}&appid={api_key}'
        pollution_response = requests.get(pollution_url, timeout=5)
        
        if pollution_response.status_code != 200:
            raise Exception(f'Air pollution API error: {pollution_response.status_code}')
        
        pollution_data = pollution_response.json()
        
        # Get weather data
        weather_url = f'{Config.WEATHER_API_URL}?lat={lat}&lon={lon}&appid={api_key}&units=metric'
        weather_response = requests.get(weather_url, timeout=5)
        weather_data = weather_response.json() if weather_response.status_code == 200 else {}
        
        components = pollution_data['list'][0]['components']
        aqi = pollution_data['list'][0]['main']['aqi']
        
        return {
            'error': False,
            'city': city_name,
            'pm25': round(components.get('pm2_5', 0), 2),
            'pm10': round(components.get('pm10', 0), 2),
            'aqi': aqi,
            'temperature': round(weather_data.get('main', {}).get('temp', 0), 1),
            'description': weather_data.get('weather', [{}])[0].get('description', 'N/A'),
            'timestamp': datetime.utcnow()
        }
        
    except requests.exceptions.Timeout:
        return {
            'error': True,
            'message': 'API request timed out',
            'pm25': 0,
            'pm10': 0
        }
    except Exception as e:
        return {
            'error': True,
            'message': f'Error: {str(e)}',
            'pm25': 0,
            'pm10': 0
        }


def get_weather_open_meteo(lat, lon, hourly_vars=None, past_days=1):
    """Fetch weather data from Open-Meteo for given coordinates.

    Returns a dict with 'error' key on failure or:
      {
        'error': False,
        'latitude': lat,
        'longitude': lon,
        'hourly': [ {'time': ISO, 'temperature_2m': val, 'relativehumidity_2m': val, ...}, ... ],
        'current': { ... }
      }
    """

    if hourly_vars is None:
        hourly_vars = ["temperature_2m", "weathercode", "relativehumidity_2m"]

    url = 'https://api.open-meteo.com/v1/forecast'
    params = {
        'latitude': lat,
        'longitude': lon,
        'hourly': ','.join(hourly_vars),
        'past_days': past_days,
        'timezone': 'UTC'
    }

    try:
        resp = requests.get(url, params=params, timeout=6)
        if resp.status_code != 200:
            return {'error': True, 'message': f'Open-Meteo error {resp.status_code}'}

        data = resp.json()
        hourly = data.get('hourly', {})
        times = hourly.get('time', [])

        hourly_list = []
        for idx, t in enumerate(times):
            entry = {'time': t}
            for var in hourly_vars:
                values = hourly.get(var, [])
                entry[var] = values[idx] if idx < len(values) else None
            hourly_list.append(entry)

        current = hourly_list[-1] if hourly_list else {}

        return {
            'error': False,
            'latitude': data.get('latitude', lat),
            'longitude': data.get('longitude', lon),
            'hourly': hourly_list,
            'current': current
        }

    except requests.exceptions.Timeout:
        return {'error': True, 'message': 'Request timed out'}
    except Exception as e:
        return {'error': True, 'message': str(e)}


def get_realtime_open_meteo(location=None):
    """Get current air quality and weather from Open-Meteo APIs.

    Fetches:
      - PM2.5 and PM10 from the Air Quality API
      - Temperature from the Weather (Forecast) API

    Noise is ALWAYS simulated because no reliable public real-time noise API exists.

    `location` can be:
      - None (defaults to Config.DEFAULT_CITY)
      - string city name (e.g., 'Kathmandu')
      - tuple/list (lat, lon)
      - dict with keys 'lat'/'lon' or 'latitude'/'longitude'

    Returns a dict:
      {
        'pm25': float,
        'pm10': float,
        'temperature': float,
        'noise': float,
        'source': {
           'pm25': 'api' | 'simulated',
           'pm10': 'api' | 'simulated',
           'temperature': 'api' | 'simulated',
           'noise': 'simulated'
        },
        'city': str | None,
        'timestamp': ISO 8601 string,
        'error': False | True,
        'message': optional str
      }

    Fallback simulation rules (when API value is None):
      - PM10: pm25 * random(1.2, 1.8) if pm25 is available, else random(20, 80)
      - Temperature: random(10, 35) °C
      - Noise: random(55, 85) dB (always simulated - no public API)
    """

    if location is None:
        location = Config.DEFAULT_CITY

    # Initialize sources tracking
    sources = {
        'pm25': 'simulated',
        'pm10': 'simulated',
        'temperature': 'simulated',
        'noise': 'simulated'  # Noise is ALWAYS simulated - no reliable public API exists
    }

    try:
        # Resolve coordinates
        lat = lon = None
        city_name = None

        if isinstance(location, (list, tuple)) and len(location) >= 2:
            lat, lon = float(location[0]), float(location[1])
        elif isinstance(location, dict):
            lat = float(location.get('lat') or location.get('latitude')) if (location.get('lat') or location.get('latitude')) is not None else None
            lon = float(location.get('lon') or location.get('longitude')) if (location.get('lon') or location.get('longitude')) is not None else None
        elif isinstance(location, str):
            city_name = location
        else:
            city_name = str(location)

        # If city name provided, geocode it
        if city_name and (lat is None or lon is None):
            geourl = f"{Config.OPEN_METEO_GEOCODING_URL}?name={city_name}&count=1"
            gresp = requests.get(geourl, timeout=5)
            if gresp.status_code != 200:
                logger.debug('Geocoding failed with status %s', gresp.status_code)
                # Return fully simulated fallback
                return _build_simulated_fallback_result(city_name, sources, 'Geocoding failed')

            geo = gresp.json().get('results', [])
            if not geo:
                logger.debug('Geocoding returned no results for %s', city_name)
                return _build_simulated_fallback_result(city_name, sources, f'City {city_name} not found')

            lat = geo[0]['latitude']
            lon = geo[0]['longitude']
            city_name = geo[0].get('name') or city_name

        if lat is None or lon is None:
            logger.debug('No coordinates available for location %s', location)
            return _build_simulated_fallback_result(city_name, sources, 'No coordinates available')

        # ---------------------------------------------------------------------
        # 1. Fetch Air Quality data (PM2.5, PM10)
        # ---------------------------------------------------------------------
        pm25_api = None
        pm10_api = None
        pm25_time = None

        aq_params = {
            'latitude': lat,
            'longitude': lon,
            'hourly': 'pm2_5,pm10',
            'timezone': 'UTC'
        }
        try:
            aq_resp = requests.get(Config.OPEN_METEO_AIR_QUALITY_URL, params=aq_params, timeout=6)
            if aq_resp.status_code == 200:
                aq_data = aq_resp.json()
                hourly = aq_data.get('hourly', {})
                times = hourly.get('time', [])

                # Find the latest non-null pm2_5 value, searching from latest backwards
                if times:
                    pm25_list = hourly.get('pm2_5', [])
                    pm10_list = hourly.get('pm10', [])

                    # PM2.5: find latest non-null
                    for idx in range(len(times) - 1, -1, -1):
                        candidate = pm25_list[idx] if idx < len(pm25_list) else None
                        if candidate is not None:
                            pm25_api = float(candidate)
                            pm25_time = times[idx]
                            sources['pm25'] = 'api'
                            break

                    # PM10: find latest non-null
                    for idx in range(len(times) - 1, -1, -1):
                        candidate = pm10_list[idx] if idx < len(pm10_list) else None
                        if candidate is not None:
                            pm10_api = float(candidate)
                            sources['pm10'] = 'api'
                            break
            else:
                logger.debug('Air quality API returned status %s', aq_resp.status_code)
        except requests.exceptions.Timeout:
            logger.debug('Air quality API request timed out')
        except Exception as e:
            logger.debug('Air quality API error: %s', e)

        # ---------------------------------------------------------------------
        # 2. Fetch Weather data (Temperature)
        # ---------------------------------------------------------------------
        temperature_api = None

        weather_params = {
            'latitude': lat,
            'longitude': lon,
            'current_weather': 'true',
            'timezone': 'UTC'
        }
        try:
            weather_resp = requests.get(Config.OPEN_METEO_BASE_URL, params=weather_params, timeout=6)
            if weather_resp.status_code == 200:
                weather_data = weather_resp.json()
                current_weather = weather_data.get('current_weather', {})
                temp_val = current_weather.get('temperature')
                if temp_val is not None:
                    temperature_api = float(temp_val)
                    sources['temperature'] = 'api'
            else:
                logger.debug('Weather API returned status %s', weather_resp.status_code)
        except requests.exceptions.Timeout:
            logger.debug('Weather API request timed out')
        except Exception as e:
            logger.debug('Weather API error: %s', e)

        # ---------------------------------------------------------------------
        # 3. Apply fallbacks for missing values
        # ---------------------------------------------------------------------

        # PM2.5: If API failed, simulate a realistic value
        if pm25_api is not None:
            pm25_final = round(pm25_api, 2)
        else:
            # Simulate PM2.5 in a realistic urban range (15-80 µg/m³)
            pm25_final = round(random.uniform(15.0, 80.0), 2)
            sources['pm25'] = 'simulated'

        # PM10: If API failed, derive from PM2.5 or simulate
        if pm10_api is not None:
            pm10_final = round(pm10_api, 2)
        else:
            # PM10 is typically 1.2x to 1.8x of PM2.5 in urban environments
            pm10_final = round(pm25_final * random.uniform(1.2, 1.8), 2)
            sources['pm10'] = 'simulated'

        # Temperature: If API failed, simulate seasonal range
        if temperature_api is not None:
            temperature_final = round(temperature_api, 1)
        else:
            # Simulate temperature in a typical range (10-35 °C)
            temperature_final = round(random.uniform(10.0, 35.0), 1)
            sources['temperature'] = 'simulated'

        # Noise: ALWAYS simulated - no reliable public real-time noise API exists
        # Urban noise typically ranges from 55 dB (quiet residential) to 85 dB (busy traffic)
        noise_final = round(random.uniform(55.0, 85.0), 1)
        # sources['noise'] is already 'simulated'

        # ---------------------------------------------------------------------
        # 4. Build result
        # ---------------------------------------------------------------------
        timestamp_iso = pm25_time if pm25_time else datetime.utcnow().isoformat()

        result = {
            'error': False,
            'city': city_name if city_name else None,
            'pm25': pm25_final,
            'pm10': pm10_final,
            'temperature': temperature_final,
            'noise': noise_final,
            'source': sources,
            'timestamp': timestamp_iso
        }

        logger.debug('Realtime data for %s -> pm25=%s (%s), pm10=%s (%s), temp=%s (%s), noise=%s (%s)',
                     location,
                     result['pm25'], sources['pm25'],
                     result['pm10'], sources['pm10'],
                     result['temperature'], sources['temperature'],
                     result['noise'], sources['noise'])
        return result

    except requests.exceptions.Timeout:
        logger.exception('Request timed out for %s', location)
        return _build_simulated_fallback_result(city_name, sources, 'Request timed out')
    except Exception as e:
        logger.exception('Error fetching realtime data for %s: %s', location, e)
        return _build_simulated_fallback_result(city_name, sources, str(e))


def _build_simulated_fallback_result(city_name, sources, message):
    """Build a fully simulated fallback result when APIs fail completely.

    This ensures the dashboard always has data to display, even if all
    external API calls fail. All values will be marked as 'simulated'.
    """
    # Mark all sources as simulated
    fallback_sources = {
        'pm25': 'simulated',
        'pm10': 'simulated',
        'temperature': 'simulated',
        'noise': 'simulated'
    }

    # Generate realistic simulated values
    pm25_sim = round(random.uniform(15.0, 80.0), 2)
    pm10_sim = round(pm25_sim * random.uniform(1.2, 1.8), 2)
    temp_sim = round(random.uniform(10.0, 35.0), 1)
    noise_sim = round(random.uniform(55.0, 85.0), 1)

    return {
        'error': True,
        'message': message,
        'city': city_name,
        'pm25': pm25_sim,
        'pm10': pm10_sim,
        'temperature': temp_sim,
        'noise': noise_sim,
        'source': fallback_sources,
        'timestamp': datetime.utcnow().isoformat()
    }


def get_temperature_status(temp_celsius):
    """Return a descriptive status for temperature.

    Categories (simple, illustrative):
      - Cool: <= 15°C
      - Normal: 15 < temp <= 25°C
      - Hot: > 25°C

    Returns a dict with level, color (Bootstrap), and description.
    """
    if temp_celsius is None:
        return {'level': 'No Data', 'color': 'secondary', 'description': 'Temperature data not available'}
    try:
        t = float(temp_celsius)
    except Exception:
        return {'level': 'No Data', 'color': 'secondary', 'description': 'Invalid temperature value'}

    if t <= 15.0:
        return {'level': 'Cool', 'color': 'info', 'description': 'Temperature is relatively cool'}
    if t <= 25.0:
        return {'level': 'Normal', 'color': 'success', 'description': 'Temperature is in the normal range'}
    return {'level': 'Hot', 'color': 'danger', 'description': 'Temperature is relatively high'}


def get_noise_status(noise_db):
    """Return descriptive status for noise level in dB.

    Categories (illustrative):
      - Low: < 60 dB
      - Moderate: 60–75 dB
      - High: > 75 dB
    """
    if noise_db is None:
        return {'level': 'No Data', 'color': 'secondary', 'description': 'Noise data not available'}
    try:
        n = float(noise_db)
    except Exception:
        return {'level': 'No Data', 'color': 'secondary', 'description': 'Invalid noise value'}

    if n < 60.0:
        return {'level': 'Low', 'color': 'success', 'description': 'Low ambient noise'}
    if n <= 75.0:
        return {'level': 'Moderate', 'color': 'warning', 'description': 'Moderate noise levels'}
    return {'level': 'High', 'color': 'danger', 'description': 'High noise levels'}



def admin_required(f):
    """Decorator to ensure the request is from an authenticated admin.
    
    Admin authentication is intentionally session-based and fully separated
    from user authentication to reflect real-world access control systems.
    
    Security:
    - Uses ONLY session['is_admin'] for validation
    - Does NOT use Flask-Login (login_user, current_user)
    - Admin must login via /admin/login to set session flag
    - Regular users cannot access admin routes even if logged in
    
    Returns: Redirect to /admin/login for non-admins
    """
    from flask import session, redirect, url_for
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Pure session-based check - NO Flask-Login dependency
        if not session.get('is_admin'):
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return wrapper