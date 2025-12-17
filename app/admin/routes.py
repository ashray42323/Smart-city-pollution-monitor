"""
Admin Routes

Admin authentication is intentionally session-based and fully separated
from user authentication to reflect real-world access control systems.
"""

from flask import render_template, request, redirect, url_for, flash, session
from app.admin import admin_bp
from app.admin.decorators import admin_required
from app.extensions import db
from app.models import User, Zone, PollutionReading, Settings
from app.services import simulate_pollution_data
from app.config import Config


@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Dedicated admin login page - completely independent of user login."""
    if session.get('is_admin'):
        return redirect(url_for('admin.admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('admin/login.html')
        
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session.clear()
            session['is_admin'] = True
            session['admin_username'] = username
            flash('Welcome, Administrator!', 'success')
            return redirect(url_for('admin.admin_dashboard'))
        else:
            flash('Invalid administrator credentials.', 'danger')
    
    return render_template('admin/login.html')


@admin_bp.route('/logout')
def admin_logout():
    """Admin logout - clears entire session."""
    session.clear()
    flash('You have been logged out of the admin panel.', 'info')
    return redirect(url_for('admin.admin_login'))


@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard with system overview."""
    total_users = User.query.count()
    total_zones = Zone.query.count()
    total_readings = PollutionReading.query.count()
    settings = Settings.query.first()
    admin_username = session.get('admin_username', 'Admin')
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_zones=total_zones,
                         total_readings=total_readings,
                         settings=settings,
                         admin_username=admin_username)


@admin_bp.route('/zones', methods=['GET', 'POST'])
@admin_required
def manage_zones():
    """Manage zones - list, add new zones."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        
        if not name:
            flash('Zone name is required.', 'danger')
            return redirect(url_for('admin.manage_zones'))
        
        try:
            lat = float(latitude) if latitude else None
            lon = float(longitude) if longitude else None
        except ValueError:
            flash('Latitude and Longitude must be valid numbers.', 'danger')
            return redirect(url_for('admin.manage_zones'))
        
        new_zone = Zone(name=name, description=description, latitude=lat, longitude=lon)
        try:
            db.session.add(new_zone)
            db.session.commit()
            flash(f'Zone "{name}" added successfully.', 'success')
        except Exception:
            db.session.rollback()
            flash('Could not add zone.', 'danger')
        
        return redirect(url_for('admin.manage_zones'))
    
    zones = Zone.query.order_by(Zone.name).all()
    return render_template('admin/manage_zones.html', zones=zones)


@admin_bp.route('/zones/delete/<int:zone_id>', methods=['POST'])
@admin_required
def delete_zone(zone_id):
    """Delete a zone and all associated pollution readings."""
    zone = Zone.query.get_or_404(zone_id)
    zone_name = zone.name
    
    try:
        PollutionReading.query.filter_by(zone_id=zone_id).delete()
        db.session.delete(zone)
        db.session.commit()
        flash(f'Zone "{zone_name}" and all associated readings deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Could not delete zone: {str(e)}', 'danger')
    
    return redirect(url_for('admin.manage_zones'))


@admin_bp.route('/simulate')
@admin_required
def admin_simulate():
    """Trigger data simulation from admin panel."""
    try:
        zones = Zone.query.all()
        simulate_pollution_data(zones)
        flash('Simulation triggered by admin successfully.', 'success')
    except Exception as e:
        flash(f'Error during simulation: {e}', 'danger')
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    """Manage system settings (thresholds)."""
    settings = Settings.query.first()
    if not settings:
        settings = Settings(pm25_threshold=55.0, noise_threshold=80.0)
        db.session.add(settings)
        db.session.commit()
    
    if request.method == 'POST':
        try:
            pm25 = float(request.form.get('pm25_threshold', settings.pm25_threshold))
            noise = float(request.form.get('noise_threshold', settings.noise_threshold))
            settings.pm25_threshold = pm25
            settings.noise_threshold = noise
            db.session.add(settings)
            db.session.commit()
            flash('Settings updated successfully.', 'success')
        except ValueError:
            flash('Please provide valid numeric threshold values.', 'danger')
        except Exception:
            db.session.rollback()
            flash('Could not update settings.', 'danger')
        
        return redirect(url_for('admin.admin_settings'))
    
    return render_template('admin/settings.html', settings=settings)
