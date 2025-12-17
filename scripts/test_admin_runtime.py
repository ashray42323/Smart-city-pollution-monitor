from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    # ensure user records
    if not User.query.filter_by(username='normal').first():
        u = User(username='normal', email='normal@example.com', password_hash=generate_password_hash('pass'))
        db.session.add(u)
    if not User.query.filter_by(username='adminuser').first():
        a = User(username='adminuser', email='admin@example.com', password_hash=generate_password_hash('pass'), is_admin=True)
        db.session.add(a)
    db.session.commit()

client = app.test_client()
# login normal
r = client.post('/login', data={'username':'normal','password':'pass'}, follow_redirects=True)
print('login normal status', r.status_code)
r = client.get('/admin/dashboard')
print('/admin/dashboard for normal ->', r.status_code)
# logout and login admin
client.get('/logout')
r = client.post('/login', data={'username':'adminuser','password':'pass'}, follow_redirects=True)
print('login admin status', r.status_code)
r = client.get('/admin/dashboard')
print('/admin/dashboard for admin ->', r.status_code)
