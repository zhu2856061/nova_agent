import reflex as rx

config = rx.Config(
    app_name="app",
    frontend_port=2022,
    plugins=[rx.plugins.SitemapPlugin()],
)
