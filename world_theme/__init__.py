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

    # Helper to retrieve challenge country info and bonuses for templates
    def get_challenge_country_info(challenge_id):
        try:
            cc = ChallengeCountry.query.filter_by(challenge_id=challenge_id).first()
            if not cc or not cc.country_iso:
                return None
            from CTFd.plugins.world_theme.api import load_countries_data
            countries_data = load_countries_data()
            c_info = countries_data.get(cc.country_iso, {})
            return {
                "iso": cc.country_iso,
                "name": c_info.get("name", cc.country_iso),
                "bonus_first": cc.bonus_first or 0,
                "bonus_second": cc.bonus_second or 0,
                "bonus_third": cc.bonus_third or 0,
            }
        except Exception:
            return None

    app.jinja_env.globals["get_challenge_country_info"] = get_challenge_country_info

    # Helper to retrieve configured directory custom attribute field names
    def get_directory_custom_fields():
        cfg = get_config("world_directory_custom_fields") or ""
        return [f.strip() for f in cfg.split(",") if f.strip()]

    # Helper to retrieve a specific custom attribute value for a user or team
    def get_custom_field_value(account, field_name):
        if not account or not field_name:
            return None
        target = field_name.strip().lower()
        try:
            entries = account.get_fields(admin=False) if hasattr(account, "get_fields") else getattr(account, "field_entries", [])
            for entry in entries:
                if entry.field and entry.field.name and entry.field.name.strip().lower() == target:
                    val = entry.value
                    if val is True:
                        return "Yes"
                    elif val is False:
                        return "No"
                    elif isinstance(val, (list, dict)):
                        import json
                        return json.dumps(val)
                    return str(val) if val is not None else None
        except Exception:
            pass
        return None

    app.jinja_env.globals["get_directory_custom_fields"] = get_directory_custom_fields
    app.jinja_env.globals["get_custom_field_value"] = get_custom_field_value
