cp -r models/* /app
tar -xzvf server.tar.gz
mv -f *so /app/.venv/lib/python3.12/site-packages/
rm -rf server.tar.gz
export CONFIG_PATH=config.yaml
gunicorn -c gunicorn_deploy/gunicorn_conf.py main:app