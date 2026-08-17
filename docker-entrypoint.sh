#!/bin/sh
set -e

# Replace ${BACKEND_URL} in nginx.conf with actual env var value
envsubst '${BACKEND_URL}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

# Start nginx
exec nginx -g 'daemon off;'
