"""
Smart City Pollution Monitoring Dashboard
Main Flask Application Entry Point
"""

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import click

from config import Config
from models import db, User, Zone, PollutionReading
from models import Settings
from admin import admin_bp
from sqlalchemy import text
import logging
import utils as utils_mod
from utils import simulate_pollution_data, get_realtime_air_quality, calculate_aqi_status, get_weather_open_meteo, get_realtime_open_meteo, get_temperature_status, get_noise_status

logger = logging.getLogger(__name__)
logger.debug('Imported utils module from %s', getattr(utils_mod, '__file__', 'unknown'))

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Register custom Jinja filter for AQI status
@app.template_filter('aqi_status')
def aqi_status_filter(pm25_value):
    """Custom Jinja filter to calculate AQI status from PM2.5"""
    return calculate_aqi_status(pm25_value)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@app.context_processor
def inject_is_admin_flag():
    """Inject `is_admin` flag into templates based on SESSION, not User model."""
    return dict(is_admin=session.get('is_admin', False))


def promote_user(username):
    """Utility to promote a user to admin; safe to call from shell or CLI."""
    u = User.query.filter_by(username=username).first()
    if not u:
        raise ValueError(f'User {username} not found')
    u.is_admin = True
    db.session.add(u)
    db.session.commit()
    return u


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Zone': Zone, 'Settings': Settings, 'promote_user': promote_user}


@app.cli.command('make-admin')
@click.argument('username')
def make_admin(username):
    """Promote an existing user to admin: `flask make-admin <username>`"""
    try:
        u = promote_user(username)
        click.echo(f'User {u.username} promoted to admin')
    except Exception as e:
        click.echo(f'Error: {e}')

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))

# Database initialization
with app.app_context():
    # Create instance folder if it doesn't exist
    os.makedirs('instance', exist_ok=True)
    
    db.create_all()

    # Ensure `is_admin` column exists on users table for older DBs (SQLite)
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
    
    # Ensure default city zones exist and have correct names/coordinates
    expected_zones = [
        {'name': 'Kathmandu',  'description': 'Capital city',       'latitude': 27.7017, 'longitude': 85.3206},
        {'name': 'Bhaktapur',  'description': 'Historic city',      'latitude': 27.6730, 'longitude': 85.4300},
        {'name': 'Pokhara',    'description': 'Lakeside city',      'latitude': 28.2669, 'longitude': 83.9685},
        {'name': 'Gulmikot',   'description': 'Rural area',         'latitude': 28.0019, 'longitude': 83.2802},
        {'name': 'Lalitpur',   'description': 'Suburban city',      'latitude': 27.5064, 'longitude': 83.6646},
        {'name': 'Biratnagar', 'description': 'Eastern city',       'latitude': 26.4600, 'longitude': 87.2700}
    ]

    # Tolerance for matching existing zones by location (degrees)
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
            # update name/description if needed
            if found.name != exp['name'] or found.description != exp['description']:
                found.name = exp['name']
                found.description = exp['description']
                db.session.add(found)
        else:
            # create missing expected zone
            new_zone = Zone(name=exp['name'], description=exp['description'], latitude=exp['latitude'], longitude=exp['longitude'])
            db.session.add(new_zone)

    db.session.commit()
    print("✓ Default zones verified/created successfully!")

