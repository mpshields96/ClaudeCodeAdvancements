#!/bin/bash
# Pokemon Crystal bot setup — run once
# Usage: cd pokemon-agent && bash setup.sh

set -e

echo "Setting up Pokemon Crystal bot..."

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install mGBA dependencies
source venv/bin/activate
echo "Installing mGBA dependencies (cffi, cached_property)..."
pip install cffi cached_property

echo ""
echo "Done! To play:"
echo "  1. Open a terminal and run:"
echo "     cd $(pwd)"
echo "     source venv/bin/activate"
echo "     python3 bridge.py --rom pokemon_crystal.gbc --speed 1"
echo ""
echo "  2. In Claude Code, run:"
echo "     /pokemon-play"
echo ""
echo "Have fun!"
