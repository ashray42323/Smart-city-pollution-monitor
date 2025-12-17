"""
Flask Extensions

Admin authentication is intentionally session-based and fully separated
from user authentication to reflect real-world access control systems.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Database instance
db = SQLAlchemy()

# Login manager for user authentication (NOT for admin)
login_manager = LoginManager()