# Routes
@app.route('/')
def index():
    """Redirect to dashboard if logged in, otherwise to login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not username or len(username) < 3:
            flash('Username must be at least 3 characters long.', 'danger')
            return render_template('register.html')
        
        if not email or '@' not in email:
            flash('Please provide a valid email address.', 'danger')
            return render_template('register.html')
        
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already taken. Please choose another.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please login or use another email.', 'danger')
            return render_template('register.html')
        
        # Create new user
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password_hash=hashed_password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'danger')
            print(f"Registration error: {e}")
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login route"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            # Regular user login - explicitly set is_admin=False in session
            # This ensures regular users don't accidentally get admin access
            if session.get('is_admin'):
                session['is_admin'] = False
            flash(f'Welcome back, {user.username}!', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """User logout route - clears session and logs out user"""
    # Clear admin session flag if it exists (though it shouldn't for regular users)
    session.pop('is_admin', None)
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard showing pollution data and metrics"""
    zones = Zone.query.all()
    
    # Get latest reading for each zone
    zone_data = []
    total_pm25 = 0
    total_pm10 = 0
    count = 0
    
    for zone in zones:
        latest_reading = PollutionReading.query.filter_by(zone_id=zone.id)\
            .order_by(PollutionReading.timestamp.desc()).first()
        
        if latest_reading:
            # Get previous reading (for temporal comparison)
            prev_reading = PollutionReading.query.filter_by(zone_id=zone.id)\
                .order_by(PollutionReading.timestamp.desc()).offset(1).first()

            # Base zone info
            zone_info = {
                'zone': zone,
                'reading': latest_reading,
                'prev_reading': prev_reading,
                'status': calculate_aqi_status(latest_reading.pm25)
            }

            # Temporal comparison (percentage change and trend)
            if prev_reading:
                pm25_change = latest_reading.pm25 - prev_reading.pm25
                pm25_pct = round((pm25_change / prev_reading.pm25) * 100, 2) if prev_reading.pm25 != 0 else None
                if pm25_pct is not None and abs(pm25_pct) < 1:
                    trend = 'Stable'
                else:
                    trend = 'Increasing' if pm25_change > 0 else 'Decreasing'
            else:
                pm25_change = None
                pm25_pct = None
                trend = 'No Data'

            # EPA category (per requirement: Good ≤12, Moderate 12–35, Unhealthy >35)
            pm25_val = latest_reading.pm25
            if pm25_val <= 12.0:
                epa_category = 'Good'
            elif pm25_val <= 35.0:
                epa_category = 'Moderate'
            else:
                epa_category = 'Unhealthy'

            zone_info.update({
                'pm25_change': round(pm25_change, 2) if pm25_change is not None else None,
                'pm25_change_pct': pm25_pct,
                'trend': trend,
                'epa_category': epa_category
            })

            zone_data.append(zone_info)
            total_pm25 += latest_reading.pm25
            total_pm10 += latest_reading.pm10
            count += 1
    
    # Calculate averages
    avg_pm25 = round(total_pm25 / count, 2) if count > 0 else 0
    avg_pm10 = round(total_pm10 / count, 2) if count > 0 else 0
    
    # Find highest and lowest pollution zones
    highest_zone = max(zone_data, key=lambda x: x['reading'].pm25) if zone_data else None
    lowest_zone = min(zone_data, key=lambda x: x['reading'].pm25) if zone_data else None
    
    # Get real-time API data (Open-Meteo)
    # The new get_realtime_open_meteo always returns numeric values:
    # - PM2.5, PM10, Temperature from API when available
    # - Noise is ALWAYS simulated (no public real-time API exists)
    # - Missing API values are filled with realistic simulations
    realtime_data = get_realtime_open_meteo(Config.DEFAULT_CITY)
    logger.debug('Realtime data fetched: %s', realtime_data)
    
    # Simulated vs Real-time comparisons (generalized for PM2.5, PM10, Temperature, Noise)
    sim_values = []
    real_values = []

    # Extract realtime values - these are now guaranteed to be numeric (never None)
    # thanks to the fallback simulation logic in get_realtime_open_meteo
    realtime_values = {
        'pm25': realtime_data.get('pm25'),
        'pm10': realtime_data.get('pm10'),
        'temperature': realtime_data.get('temperature'),
        # Noise is returned as 'noise' in the new format
        'noise_level': realtime_data.get('noise')
    }
    
    # Extract source information to show users which values are real vs simulated
    realtime_sources = realtime_data.get('source', {
        'pm25': 'unknown',
        'pm10': 'unknown',
        'temperature': 'unknown',
        'noise': 'simulated'  # Noise is always simulated
    })

    def compute_comparison(sim, real):
        """Compute absolute and percentage differences and simple status text.
        Returns (abs_diff, pct_diff, status_text). Uses None when real is missing or invalid.
        """
        if real is None:
            return (None, None, 'No Data')
        try:
            abs_diff = round(abs(sim - real), 2)
        except Exception:
            return (None, None, 'No Data')
        pct = None
        try:
            if real != 0:
                pct = round((abs_diff / real) * 100, 2)
        except Exception:
            pct = None

        if sim > real:
            status = 'Above'
        elif sim < real:
            status = 'Below'
        else:
            status = 'Equal'

        return (abs_diff, pct, status)

    for z in zone_data:
        # Metrics from simulated (latest) reading
        sim_pm25 = z['reading'].pm25
        sim_pm10 = z['reading'].pm10
        sim_temp = z['reading'].temperature
        sim_noise = z['reading'].noise_level

        # Realtime values (now always numeric thanks to fallback simulation)
        real_pm25 = realtime_values['pm25']
        real_pm10 = realtime_values['pm10']
        real_temp = realtime_values['temperature']
        real_noise = realtime_values['noise_level']

        # Compute comparisons using safe fallbacks and helper function
        pm25_abs, pm25_pct, pm25_status = compute_comparison(sim_pm25, real_pm25)
        pm10_abs, pm10_pct, pm10_status = compute_comparison(sim_pm10, real_pm10)
        temp_abs, temp_pct, temp_status = compute_comparison(sim_temp, real_temp)
        noise_abs, noise_pct, noise_status = compute_comparison(sim_noise, real_noise)

        # Temperature and Noise descriptive statuses based on the simulated (local) value
        temp_desc = get_temperature_status(sim_temp)
        noise_desc = get_noise_status(sim_noise)

        z.update({
            'realtime_pm25': real_pm25,
            'realtime_pm10': real_pm10,
            'realtime_temperature': real_temp,
            'realtime_noise_level': real_noise,
            
            # Include source tracking for UI to display data provenance
            'realtime_sources': realtime_sources,

            'metrics': {
                'pm25': {
                    'simulated': sim_pm25,
                    'realtime': real_pm25,
                    'abs_diff': pm25_abs,
                    'pct_diff': pm25_pct,
                    'status': pm25_status,
                    'source': realtime_sources.get('pm25', 'unknown')
                },
                'pm10': {
                    'simulated': sim_pm10,
                    'realtime': real_pm10,
                    'abs_diff': pm10_abs,
                    'pct_diff': pm10_pct,
                    'status': pm10_status,
                    'source': realtime_sources.get('pm10', 'unknown')
                },
                'temperature': {
                    'simulated': sim_temp,
                    'realtime': real_temp,
                    'abs_diff': temp_abs,
                    'pct_diff': temp_pct,
                    'status': temp_status,
                    'desc': temp_desc,
                    'source': realtime_sources.get('temperature', 'unknown')
                },
                'noise_level': {
                    'simulated': sim_noise,
                    'realtime': real_noise,
                    'abs_diff': noise_abs,
                    'pct_diff': noise_pct,
                    'status': noise_status,
                    'desc': noise_desc,
                    'source': realtime_sources.get('noise', 'simulated')  # Always simulated
                }
            }
        })

        # Keep existing sim/real lists for PM2.5 chart compatibility
        sim_values.append(sim_pm25)
        real_values.append(real_pm25)

    zone_names = [z['zone'].name for z in zone_data]
    highest_idx = zone_names.index(highest_zone['zone'].name) if highest_zone else None
    lowest_idx = zone_names.index(lowest_zone['zone'].name) if lowest_zone else None

    # Check for alerts using EPA categories (Unhealthy > 35 per requirement)
    alerts = [z for z in zone_data if z.get('epa_category') == 'Unhealthy']
    
    # -------------------------------------------------------------------------
    # Statistics & Insights Panel - Computed values for the new visual cards
    # -------------------------------------------------------------------------
    
    # Trend counts: Count zones by PM2.5 trend (Increasing, Decreasing, Stable)
    trend_counts = {'Increasing': 0, 'Decreasing': 0, 'Stable': 0, 'No Data': 0}
    for z in zone_data:
        trend = z.get('trend', 'No Data')
        if trend in trend_counts:
            trend_counts[trend] += 1
        else:
            trend_counts['No Data'] += 1
    
    # EPA category counts: Count zones by EPA status
    epa_counts = {'Good': 0, 'Moderate': 0, 'Unhealthy': 0}
    for z in zone_data:
        cat = z.get('epa_category', 'Good')
        if cat in epa_counts:
            epa_counts[cat] += 1
    
    # Overall EPA status based on average PM2.5
    if avg_pm25 <= 12.0:
        overall_epa_status = 'Good'
        overall_epa_color = 'success'
    elif avg_pm25 <= 35.0:
        overall_epa_status = 'Moderate'
        overall_epa_color = 'warning'
    else:
        overall_epa_status = 'Unhealthy'
        overall_epa_color = 'danger'
    
    # Simulated vs Real-time comparison status
    # Calculate average simulated PM2.5 from all zones
    avg_sim_pm25 = round(sum(sim_values) / len(sim_values), 2) if sim_values else 0
    real_pm25_value = realtime_values.get('pm25')
    
    # Determine comparison indicator
    if real_pm25_value is not None and avg_sim_pm25 > 0:
        diff_pct = abs(avg_sim_pm25 - real_pm25_value) / real_pm25_value * 100 if real_pm25_value != 0 else 0
        if diff_pct < 1:
            comparison_status = 'equal'  # Nearly equal (<1% difference)
            comparison_color = 'warning'
            comparison_icon = '→'
        elif avg_sim_pm25 > real_pm25_value:
            comparison_status = 'above'  # Simulated > Real
            comparison_color = 'danger'
            comparison_icon = '↑'
        else:
            comparison_status = 'below'  # Simulated < Real
            comparison_color = 'success'
            comparison_icon = '↓'
        comparison_diff_pct = round(diff_pct, 1)
    else:
        comparison_status = 'unknown'
        comparison_color = 'secondary'
        comparison_icon = '?'
        comparison_diff_pct = None
    
    # Build statistics dict for template
    stats = {
        'trend_counts': trend_counts,
        'epa_counts': epa_counts,
        'overall_epa_status': overall_epa_status,
        'overall_epa_color': overall_epa_color,
        'avg_sim_pm25': avg_sim_pm25,
        'real_pm25': real_pm25_value,
        'comparison_status': comparison_status,
        'comparison_color': comparison_color,
        'comparison_icon': comparison_icon,
        'comparison_diff_pct': comparison_diff_pct,
        'total_zones': len(zone_data)
    }
    
    return render_template('dashboard.html', 
                         zone_data=zone_data,
                         avg_pm25=avg_pm25,
                         avg_pm10=avg_pm10,
                         highest_zone=highest_zone,
                         lowest_zone=lowest_zone,
                         realtime_data=realtime_data,
                         realtime_sources=realtime_sources,
                         sim_values=sim_values,
                         real_values=real_values,
                         highest_idx=highest_idx,
                         lowest_idx=lowest_idx,
                         alerts=alerts,
                         stats=stats)

