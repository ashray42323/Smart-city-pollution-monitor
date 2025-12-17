"""
Real-time Data Service

Integration with Open-Meteo APIs for weather and air quality data.
"""

import logging
import random
from datetime import datetime
import requests
from app.config import Config

logger = logging.getLogger(__name__)


def get_weather_open_meteo(lat, lon, hourly_vars=None, past_days=1):
    """Fetch weather data from Open-Meteo for given coordinates."""
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
    
    Noise is ALWAYS simulated because no reliable public real-time noise API exists.
    """
    if location is None:
        location = Config.DEFAULT_CITY
    
    sources = {
        'pm25': 'simulated',
        'pm10': 'simulated',
        'temperature': 'simulated',
        'noise': 'simulated'
    }
    
    try:
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
        
        # Geocode city name if needed
        if city_name and (lat is None or lon is None):
            geourl = f"{Config.OPEN_METEO_GEOCODING_URL}?name={city_name}&count=1"
            gresp = requests.get(geourl, timeout=5)
            if gresp.status_code != 200:
                return _build_simulated_fallback_result(city_name, sources, 'Geocoding failed')
            
            geo = gresp.json().get('results', [])
            if not geo:
                return _build_simulated_fallback_result(city_name, sources, f'City {city_name} not found')
            
            lat = geo[0]['latitude']
            lon = geo[0]['longitude']
            city_name = geo[0].get('name') or city_name
        
        if lat is None or lon is None:
            return _build_simulated_fallback_result(city_name, sources, 'No coordinates available')
        
        # Fetch Air Quality data
        pm25_api = pm10_api = None
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
                
                if times:
                    pm25_list = hourly.get('pm2_5', [])
                    pm10_list = hourly.get('pm10', [])
                    
                    for idx in range(len(times) - 1, -1, -1):
                        candidate = pm25_list[idx] if idx < len(pm25_list) else None
                        if candidate is not None:
                            pm25_api = float(candidate)
                            pm25_time = times[idx]
                            sources['pm25'] = 'api'
                            break
                    
                    for idx in range(len(times) - 1, -1, -1):
                        candidate = pm10_list[idx] if idx < len(pm10_list) else None
                        if candidate is not None:
                            pm10_api = float(candidate)
                            sources['pm10'] = 'api'
                            break
        except Exception as e:
            logger.debug('Air quality API error: %s', e)
        
        # Fetch Weather data
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
        except Exception as e:
            logger.debug('Weather API error: %s', e)
        
        # Apply fallbacks
        pm25_final = round(pm25_api, 2) if pm25_api is not None else round(random.uniform(15.0, 80.0), 2)
        if pm25_api is None:
            sources['pm25'] = 'simulated'
        
        pm10_final = round(pm10_api, 2) if pm10_api is not None else round(pm25_final * random.uniform(1.2, 1.8), 2)
        if pm10_api is None:
            sources['pm10'] = 'simulated'
        
        temperature_final = round(temperature_api, 1) if temperature_api is not None else round(random.uniform(10.0, 35.0), 1)
        if temperature_api is None:
            sources['temperature'] = 'simulated'
        
        noise_final = round(random.uniform(55.0, 85.0), 1)
        
        timestamp_iso = pm25_time if pm25_time else datetime.utcnow().isoformat()
        
        return {
            'error': False,
            'city': city_name if city_name else None,
            'pm25': pm25_final,
            'pm10': pm10_final,
            'temperature': temperature_final,
            'noise': noise_final,
            'source': sources,
            'timestamp': timestamp_iso
        }
    
    except requests.exceptions.Timeout:
        return _build_simulated_fallback_result(city_name, sources, 'Request timed out')
    except Exception as e:
        logger.exception('Error fetching realtime data: %s', e)
        return _build_simulated_fallback_result(city_name, sources, str(e))


def _build_simulated_fallback_result(city_name, sources, message):
    """Build a fully simulated fallback result when APIs fail."""
    fallback_sources = {
        'pm25': 'simulated',
        'pm10': 'simulated',
        'temperature': 'simulated',
        'noise': 'simulated'
    }
    
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


def get_realtime_air_quality(city_name='Kathmandu'):
    """Fetch real-time air quality data from OpenWeatherMap API (legacy)."""
    api_key = Config.API_KEY
    
    if not api_key or api_key == 'YOUR_API_KEY_HERE':
        return {
            'error': True,
            'message': 'API key not configured.',
            'pm25': 0,
            'pm10': 0,
            'aqi': 0,
            'temperature': 0
        }
    
    try:
        geo_url = f'http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=1&appid={api_key}'
        geo_response = requests.get(geo_url, timeout=5)
        
        if geo_response.status_code != 200:
            raise Exception(f'Geocoding API error: {geo_response.status_code}')
        
        geo_data = geo_response.json()
        if not geo_data:
            raise Exception(f'City {city_name} not found')
        
        lat = geo_data[0]['lat']
        lon = geo_data[0]['lon']
        
        pollution_url = f'{Config.API_BASE_URL}?lat={lat}&lon={lon}&appid={api_key}'
        pollution_response = requests.get(pollution_url, timeout=5)
        
        if pollution_response.status_code != 200:
            raise Exception(f'Air pollution API error: {pollution_response.status_code}')
        
        pollution_data = pollution_response.json()
        
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
        return {'error': True, 'message': 'API request timed out', 'pm25': 0, 'pm10': 0}
    except Exception as e:
        return {'error': True, 'message': f'Error: {str(e)}', 'pm25': 0, 'pm10': 0}
