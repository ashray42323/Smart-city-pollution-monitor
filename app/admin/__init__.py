"""
Admin Blueprint

Admin authentication is intentionally session-based and fully separated
from user authentication to reflect real-world access control systems.
"""

from flask import Blueprint

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin')

from app.admin import routes  # noqa: E402, F401