# -----------------------------------------------------------------------------
# Statistics & Insights Page - Visual analytics and comparisons
# -----------------------------------------------------------------------------
@app.route('/statistics')
@login_required
def statistics():
    """Statistics & Insights page with visual analytics and comparisons"""
    zones = Zone.query.all()
    
    # Reuse dashboard data computation logic
    zone_data = []
    total_pm25 = 0
    total_pm10 = 0
    count = 0
    
    for zone in zones:
        latest_reading = PollutionReading.query.filter_by(zone_id=zone.id)\
            .order_by(PollutionReading.timestamp.desc()).first()
        
        if latest_reading:
            prev_reading = PollutionReading.query.filter_by(zone_id=zone.id)\
                .order_by(PollutionReading.timestamp.desc()).offset(1).first()
            
            zone_info = {
                'zone': zone,
                'reading': latest_reading,
                'prev_reading': prev_reading,
                'status': calculate_aqi_status(latest_reading.pm25)
            }
            
            # Trend calculation
            if prev_reading:
                pm25_change = latest_reading.pm25 - prev_reading.pm25
                pm25_pct = round((pm25_change / prev_reading.pm25) * 100, 2) if prev_reading.pm25 != 0 else None
                if pm25_pct is not None and abs(pm25_pct) < 1:
                    trend = 'Stable'
                else:
                    trend = 'Increasing' if pm25_change > 0 else 'Decreasing'
            else:
                pm25_pct = None
                trend = 'No Data'
            
            # EPA category
            pm25_val = latest_reading.pm25
            if pm25_val <= 12.0:
                epa_category = 'Good'
            elif pm25_val <= 35.0:
                epa_category = 'Moderate'
            else:
                epa_category = 'Unhealthy'
            
            zone_info.update({
                'pm25_change_pct': pm25_pct,
                'trend': trend,
                'epa_category': epa_category
            })
            
            zone_data.append(zone_info)
            total_pm25 += latest_reading.pm25
            total_pm10 += latest_reading.pm10
            count += 1
    
    avg_pm25 = round(total_pm25 / count, 2) if count > 0 else 0
    avg_pm10 = round(total_pm10 / count, 2) if count > 0 else 0
    
    highest_zone = max(zone_data, key=lambda x: x['reading'].pm25) if zone_data else None
    lowest_zone = min(zone_data, key=lambda x: x['reading'].pm25) if zone_data else None
    
    # Get real-time data
    realtime_data = get_realtime_open_meteo(Config.DEFAULT_CITY)
    realtime_sources = realtime_data.get('source', {})
    
    # Build statistics
    sim_values = [z['reading'].pm25 for z in zone_data]
    
    trend_counts = {'Increasing': 0, 'Decreasing': 0, 'Stable': 0, 'No Data': 0}
    for z in zone_data:
        trend = z.get('trend', 'No Data')
        if trend in trend_counts:
            trend_counts[trend] += 1
    
    epa_counts = {'Good': 0, 'Moderate': 0, 'Unhealthy': 0}
    for z in zone_data:
        cat = z.get('epa_category', 'Good')
        if cat in epa_counts:
            epa_counts[cat] += 1
    
    avg_sim_pm25 = round(sum(sim_values) / len(sim_values), 2) if sim_values else 0
    real_pm25_value = realtime_data.get('pm25')
    
    stats = {
        'trend_counts': trend_counts,
        'epa_counts': epa_counts,
        'avg_sim_pm25': avg_sim_pm25,
        'real_pm25': real_pm25_value,
        'total_zones': len(zone_data)
    }
    
    return render_template('statistics.html',
                         zone_data=zone_data,
                         avg_pm25=avg_pm25,
                         avg_pm10=avg_pm10,
                         highest_zone=highest_zone,
                         lowest_zone=lowest_zone,
                         realtime_data=realtime_data,
                         realtime_sources=realtime_sources,
                         stats=stats)


