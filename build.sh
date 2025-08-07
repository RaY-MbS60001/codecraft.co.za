#!/usr/bin/env bash
# Build script for Render
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Create instance directory for SQLite database
mkdir -p instance

# Initialize database
python << EOF
from app import app, db
with app.app_context():
    db.create_all()
    print("Database initialized successfully!")
EOF