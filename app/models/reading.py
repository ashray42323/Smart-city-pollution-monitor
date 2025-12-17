"""
Pollution Reading Model
"""

from app.extensions import db


class PollutionReading(db.Model):
    """Pollution reading model for sensor data"""
    __tablename__ = 'pollution_readings'
    
    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer, db.ForeignKey('zones.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    pm25 = db.Column(db.Float, nullable=False)
    pm10 = db.Column(db.Float, nullable=False)
    noise_level = db.Column(db.Float)
    temperature = db.Column(db.Float)
    aqi = db.Column(db.Integer)
    
    def __repr__(self):
        return f'<PollutionReading Zone:{self.zone_id} PM2.5:{self.pm25}>'


class Settings(db.Model):
    """Application settings model"""
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    pm25_threshold = db.Column(db.Float, default=55.0)
    noise_threshold = db.Column(db.Float, default=80.0)
    
    def __repr__(self):
        return f'<Settings PM2.5:{self.pm25_threshold} Noise:{self.noise_threshold}>'
