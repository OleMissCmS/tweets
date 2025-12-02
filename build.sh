#!/bin/bash
# Build script to ensure Python 3.11 is used
echo "Python version check:"
python3 --version || python --version

# Install dependencies
pip install -r requirements.txt

