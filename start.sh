#!/bin/bash
mkdir -p /tmp/Ultralytics 2>/dev/null
export YOLO_CONFIG_DIR=/tmp
export MPLCONFIGDIR=/tmp/matplotlib
mkdir -p /tmp/matplotlib 2>/dev/null

gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 300 --worker-class gthread --threads 2
