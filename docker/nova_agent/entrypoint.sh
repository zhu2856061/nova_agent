
export CONFIG_PATH=/app/engine/config.yaml
# 启动agent引擎
cd /app/engine && uvicorn nova.main:app --host 0.0.0.0 --port 2021 &

# 后端backend
cd /app/backend && reflex run --env prod --backend-only &
# 启动前端forntend
nginx -c /etc/nginx/nginx.conf -g 'daemon off;'