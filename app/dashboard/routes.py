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


@dashboard_bp.route('/compare-zones')
@login_required
def compare_zones():
    """
    Zone Comparison page - dynamically compares pollution metrics between two zones.
    
    Query Parameters:
        zone1_id: ID of the first zone to compare
        zone2_id: ID of the second zone to compare
    """
    from flask import request
    from datetime import datetime
    
    # Fetch all zones for dropdown selection
    zones = Zone.query.all()
    
    # Get selected zone IDs from query parameters
    zone1_id = request.args.get('zone1_id', type=int)
    zone2_id = request.args.get('zone2_id', type=int)
    
    # Initialize comparison data
    zone1_data = None
    zone2_data = None
    comparison = None
    
    def get_zone_metrics(zone):
        """Get the latest pollution metrics for a zone with fallback to simulated data."""
        latest_reading = PollutionReading.query.filter_by(zone_id=zone.id)\
            .order_by(PollutionReading.timestamp.desc()).first()
        
        if latest_reading:
            pm25_val = latest_reading.pm25
            if pm25_val <= 12.0:
                epa_category, epa_color = 'Good', 'success'
            elif pm25_val <= 35.0:
                epa_category, epa_color = 'Moderate', 'warning'
            else:
                epa_category, epa_color = 'Unhealthy', 'danger'
            
            return {
                'zone': zone,
                'has_data': True,
                'pm25': latest_reading.pm25,
                'pm10': latest_reading.pm10,
                'temperature': latest_reading.temperature,
                'noise': latest_reading.noise_level,
                'timestamp': latest_reading.timestamp,
                'epa_category': epa_category,
                'epa_color': epa_color,
                'status': calculate_aqi_status(latest_reading.pm25)
            }
        else:
            # Use simulated fallback data
            realtime = get_realtime_open_meteo({'latitude': zone.latitude, 'longitude': zone.longitude})
            pm25_val = realtime.get('pm25', 30.0)
            
            if pm25_val <= 12.0:
                epa_category, epa_color = 'Good', 'success'
            elif pm25_val <= 35.0:
                epa_category, epa_color = 'Moderate', 'warning'
            else:
                epa_category, epa_color = 'Unhealthy', 'danger'
            
            return {
                'zone': zone,
                'has_data': False,
                'pm25': pm25_val,
                'pm10': realtime.get('pm10', 45.0),
                'temperature': realtime.get('temperature', 20.0),
                'noise': realtime.get('noise', 60.0),
                'timestamp': datetime.utcnow(),
                'epa_category': epa_category,
                'epa_color': epa_color,
                'status': calculate_aqi_status(pm25_val)
            }
    
    def compute_metric_comparison(val1, val2, metric_name):
        """Compute comparison between two metric values."""
        if val1 is None or val2 is None:
            return {'abs_diff': None, 'pct_diff': None, 'worse_zone': 0, 'indicator': '='}
        
        abs_diff = round(abs(val1 - val2), 2)
        max_val = max(abs(val1), abs(val2))
        pct_diff = round((abs_diff / max_val) * 100, 1) if max_val != 0 else 0.0
        
        if metric_name == 'temperature':
            comfortable_temp = 22.0
            dev1, dev2 = abs(val1 - comfortable_temp), abs(val2 - comfortable_temp)
            if abs(dev1 - dev2) < 0.5:
                worse_zone, indicator = 0, '='
            elif dev1 > dev2:
                worse_zone, indicator = 1, '←'
            else:
                worse_zone, indicator = 2, '→'
        else:
            if abs(val1 - val2) < 0.5:
                worse_zone, indicator = 0, '='
            elif val1 > val2:
                worse_zone, indicator = 1, '←'
            else:
                worse_zone, indicator = 2, '→'
        
        return {
            'abs_diff': abs_diff, 'pct_diff': pct_diff, 
            'worse_zone': worse_zone, 'indicator': indicator,
            'zone1_value': val1, 'zone2_value': val2
        }
    
    # Get data for selected zones
    if zone1_id:
        zone1 = Zone.query.get(zone1_id)
        if zone1:
            zone1_data = get_zone_metrics(zone1)
    
    if zone2_id:
        zone2 = Zone.query.get(zone2_id)
        if zone2:
            zone2_data = get_zone_metrics(zone2)
    
    # Compute comparisons if both zones selected
    if zone1_data and zone2_data:
        comparison = {
            'pm25': compute_metric_comparison(zone1_data['pm25'], zone2_data['pm25'], 'pm25'),
            'pm10': compute_metric_comparison(zone1_data['pm10'], zone2_data['pm10'], 'pm10'),
            'temperature': compute_metric_comparison(zone1_data['temperature'], zone2_data['temperature'], 'temperature'),
            'noise': compute_metric_comparison(zone1_data['noise'], zone2_data['noise'], 'noise')
        }
        
        if zone1_data['pm25'] > zone2_data['pm25']:
            comparison['overall_worse'], comparison['overall_better'] = 1, 2
        elif zone2_data['pm25'] > zone1_data['pm25']:
            comparison['overall_worse'], comparison['overall_better'] = 2, 1
        else:
            comparison['overall_worse'], comparison['overall_better'] = 0, 0
    
    return render_template('dashboard/compare_zones.html',
                         zones=zones,
                         zone1_id=zone1_id,
                         zone2_id=zone2_id,
                         zone1_data=zone1_data,
                         zone2_data=zone2_data,
                         comparison=comparison)


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
