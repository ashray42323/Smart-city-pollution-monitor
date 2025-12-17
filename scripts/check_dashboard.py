import sys
sys.path.insert(0, '.')
from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    if not User.query.filter_by(username='testuser').first():
        u = User(username='testuser', email='test@example.com', password_hash=generate_password_hash('testpass'))
        db.session.add(u)
        db.session.commit()

with app.test_client() as client:
    # login
    r = client.post('/login', data={'username':'testuser', 'password': 'testpass'}, follow_redirects=True)
    print('login status', r.status_code)
    r = client.get('/dashboard')
    text = r.get_data(as_text=True)
    print('dashboard status', r.status_code)
    print('label present:', 'Simulated vs Real-Time PM2.5 Comparison' in text)
    print('simRealChart present:', 'id="simRealChart"' in text)
    print('EPA present:', 'EPA:' in text)
    # print a small excerpt
    if 'Simulated vs Real-Time PM2.5 Comparison' in text:
        start = text.find('Simulated vs Real-Time PM2.5 Comparison')
        print(text[start:start+300])