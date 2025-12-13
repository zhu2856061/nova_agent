#!/bin/bash
set -e

echo "Starting all services with supervisord..."
exec supervisord -c /app/supervisord.conf