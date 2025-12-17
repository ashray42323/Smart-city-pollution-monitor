from app import app
from werkzeug.security import generate_password_hash
from models import User
from models import db

with app.app_context():
    if not User.query.filter_by(username='testuser').first():
        u = User(username='testuser', email='test@example.com', password_hash=generate_password_hash('testpass'))
        db.session.add(u)
        db.session.commit()

with app.test_client() as c:
    c.post('/login', data={'username':'testuser','password':'testpass'}, follow_redirects=True)
    r = c.get('/dashboard')
    s = r.get_data(as_text=True)
    print('simRealChart present:', 'id="simRealChart"' in s)
    print('EPA present:', 'EPA:' in s)
    print('Sim vs Real label present:', 'Simulated vs Real-Time PM2.5 Comparison' in s)
    # Print sample table header
    start = s.find('Simulated vs Real-Time PM2.5 Comparison')
    if start != -1:
        print(s[start:start+300])