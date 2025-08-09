"""Initialize the database with required tables"""
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Now import the database and models
from apps.api.core.database import engine, Base
from apps.api.domain import models  # noqa: F401 - Import models to create tables
from apps.api.domain import models_digital_twin  # noqa: F401 - Import Digital Twin models

def main():
    print("Initializing database...")
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")
    print(f"Database location: {os.path.abspath('satlink.db')}")

if __name__ == "__main__":
    main()
