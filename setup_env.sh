#!/bin/bash

# Exit on error
set -e

# Create and activate virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r apps/api/requirements.txt

# Install additional required packages
echo "Installing additional packages..."
pip install requests==2.32.4

# Set PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
echo "PYTHONPATH set to: $PYTHONPATH"

echo "\nSetup complete! To start the server, run:"
echo "source venv/bin/activate"
echo "export PYTHONPATH=\$PYTHONPATH:$(pwd)"
echo "uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000"
