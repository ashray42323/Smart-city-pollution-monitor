"""
Zone Model
"""

from app.extensions import db


class Zone(db.Model):
    """Zone model representing a monitoring location"""
    __tablename__ = 'zones'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # Relationship to readings
    readings = db.relationship('PollutionReading', backref='zone', lazy=True)
    
    def __repr__(self):
        return f'<Zone {self.name}>'