# -----------------------------------------------------------------------------
# Zones & Data Page - Operational view with raw data tables
# -----------------------------------------------------------------------------
@app.route('/zones')
@login_required
def zones_page():
    """Zones & Data page with detailed zone-wise tables"""
    zones = Zone.query.all()
    
    zone_data = []
    for zone in zones:
        latest_reading = PollutionReading.query.filter_by(zone_id=zone.id)\
            .order_by(PollutionReading.timestamp.desc()).first()
        
        if latest_reading:
            prev_reading = PollutionReading.query.filter_by(zone_id=zone.id)\
                .order_by(PollutionReading.timestamp.desc()).offset(1).first()
            
            zone_info = {
                'zone': zone,
                'reading': latest_reading,
                'status': calculate_aqi_status(latest_reading.pm25)
            }
            
            # Trend calculation
            if prev_reading:
                pm25_change = latest_reading.pm25 - prev_reading.pm25
                pm25_pct = round((pm25_change / prev_reading.pm25) * 100, 2) if prev_reading.pm25 != 0 else None
                if pm25_pct is not None and abs(pm25_pct) < 1:
                    trend = 'Stable'
                else:
                    trend = 'Increasing' if pm25_change > 0 else 'Decreasing'
            else:
                pm25_pct = None
                trend = 'No Data'
            
            # EPA category
            pm25_val = latest_reading.pm25
            if pm25_val <= 12.0:
                epa_category = 'Good'
            elif pm25_val <= 35.0:
                epa_category = 'Moderate'
            else:
                epa_category = 'Unhealthy'
            
            zone_info.update({
                'pm25_change_pct': pm25_pct,
                'trend': trend,
                'epa_category': epa_category
            })
            
            zone_data.append(zone_info)
    
    # Get real-time data for comparison
    realtime_data = get_realtime_open_meteo(Config.DEFAULT_CITY)
    realtime_sources = realtime_data.get('source', {})
    
    return render_template('zones.html',
                         zone_data=zone_data,
                         realtime_data=realtime_data,
                         realtime_sources=realtime_sources)


