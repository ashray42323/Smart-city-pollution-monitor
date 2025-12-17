"""
Smart City Pollution Monitoring - Application Factory

This module provides the Flask application factory pattern for creating
and configuring the application instance.
"""

from flask import Flask
from app.extensions import db, login_manager
from app.config import Config


def create_app(config_class=Config):
    """Create and configure the Flask application.
    
    Args:
        config_class: Configuration class to use (default: Config)
    
    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Register blueprints
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.dashboard import dashboard_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(dashboard_bp)
    
    # Context processor for admin flag
    @app.context_processor
    def inject_is_admin_flag():
        """Inject `is_admin` flag into templates based on SESSION."""
        from flask import session
        return dict(is_admin=session.get('is_admin', False))
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Template filter for AQI status
    @app.template_filter('aqi_status')
    def aqi_status_filter(pm25_value):
        from app.services.aqi import calculate_aqi_status
        return calculate_aqi_status(pm25_value)
    
    # Create database tables
    with app.app_context():
        import os
        os.makedirs('instance', exist_ok=True)
        db.create_all()
        _ensure_default_data(app)
    
    return app


def _ensure_default_data(app):
    """Ensure default zones and settings exist."""
    from app.models import Zone, Settings
    from sqlalchemy import text
    
    # Ensure is_admin column exists (for older DBs)
    try:
        with db.engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info('users');"))
            cols = [r[1] for r in res.fetchall()]
            if 'is_admin' not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0;"))
                print('Added is_admin column to users table')
    except Exception as e:
        print('Could not modify users table schema:', e)
    
    # Ensure Settings table has at least one row
    if not Settings.query.first():
        try:
            s = Settings(pm25_threshold=55.0, noise_threshold=80.0)
            db.session.add(s)
            db.session.commit()
            print('Created default settings row')
        except Exception as e:
            db.session.rollback()
            print('Could not create default settings row:', e)
    
    # Ensure default city zones exist
    expected_zones = [
        {'name': 'Kathmandu',  'description': 'Capital city',       'latitude': 27.7017, 'longitude': 85.3206},
        {'name': 'Bhaktapur',  'description': 'Historic city',      'latitude': 27.6730, 'longitude': 85.4300},
        {'name': 'Pokhara',    'description': 'Lakeside city',      'latitude': 28.2669, 'longitude': 83.9685},
        {'name': 'Gulmikot',   'description': 'Rural area',         'latitude': 28.0019, 'longitude': 83.2802},
        {'name': 'Lalitpur',   'description': 'Suburban city',      'latitude': 27.5064, 'longitude': 83.6646},
        {'name': 'Biratnagar', 'description': 'Eastern city',       'latitude': 26.4600, 'longitude': 87.2700}
    ]
    
    tol = 0.05
    existing = Zone.query.all()
    
    for exp in expected_zones:
        found = None
        for z in existing:
            if z.latitude is not None and z.longitude is not None:
                if abs(z.latitude - exp['latitude']) < tol and abs(z.longitude - exp['longitude']) < tol:
                    found = z
                    break
        
        if found:
            if found.name != exp['name'] or found.description != exp['description']:
                found.name = exp['name']
                found.description = exp['description']
                db.session.add(found)
        else:
            new_zone = Zone(name=exp['name'], description=exp['description'], 
                          latitude=exp['latitude'], longitude=exp['longitude'])
            db.session.add(new_zone)
    
    db.session.commit()
    print("✓ Default zones verified/created successfully!")
