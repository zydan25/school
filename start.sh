#!/usr/bin/env bash
cd /home/root/projects/school
source .venv/bin/activate
exec gunicorn config.wsgi:application \
    --bind 127.0.0.1:6005 \
    --workers 3 \
    --timeout 60
