"""
Smart City Pollution Monitoring Dashboard
Application Entry Point

This file serves as the entry point for the Flask application.
It uses the application factory pattern defined in the app package.
"""

from app import create_app

# Create the Flask application using the factory
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)