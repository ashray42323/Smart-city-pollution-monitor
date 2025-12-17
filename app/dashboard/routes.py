"""
Dashboard Routes

Main dashboard routes for pollution monitoring.
"""

from flask import render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp
from app.dashboard.services import get_zone_data, enrich_zone_data_with_realtime, compute_statistics
from app.models import Zone, PollutionReading
from app.services import simulate_pollution_data, calculate_aqi_status, get_weather_open_meteo, get_realtime_open_meteo
from app.config import Config


@dashboard_bp.route('/')
def index():
    """Redirect to dashboard if logged in, otherwise to login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    return redirect(url_for('auth.login'))


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard showing pollution data and metrics"""
    zone_data, avg_pm25, avg_pm10 = get_zone_data()
    
    if not zone_data:
        return render_template('dashboard/dashboard.html',
                             zone_data=[],
                             avg_pm25=0,
                             avg_pm10=0,
                             highest_zone=None,
                             lowest_zone=None,
                             realtime_data={},
                             realtime_sources={},
                             sim_values=[],
                             real_values=[],
                             highest_idx=None,
                             lowest_idx=None,
                             alerts=[],
                             stats={})
    
    # Enrich with realtime data
    zone_data, realtime_data, realtime_sources, sim_values, real_values = enrich_zone_data_with_realtime(zone_data)
    
    # Find highest and lowest pollution zones
    highest_zone = max(zone_data, key=lambda x: x['reading'].pm25)
    lowest_zone = min(zone_data, key=lambda x: x['reading'].pm25)
    
    zone_names = [z['zone'].name for z in zone_data]
    highest_idx = zone_names.index(highest_zone['zone'].name)
    lowest_idx = zone_names.index(lowest_zone['zone'].name)
    
    # Check for alerts
    alerts = [z for z in zone_data if z.get('epa_category') == 'Unhealthy']
    
    # Compute statistics
    stats = compute_statistics(zone_data, sim_values, realtime_data, avg_pm25)
    
    return render_template('dashboard/dashboard.html',
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


@dashboard_bp.route('/statistics')
@login_required
def statistics():
    """Statistics & Insights page with visual analytics"""
    zone_data, avg_pm25, avg_pm10 = get_zone_data()
    
    if not zone_data:
        return render_template('dashboard/statistics.html',
                             zone_data=[],
                             avg_pm25=0,
                             avg_pm10=0,
                             highest_zone=None,
                             lowest_zone=None,
                             realtime_data={},
                             realtime_sources={},
                             stats={})
    
    highest_zone = max(zone_data, key=lambda x: x['reading'].pm25)
    lowest_zone = min(zone_data, key=lambda x: x['reading'].pm25)
    
    realtime_data = get_realtime_open_meteo(Config.DEFAULT_CITY)
    realtime_sources = realtime_data.get('source', {})
    
    sim_values = [z['reading'].pm25 for z in zone_data]
    
    stats = compute_statistics(zone_data, sim_values, realtime_data, avg_pm25)
    
    return render_template('dashboard/statistics.html',
                         zone_data=zone_data,
                         avg_pm25=avg_pm25,
                         avg_pm10=avg_pm10,
                         highest_zone=highest_zone,
                         lowest_zone=lowest_zone,
                         realtime_data=realtime_data,
                         realtime_sources=realtime_sources,
                         stats=stats)


@dashboard_bp.route('/zones')
@login_required
def zones_page():
    """Zones & Data page with detailed zone-wise tables"""
    zone_data, avg_pm25, avg_pm10 = get_zone_data()
    
    realtime_data = get_realtime_open_meteo(Config.DEFAULT_CITY)
    realtime_sources = realtime_data.get('source', {})
    
    return render_template('dashboard/zones.html',
                         zone_data=zone_data,
                         realtime_data=realtime_data,
                         realtime_sources=realtime_sources)


@dashboard_bp.route('/zone/<int:zone_id>')
@login_required
def zone_detail(zone_id):
    """Detailed view of a specific zone"""
    zone = Zone.query.get_or_404(zone_id)
    
    readings = PollutionReading.query.filter_by(zone_id=zone_id)\
        .order_by(PollutionReading.timestamp.desc()).limit(20).all()
    
    readings.reverse()
    
    latest = readings[-1] if readings else None
    status = calculate_aqi_status(latest.pm25) if latest else {'level': 'No Data', 'color': 'secondary'}
    
    weather = None
    if zone.latitude is not None and zone.longitude is not None:
        weather = get_weather_open_meteo(zone.latitude, zone.longitude)
    
    return render_template('dashboard/zone_details.html',
                         zone=zone,
                         readings=readings,
                         latest=latest,
                         status=status,
                         weather=weather)


@dashboard_bp.route('/simulate')
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
    
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/api/readings')
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
