"""
AQI Calculation Services

EPA-style AQI calculations and status helpers.
"""


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


def get_temperature_status(temp_celsius):
    """Return a descriptive status for temperature."""
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
    """Return descriptive status for noise level in dB."""
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
