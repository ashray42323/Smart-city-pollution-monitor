"""
Admin Decorator

Admin authentication is intentionally session-based and fully separated
from user authentication to reflect real-world access control systems.
"""

from functools import wraps
from flask import session, redirect, url_for


def admin_required(f):
    """Decorator to ensure the request is from an authenticated admin.
    
    Security:
    - Uses ONLY session['is_admin'] for validation
    - Does NOT use Flask-Login (login_user, current_user)
    - Admin must login via /admin/login to set session flag
    - Regular users cannot access admin routes even if logged in
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return wrapper
