"""
Database Models for Smart City Pollution Monitoring
Defines User, Zone, and PollutionReading entities
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import Boolean
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    # Role-based access control flag
    is_admin = db.Column(Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Zone(db.Model):
    """Zone model representing different city areas"""
    __tablename__ = 'zones'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # Relationship to pollution readings
    readings = db.relationship('PollutionReading', backref='zone', lazy=True, 
                              cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Zone {self.name}>'

class PollutionReading(db.Model):
    """Pollution reading model for storing sensor data"""
    __tablename__ = 'pollution_readings'
    
    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer, db.ForeignKey('zones.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Pollution metrics
    pm25 = db.Column(db.Float, nullable=False)  # PM2.5 concentration (µg/m³)
    pm10 = db.Column(db.Float, nullable=False)  # PM10 concentration (µg/m³)
    noise_level = db.Column(db.Float)  # Noise level in decibels (dB)
    temperature = db.Column(db.Float)  # Temperature in Celsius
    aqi = db.Column(db.Integer)  # Air Quality Index (optional calculated field)
    
    def __repr__(self):
        return f'<PollutionReading Zone:{self.zone_id} PM2.5:{self.pm25} at {self.timestamp}>'


class Settings(db.Model):
    """Application-wide settings for thresholds and defaults"""
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    pm25_threshold = db.Column(db.Float, default=55.0, nullable=False)
    noise_threshold = db.Column(db.Float, default=80.0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Settings PM2.5:{self.pm25_threshold} Noise:{self.noise_threshold}>'