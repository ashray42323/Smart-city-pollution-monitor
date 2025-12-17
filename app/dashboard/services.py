"""
Dashboard Services

Data aggregation and comparison logic for the dashboard.
"""

from app.models import Zone, PollutionReading
from app.services.aqi import calculate_aqi_status, get_temperature_status, get_noise_status
from app.services.realtime import get_realtime_open_meteo
from app.config import Config


def get_zone_data():
    """Get all zones with their latest readings and computed metrics."""
    zones = Zone.query.all()
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
            
            # Temporal comparison
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
            
            # EPA category
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
    
    avg_pm25 = round(total_pm25 / count, 2) if count > 0 else 0
    avg_pm10 = round(total_pm10 / count, 2) if count > 0 else 0
    
    return zone_data, avg_pm25, avg_pm10


def enrich_zone_data_with_realtime(zone_data):
    """Enrich zone data with real-time API comparisons."""
    realtime_data = get_realtime_open_meteo(Config.DEFAULT_CITY)
    realtime_sources = realtime_data.get('source', {
        'pm25': 'unknown',
        'pm10': 'unknown',
        'temperature': 'unknown',
        'noise': 'simulated'
    })
    
    realtime_values = {
        'pm25': realtime_data.get('pm25'),
        'pm10': realtime_data.get('pm10'),
        'temperature': realtime_data.get('temperature'),
        'noise_level': realtime_data.get('noise')
    }
    
    sim_values = []
    real_values = []
    
    def compute_comparison(sim, real):
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
        sim_pm25 = z['reading'].pm25
        sim_pm10 = z['reading'].pm10
        sim_temp = z['reading'].temperature
        sim_noise = z['reading'].noise_level
        
        real_pm25 = realtime_values['pm25']
        real_pm10 = realtime_values['pm10']
        real_temp = realtime_values['temperature']
        real_noise = realtime_values['noise_level']
        
        pm25_abs, pm25_pct, pm25_status = compute_comparison(sim_pm25, real_pm25)
        pm10_abs, pm10_pct, pm10_status = compute_comparison(sim_pm10, real_pm10)
        temp_abs, temp_pct, temp_status = compute_comparison(sim_temp, real_temp)
        noise_abs, noise_pct, noise_status = compute_comparison(sim_noise, real_noise)
        
        temp_desc = get_temperature_status(sim_temp)
        noise_desc = get_noise_status(sim_noise)
        
        z.update({
            'realtime_pm25': real_pm25,
            'realtime_pm10': real_pm10,
            'realtime_temperature': real_temp,
            'realtime_noise_level': real_noise,
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
                    'source': realtime_sources.get('noise', 'simulated')
                }
            }
        })
        
        sim_values.append(sim_pm25)
        real_values.append(real_pm25)
    
    return zone_data, realtime_data, realtime_sources, sim_values, real_values


def compute_statistics(zone_data, sim_values, realtime_values, avg_pm25):
    """Compute statistics for dashboard visualization."""
    trend_counts = {'Increasing': 0, 'Decreasing': 0, 'Stable': 0, 'No Data': 0}
    for z in zone_data:
        trend = z.get('trend', 'No Data')
        if trend in trend_counts:
            trend_counts[trend] += 1
        else:
            trend_counts['No Data'] += 1
    
    epa_counts = {'Good': 0, 'Moderate': 0, 'Unhealthy': 0}
    for z in zone_data:
        cat = z.get('epa_category', 'Good')
        if cat in epa_counts:
            epa_counts[cat] += 1
    
    if avg_pm25 <= 12.0:
        overall_epa_status = 'Good'
        overall_epa_color = 'success'
    elif avg_pm25 <= 35.0:
        overall_epa_status = 'Moderate'
        overall_epa_color = 'warning'
    else:
        overall_epa_status = 'Unhealthy'
        overall_epa_color = 'danger'
    
    avg_sim_pm25 = round(sum(sim_values) / len(sim_values), 2) if sim_values else 0
    real_pm25_value = realtime_values.get('pm25') if realtime_values else None
    
    if real_pm25_value is not None and avg_sim_pm25 > 0:
        diff_pct = abs(avg_sim_pm25 - real_pm25_value) / real_pm25_value * 100 if real_pm25_value != 0 else 0
        if diff_pct < 1:
            comparison_status = 'equal'
            comparison_color = 'warning'
            comparison_icon = '→'
        elif avg_sim_pm25 > real_pm25_value:
            comparison_status = 'above'
            comparison_color = 'danger'
            comparison_icon = '↑'
        else:
            comparison_status = 'below'
            comparison_color = 'success'
            comparison_icon = '↓'
        comparison_diff_pct = round(diff_pct, 1)
    else:
        comparison_status = 'unknown'
        comparison_color = 'secondary'
        comparison_icon = '?'
        comparison_diff_pct = None
    
    return {
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
