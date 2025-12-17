"""
Configuration settings for Smart City Pollution Monitoring Dashboard
"""
import os

class Config:
    """Flask application configuration"""
    
    # Flask secret key for sessions (CHANGE THIS IN PRODUCTION!)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-12345'
    
    # Database configuration
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'smart_city.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # OpenWeatherMap API configuration (legacy - not used by frontend)
    # Get your free API key from: https://openweathermap.org/api
    API_KEY = os.environ.get('OPENWEATHER_API_KEY') or 'YOUR_API_KEY_HERE'
    API_BASE_URL = 'http://api.openweathermap.org/data/2.5/air_pollution'
    WEATHER_API_URL = 'http://api.openweathermap.org/data/2.5/weather'

    # Open-Meteo endpoints
    OPEN_METEO_BASE_URL = 'https://api.open-meteo.com/v1/forecast'
    OPEN_METEO_AIR_QUALITY_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality'
    OPEN_METEO_GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'
    
    # Application settings
    DEFAULT_CITY = 'Kathmandu'
    ALERT_THRESHOLD_PM25 = 55.0  # EPA Unhealthy threshold
    
    # ---------------------------------------------------------------------
    # Admin Credentials (for separate admin authentication)
    # Admin authentication is intentionally session-based and fully separated
    # from user authentication to reflect real-world access control systems.
    # ---------------------------------------------------------------------
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin123'