import os
from CTFd.models import db
from CTFd.plugins import (
    register_admin_plugin_menu_bar,
    register_admin_plugin_script,
    register_plugin_assets_directory,
)
from CTFd.utils import get_config
from CTFd.plugins.world_theme.api import register_world_theme_listeners, world_bp
from CTFd.plugins.world_theme.models import ChallengeCountry

def load(app):
    # Ensure database table and columns exist
    with app.app_context():
        ChallengeCountry.__table__.create(bind=db.engine, checkfirst=True)
        try:
            from sqlalchemy import inspect as sa_inspect

            inspector = sa_inspect(db.engine)
            existing_cols = {c["name"] for c in inspector.get_columns("challenge_countries")}
            for col in ("bonus_first", "bonus_second", "bonus_third", "bonus_fourth", "bonus_fifth"):
                if col in existing_cols:
                    continue
                # Each ALTER runs in its own transaction so a failure on one
                # (e.g. a race) does not abort the others, which matters on
                # databases like Postgres that abort the whole transaction.
                try:
                    with db.engine.begin() as conn:
                        conn.execute(
                            db.text(
                                f"ALTER TABLE challenge_countries "
                                f"ADD COLUMN {col} INTEGER DEFAULT 0"
                            )
                        )
                except Exception as e:
                    print(f"world_theme: could not add column {col}:", e)
        except Exception as e:
            print("world_theme: schema check failed:", e)

    # Register API and Admin routes
    app.register_blueprint(world_bp)

    # Attach event listeners once (not at import time)
    register_world_theme_listeners()

    # Register assets directory
    register_plugin_assets_directory(
        app, base_path="/plugins/world_theme/assets/"
    )

    # Register Admin script to inject Country & Bonus tab on challenge edit page
    register_admin_plugin_script("/plugins/world_theme/assets/admin.js")

    # Register Admin Menu link to Theme Settings
    register_admin_plugin_menu_bar(title="Theme Settings", route="/admin/theme_settings")

    # Dynamically filter Theme Settings so it ONLY displays when active theme is 'world'
    original_get_admin_plugin_menu_bar = app.jinja_env.globals.get("get_admin_plugin_menu_bar")
    def custom_get_admin_plugin_menu_bar():
        items = original_get_admin_plugin_menu_bar() if original_get_admin_plugin_menu_bar else app.admin_plugin_menu_bar
        current_theme = get_config("ctf_theme")
        if current_theme == "world":
            return items
        return [m for m in items if m.title != "Theme Settings" and m.route != "/admin/theme_settings"]

    app.jinja_env.globals["get_admin_plugin_menu_bar"] = custom_get_admin_plugin_menu_bar
