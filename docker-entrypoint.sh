#!/bin/sh
# Bring the database schema up to date, then hand PID 1 to the server so it
# receives signals directly and can shut down gracefully.
set -e
python manage.py migrate --noinput
exec "$@"
