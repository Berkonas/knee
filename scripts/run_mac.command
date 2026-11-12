#!/bin/bash
# Start TrailBuddy Analyzer from this folder (after install_mac.command).
cd "$(dirname "$0")/.." && exec .venv/bin/python -m trailbuddy
