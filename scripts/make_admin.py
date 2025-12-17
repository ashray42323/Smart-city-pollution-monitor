import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    user = User.query.filter_by(username="testuser").first()

    if not user:
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=generate_password_hash("testpass"),
            is_admin=True
        )
        db.session.add(user)
        print("New admin user created")
    else:
        user.is_admin = True
        print("Existing user promoted to admin")

    db.session.commit()
