#!/usr/bin/env bash

cd app
python3 manage.py migrate
#python3 manage.py runserver 0.0.0.0:8000
gunicorn demoservice.wsgi --bind 0.0.0.0:8000
