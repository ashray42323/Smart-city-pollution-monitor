"""
Services Package

Exports all services for easy importing.
"""

from app.services.aqi import calculate_aqi, calculate_aqi_status, get_temperature_status, get_noise_status
from app.services.simulation import simulate_pollution_data
from app.services.realtime import get_realtime_open_meteo, get_weather_open_meteo, get_realtime_air_quality

__all__ = [
    'calculate_aqi',
    'calculate_aqi_status',
    'get_temperature_status',
    'get_noise_status',
    'simulate_pollution_data',
    'get_realtime_open_meteo',
    'get_weather_open_meteo',
    'get_realtime_air_quality'
]