@app.route('/test-admin')
@login_required
def test_admin():
    """Temporary testing endpoint to show current user's admin status."""
    return jsonify({'username': current_user.username, 'is_admin': bool(getattr(current_user, 'is_admin', False))})

# Register admin blueprint
app.register_blueprint(admin_bp, url_prefix='/admin')

@app.route('/zone/<int:zone_id>')
@login_required
def zone_detail(zone_id):
    """Detailed view of a specific zone"""
    zone = Zone.query.get_or_404(zone_id)
    
    # Get recent readings (last 20)
    readings = PollutionReading.query.filter_by(zone_id=zone_id)\
        .order_by(PollutionReading.timestamp.desc()).limit(20).all()
    
    # Reverse for chronological order in charts
    readings.reverse()
    
    # Latest reading for current status
    latest = readings[-1] if readings else None
    status = calculate_aqi_status(latest.pm25) if latest else {'level': 'No Data', 'color': 'secondary'}

    # Fetch weather for the zone coordinates (if available)
    weather = None
    if zone.latitude is not None and zone.longitude is not None:
        weather = get_weather_open_meteo(zone.latitude, zone.longitude)

    return render_template('zone_details.html', 
                         zone=zone, 
                         readings=readings,
                         latest=latest,
                         status=status,
                         weather=weather)

@app.route('/simulate')
@login_required
def simulate():
    """Simulate pollution data for all zones"""
    try:
        zones = Zone.query.all()
        simulate_pollution_data(zones)
        flash('Pollution data simulated successfully!', 'success')
    except Exception as e:
        flash(f'Error simulating data: {str(e)}', 'danger')
        print(f"Simulation error: {e}")
    
    return redirect(url_for('dashboard'))

@app.route('/api/readings')
@login_required
def api_readings():
    """Return JSON of latest readings for dynamic updates"""
    zones = Zone.query.all()
    data = []
    
    for zone in zones:
        latest = PollutionReading.query.filter_by(zone_id=zone.id)\
            .order_by(PollutionReading.timestamp.desc()).first()
        
        if latest:
            data.append({
                'zone_id': zone.id,
                'zone_name': zone.name,
                'pm25': latest.pm25,
                'pm10': latest.pm10,
                'noise_level': latest.noise_level,
                'temperature': latest.temperature,
                'timestamp': latest.timestamp.isoformat(),
                'status': calculate_aqi_status(latest.pm25)
            })
    
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)