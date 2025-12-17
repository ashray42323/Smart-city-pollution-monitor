"""Test script to debug app initialization"""
import traceback
import sys

try:
    print("Attempting to import create_app...")
    from app import create_app
    print("create_app imported successfully")
    
    print("Attempting to create app...")
    app = create_app()
    print("App created successfully!")
    
except Exception as e:
    print("=" * 60)
    print("ERROR OCCURRED:")
    print("=" * 60)
    traceback.print_exc()
    print("=" * 60)
    sys.exit(1)
