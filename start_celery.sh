#!/usr/bin/env bash

cd app
celery worker -A demoservice.tasks
