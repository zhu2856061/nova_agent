import os

import reflex as rx

config = rx.Config(
    app_name="app",
    frontend_port=2022,
    plugins=[rx.plugins.SitemapPlugin()],
    api_url=os.getenv("API_URL", "http://localhost:2022"),  # 关键！默认本地，生产可覆盖
)
