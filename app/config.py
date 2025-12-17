"""
Configuration settings for Smart City Pollution Monitoring Dashboard
"""
import os


class Config:
    """Flask application configuration"""
    
    # Flask secret key for sessions
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-12345'
    
    # Database configuration
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'smart_city.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # OpenWeatherMap API configuration (legacy)
    API_KEY = os.environ.get('OPENWEATHER_API_KEY') or 'YOUR_API_KEY_HERE'
    API_BASE_URL = 'http://api.openweathermap.org/data/2.5/air_pollution'
    WEATHER_API_URL = 'http://api.openweathermap.org/data/2.5/weather'
    
    # Open-Meteo endpoints
    OPEN_METEO_BASE_URL = 'https://api.open-meteo.com/v1/forecast'
    OPEN_METEO_AIR_QUALITY_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality'
    OPEN_METEO_GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'
    
    # Application settings
    DEFAULT_CITY = 'Kathmandu'
    ALERT_THRESHOLD_PM25 = 55.0
    
    # Admin Credentials (session-based, separate from user auth)
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin123'


class TestConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
