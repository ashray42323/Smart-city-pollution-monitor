"""
Pollution Data Simulation Service

Generates realistic pollution readings for all zones.
"""

import random
from datetime import datetime, timedelta
from app.extensions import db
from app.models import PollutionReading
from app.services.aqi import calculate_aqi


# Zone-specific characteristics for simulation
ZONE_CHARACTERISTICS = {
    'Kathmandu': {'pm25_base': 35, 'pm10_base': 50, 'noise_base': 75},
    'Bhaktapur': {'pm25_base': 25, 'pm10_base': 40, 'noise_base': 55},
    'Pokhara': {'pm25_base': 28, 'pm10_base': 42, 'noise_base': 58},
    'Gulmikot': {'pm25_base': 55, 'pm10_base': 80, 'noise_base': 85},
    'Lalitpur': {'pm25_base': 15, 'pm10_base': 25, 'noise_base': 45},
    'Biratnagar': {'pm25_base': 30, 'pm10_base': 45, 'noise_base': 65}
}

DEFAULT_CHARACTERISTICS = {'pm25_base': 30, 'pm10_base': 45, 'noise_base': 60}


def simulate_pollution_data(zones, num_readings=5):
    """
    Simulate realistic pollution readings for all zones.
    
    Args:
        zones: List of Zone objects
        num_readings: Number of readings to generate per zone
    """
    for zone in zones:
        characteristics = ZONE_CHARACTERISTICS.get(zone.name, DEFAULT_CHARACTERISTICS)
        
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
