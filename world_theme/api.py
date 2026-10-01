import hashlib
import json
import os
import re
from datetime import datetime
from flask import Blueprint, jsonify, make_response, render_template, request, redirect, url_for
from sqlalchemy import event, func
from CTFd.models import Awards, Challenges, Solves, db
from CTFd.utils import get_config, set_config
from CTFd.utils.user import get_current_user, get_current_team, is_admin, authed
from CTFd.utils.decorators import admins_only, ratelimit
from CTFd.cache import cache, make_cache_key
from CTFd.plugins.world_theme.models import ChallengeCountry

world_bp = Blueprint(
    "world_theme",
    __name__,
    template_folder="templates",
    static_folder="assets",
)

COUNTRIES_CACHE = None

def load_countries_data():
    global COUNTRIES_CACHE
    if COUNTRIES_CACHE is not None:
        return COUNTRIES_CACHE
    path = os.path.join(os.path.dirname(__file__), "countries.json")
    with open(path, "r", encoding="utf-8") as f:
        COUNTRIES_CACHE = json.load(f)
    return COUNTRIES_CACHE

def make_user_cache_key(path=None):
    if path is None:
        path = request.endpoint
    user = get_current_user()
    team = get_current_team()
    acc_id = f"t{team.id}" if team else (f"u{user.id}" if user else "anon")
    admin_flag = "adm" if is_admin() else "pub"
    geo_flag = "geo1" if request.args.get("include_geometry", "").lower() in ("true", "1") else "geo0"
    return f"view/{path}/{admin_flag}/{acc_id}/{geo_flag}"

def make_feed_cache_key():
    adm = "adm" if is_admin() else "pub"
    return f"view/world_theme.get_world_live_feed/{adm}"

def get_solve_state_summary():
    """Returns (max_solve_id, solve_count) in a single fast scalar query (<1ms)"""
    return db.session.query(
        func.coalesce(func.max(Solves.id), 0),
        func.count(Solves.id)
    ).first()

@cache.memoize(timeout=300)
def get_country_mappings():
    """
    Returns a mapping of { challenge_id: iso_code } and { iso_code: challenge_id }.
    Priority:
    1. Explicit DB record in ChallengeCountry
    2. Tag matching 'country:XX' or 'iso:XX'
    """
    db_mappings = {
        cc.challenge_id: cc.country_iso.upper()
        for cc in ChallengeCountry.query.all()
    }

    challenges = (
        Challenges.query.filter(Challenges.state != "hidden")
        .options(db.joinedload(Challenges.tags))
        .all()
    )
    tag_mappings = {}
    tag_regex = re.compile(r"^(?:country|iso):([a-z0-9_]+)$", re.IGNORECASE)

    for c in challenges:
        if c.id in db_mappings:
            continue
        for tag in c.tags:
            match = tag_regex.match(tag.value.strip())
            if match:
                iso_candidate = match.group(1).upper()
                if iso_candidate not in db_mappings.values() and iso_candidate not in tag_mappings.values():
                    tag_mappings[c.id] = iso_candidate
                    break

    all_chal_to_iso = {**tag_mappings, **db_mappings}
    iso_to_chal = {iso: chal_id for chal_id, iso in all_chal_to_iso.items()}
    return all_chal_to_iso, iso_to_chal

def on_challenge_changed(mapper, connection, target):
    try:
        cache.delete_memoized(get_country_mappings)
    except Exception:
        pass

def register_world_theme_listeners():
    """Attach SQLAlchemy event listeners.

    Registered from load() rather than at import time so the listeners are not
    attached multiple times if this module is imported more than once.
    """
    event.listen(Challenges, "after_insert", on_challenge_created)
    event.listen(Challenges, "after_update", on_challenge_changed)
    event.listen(Challenges, "after_delete", on_challenge_changed)
    event.listen(Solves, "after_insert", on_solve_award_bonus)


def on_challenge_created(mapper, connection, target):
    """Automatically associate country when challenge is created, enforcing 1:1 mapping"""
    try:
        cache.delete_memoized(get_country_mappings)
        if request:
            data = request.get_json(silent=True) or request.form
            country_iso = (data.get("country_iso") or "").strip().upper()
            bonus_first = int(data.get("bonus_first", 0) or 0)
            bonus_second = int(data.get("bonus_second", 0) or 0)
            bonus_third = int(data.get("bonus_third", 0) or 0)

            if country_iso:
                existing = connection.execute(
                    ChallengeCountry.__table__.select().where(
                        ChallengeCountry.country_iso == country_iso
                    )
                ).first()
                if not existing:
                    connection.execute(
                        ChallengeCountry.__table__.insert().values(
                            challenge_id=target.id,
                            country_iso=country_iso,
                            bonus_first=bonus_first,
                            bonus_second=bonus_second,
                            bonus_third=bonus_third,
                        )
                    )
    except Exception as e:
        print("Error saving country on challenge creation:", e)

def on_solve_award_bonus(mapper, connection, target):
    """
    Early-Solver Decaying Bonuses (Locked-in):
    Award permanent, non-retroactive bonus points to the 1st, 2nd, and 3rd solvers
    via CTFd's native Awards model.
    """
    try:
        cc = ChallengeCountry.query.filter_by(challenge_id=target.challenge_id).first()
        if not cc:
            return

        # Count total solves for this challenge
        solve_count = Solves.query.filter_by(challenge_id=target.challenge_id).count()

        levels = [
            (cc.bonus_first or 0, "First Blood Bonus"),
            (cc.bonus_second or 0, "2nd Solver Bonus"),
            (cc.bonus_third or 0, "3rd Solver Bonus"),
            (cc.bonus_fourth or 0, "4th Solver Bonus"),
            (cc.bonus_fifth or 0, "5th Solver Bonus"),
        ]

        bonus_amount = 0
        bonus_name = ""
        chal_name = target.challenge.name if target.challenge else f"Challenge #{target.challenge_id}"

        if 1 <= solve_count <= len(levels):
            pts, label = levels[solve_count - 1]
            if pts > 0:
                bonus_amount = pts
                bonus_name = f"{label}: {chal_name}"

        if bonus_amount > 0:
            # Avoid duplicate award
            existing_query = Awards.query.filter_by(name=bonus_name)
            if target.team_id:
                existing = existing_query.filter_by(team_id=target.team_id).first()
            else:
                existing = existing_query.filter_by(user_id=target.user_id).first()

            if not existing:
                connection.execute(
                    Awards.__table__.insert().values(
                        user_id=target.user_id,
                        team_id=target.team_id,
                        type="standard",
                        name=bonus_name,
                        description=f"Early-solver locked bonus for #{solve_count} solve on {chal_name}",
                        value=bonus_amount,
                        category="Early-Solver Bonus",
                        date=datetime.utcnow()
                    )
                )
    except Exception as e:
        print("Error processing early-solver bonus:", e)

@world_bp.route("/api/v1/world/geo", methods=["GET"])
@ratelimit(method="GET", limit=60, interval=60)
@cache.cached(timeout=86400, key_prefix="view/world_theme.get_world_geo")
def get_world_geo():
    """Returns static SVG geometry (d and transform) for all countries, cached for 24 hours."""
    countries_data = load_countries_data()
    geo = {
        iso: {
            "iso": c.get("iso", iso),
            "name": c.get("name", iso),
            "d": c.get("d", ""),
            "transform": c.get("transform", ""),
        }
        for iso, c in countries_data.items()
    }
    resp = jsonify({"success": True, "data": geo})
    resp.headers["Cache-Control"] = "public, max-age=86400, immutable"
    return resp

@world_bp.route("/api/v1/world/countries", methods=["GET"])
@ratelimit(method="GET", limit=60, interval=60)
def get_world_countries():
    include_geometry = request.args.get("include_geometry", "").lower() in ("true", "1")
    user = get_current_user()
    team = get_current_team()
    acc_id = f"t{team.id}" if team else (f"u{user.id}" if user else "anon")
    admin_flag = "adm" if is_admin() else "pub"
    geo_flag = "geo1" if include_geometry else "geo0"

    max_solve_id, solve_count = get_solve_state_summary()
    etag = f'"wcountries-{max_solve_id}-{solve_count}-{admin_flag}-{acc_id}-{geo_flag}"'

    if request.headers.get("If-None-Match") == etag:
        resp = make_response("", 304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "private, max-age=15, must-revalidate"
        return resp

    cache_key = f"view/world_theme.countries/{admin_flag}/{acc_id}/{geo_flag}/{max_solve_id}/{solve_count}"
    cached_res = cache.get(cache_key)
    if cached_res is not None:
        resp = jsonify({"success": True, "data": cached_res})
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "private, max-age=15, must-revalidate"
        return resp

    countries_data = load_countries_data()
    chal_to_iso, iso_to_chal = get_country_mappings()
    mapped_chal_ids = list(iso_to_chal.values())

    # Pre-fetch user's solves only for mapped challenges
    my_solves = set()
    if authed() and mapped_chal_ids:
        if team:
            solves_query = (
                db.session.query(Solves.challenge_id)
                .filter(Solves.team_id == team.id, Solves.challenge_id.in_(mapped_chal_ids))
                .all()
            )
        elif user:
            solves_query = (
                db.session.query(Solves.challenge_id)
                .filter(Solves.user_id == user.id, Solves.challenge_id.in_(mapped_chal_ids))
                .all()
            )
        else:
            solves_query = []
        my_solves = {s[0] for s in solves_query}

    # Pre-fetch solved challenge IDs ONLY for mapped challenges (avoids full table read of Solves)
    all_solved_chal_ids = set()
    if mapped_chal_ids:
        all_solved_chal_ids = {
            s[0]
            for s in db.session.query(Solves.challenge_id)
            .filter(Solves.challenge_id.in_(mapped_chal_ids))
            .distinct()
            .all()
        }

    # Pre-fetch challenges and bonus config with tags eager-loaded via joinedload
    challenges_map = {}
    if mapped_chal_ids:
        chals = (
            Challenges.query.options(db.joinedload(Challenges.tags))
            .filter(Challenges.id.in_(mapped_chal_ids))
            .all()
        )
        cc_map = {
            cc.challenge_id: cc
            for cc in ChallengeCountry.query.filter(ChallengeCountry.challenge_id.in_(mapped_chal_ids)).all()
        }
        for c in chals:
            if not is_admin() and c.state == "hidden":
                continue
            cc = cc_map.get(c.id)
            challenges_map[c.id] = {
                "id": c.id,
                "name": c.name,
                "value": c.value,
                "category": c.category,
                "tags": [t.value for t in c.tags],
                "solved_by_me": c.id in my_solves,
                "bonus_first": cc.bonus_first if cc else 0,
                "bonus_second": cc.bonus_second if cc else 0,
                "bonus_third": cc.bonus_third if cc else 0,
            }

    response = {}
    for iso, country in countries_data.items():
        chal_id = iso_to_chal.get(iso)
        chal_info = challenges_map.get(chal_id) if chal_id else None

        if not chal_info:
            status = "inactive"
        else:
            if chal_id in my_solves:
                status = "captured_by_you"
            elif chal_id in all_solved_chal_ids:
                status = "captured_by_opponent"
            else:
                status = "active"

        entry = {
            "iso": country.get("iso", iso),
            "name": country.get("name", iso),
            "challenge": chal_info,
            "status": status,
        }
        if include_geometry:
            entry["d"] = country.get("d", "")
            entry["transform"] = country.get("transform", "")

        response[iso] = entry

    cache.set(cache_key, response, timeout=30)
    resp = jsonify({"success": True, "data": response})
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "private, max-age=15, must-revalidate"
    return resp

@world_bp.route("/api/v1/world/feed", methods=["GET"])
@ratelimit(method="GET", limit=60, interval=60)
def get_world_live_feed():
    """Returns real-time country captures and first bloods for all players with ETag and since_id polling support"""
    if not is_admin() and get_config("score_visibility") == "admins":
        return jsonify({"success": True, "data": [], "last_id": 0})

    max_solve_id, solve_count = get_solve_state_summary()
    role_flag = "adm" if is_admin() else "pub"
    etag = f'"wfeed-{max_solve_id}-{solve_count}-{role_flag}"'

    # 1. HTTP 304 Not Modified if ETag matches
    if request.headers.get("If-None-Match") == etag:
        resp = make_response("", 304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "public, max-age=10, must-revalidate"
        return resp

    # 2. since_id support: if client already has latest solves, return tiny empty diff
    since_id = request.args.get("since_id", type=int)
    if since_id is not None and since_id >= max_solve_id and max_solve_id > 0:
        resp = jsonify({
            "success": True,
            "changed": False,
            "data": [],
            "last_id": max_solve_id
        })
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "public, max-age=10, must-revalidate"
        return resp

    # 3. Check cache for full feed payload
    feed_cache_key = f"view/world_theme.feed_data/{role_flag}/{max_solve_id}/{solve_count}"
    cached_feed = cache.get(feed_cache_key)
    if cached_feed is not None:
        resp = jsonify({
            "success": True,
            "changed": True,
            "data": cached_feed,
            "last_id": max_solve_id
        })
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "public, max-age=10, must-revalidate"
        return resp

    # 4. Cache miss: query DB
    solves = (
        Solves.query.options(
            db.joinedload(Solves.challenge),
            db.joinedload(Solves.user),
            db.joinedload(Solves.team),
        )
        .order_by(Solves.date.desc())
        .limit(35)
        .all()
    )
    chal_to_iso, iso_to_chal = get_country_mappings()
    countries_data = load_countries_data()

    # Determine first bloods for all challenges in feed in a single batch query
    feed_chal_ids = {s.challenge_id for s in solves}
    first_blood_solve_ids = set()
    if feed_chal_ids:
        fb_query = (
            db.session.query(Solves.challenge_id, func.min(Solves.id))
            .filter(Solves.challenge_id.in_(feed_chal_ids))
            .group_by(Solves.challenge_id)
            .all()
        )
        first_blood_solve_ids = {row[1] for row in fb_query}

    feed = []
    for s in solves:
        if not is_admin() and s.challenge and s.challenge.state == "hidden":
            continue
        iso = chal_to_iso.get(s.challenge_id)
        c_data = countries_data.get(iso, {}) if iso else {}
        country_name = c_data.get("name", "Unknown Country")

        is_first_blood = (s.id in first_blood_solve_ids)

        solver_name = s.team.name if s.team else (s.user.name if s.user else "Anonymous")
        account_url = f"/teams/{s.team_id}" if s.team_id else (f"/users/{s.user_id}" if s.user_id else None)

        feed.append({
            "type": "solve",
            "solve_id": s.id,
            "challenge_id": s.challenge_id,
            "challenge_name": s.challenge.name if s.challenge else "Challenge",
            "points": s.challenge.value if s.challenge else 0,
            "country_iso": iso or "",
            "country_name": country_name,
            "solver_name": solver_name,
            "user_name": solver_name,
            "team_id": s.team_id,
            "user_id": s.user_id,
            "account_url": account_url,
            "is_first_blood": is_first_blood,
            "first_blood": is_first_blood,
            "date": s.date.isoformat(),
        })

    # Append activation events for active challenges if feed has room
    if len(feed) < 10:
        active_chals = Challenges.query.filter(Challenges.state != "hidden").order_by(Challenges.id.asc()).limit(15).all()
        for c in active_chals:
            iso = chal_to_iso.get(c.id)
            c_data = countries_data.get(iso, {}) if iso else {}
            feed.append({
                "type": "activation",
                "challenge_id": c.id,
                "challenge_name": c.name,
                "points": c.value,
                "country_iso": iso or "",
                "country_name": c_data.get("name", "Global Node"),
                "solver_name": "CTF-NET DEFENSE",
                "user_name": "CTF-NET DEFENSE",
                "team_id": None,
                "user_id": None,
                "account_url": None,
                "is_first_blood": False,
                "first_blood": False,
                "date": datetime.utcnow().isoformat(),
            })

    cache.set(feed_cache_key, feed, timeout=30)
    resp = jsonify({
        "success": True,
        "changed": True,
        "data": feed,
        "last_id": max_solve_id
    })
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "public, max-age=10, must-revalidate"
    return resp

@world_bp.route("/api/v1/world/dominance", methods=["GET"])
@ratelimit(method="GET", limit=60, interval=60)
def get_world_dominance():
    """Returns geopolitical territory conquest and dominance rankings using SQL aggregations"""
    empty_resp = {
        "total_territories": 0,
        "conquered_territories": 0,
        "unclaimed_territories": 0,
        "world_conquest_pct": 0,
        "top_conquerors": [],
        "my_dominance": None,
    }
    if not is_admin() and get_config("score_visibility") == "admins":
        return jsonify({"success": True, "data": empty_resp})

    user = get_current_user()
    team = get_current_team()
    acc_id = f"t{team.id}" if team else (f"u{user.id}" if user else "anon")
    admin_flag = "adm" if is_admin() else "pub"

    max_solve_id, solve_count = get_solve_state_summary()
    etag = f'"wdominance-{max_solve_id}-{solve_count}-{admin_flag}-{acc_id}"'
    if request.headers.get("If-None-Match") == etag:
        resp = make_response("", 304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "public, max-age=20, must-revalidate"
        return resp

    cache_key = f"view/world_theme.dominance/{admin_flag}/{acc_id}/{max_solve_id}/{solve_count}"
    cached_res = cache.get(cache_key)
    if cached_res is not None:
        resp = jsonify({"success": True, "data": cached_res})
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "public, max-age=20, must-revalidate"
        return resp

    chal_to_iso, iso_to_chal = get_country_mappings()
    countries_data = load_countries_data()

    active_chal_ids = list(chal_to_iso.keys())
    if not active_chal_ids:
        return jsonify({"success": True, "data": empty_resp})

    if not is_admin():
        active_chal_ids = [
            c[0]
            for c in db.session.query(Challenges.id)
            .filter(Challenges.id.in_(active_chal_ids), Challenges.state != "hidden")
            .all()
        ]

    total_territories = len(active_chal_ids)
    if total_territories == 0:
        return jsonify({"success": True, "data": empty_resp})

    is_teams = get_config("user_mode") == "teams"
    acc_col = Solves.team_id if is_teams else Solves.user_id

    # 1. Total conquered territories & first bloods per challenge in SQL
    fb_subquery = (
        db.session.query(
            Solves.challenge_id.label("chal_id"),
            func.min(Solves.id).label("min_solve_id")
        )
        .filter(Solves.challenge_id.in_(active_chal_ids))
        .group_by(Solves.challenge_id)
        .subquery()
    )

    fb_accounts = (
        db.session.query(Solves.challenge_id, acc_col)
        .join(fb_subquery, Solves.id == fb_subquery.c.min_solve_id)
        .filter(acc_col.isnot(None))
        .all()
    )

    conquered_territories = len(fb_accounts)
    unclaimed_territories = max(0, total_territories - conquered_territories)
    world_conquest_pct = round((conquered_territories / total_territories) * 100, 1) if total_territories > 0 else 0

    first_bloods_per_acc = {}
    for cid, acc_id in fb_accounts:
        first_bloods_per_acc[acc_id] = first_bloods_per_acc.get(acc_id, 0) + 1

    # 2. Count distinct conquered territories per account in SQL
    territory_counts = (
        db.session.query(
            acc_col.label("account_id"),
            func.count(func.distinct(Solves.challenge_id)).label("territories_count")
        )
        .filter(Solves.challenge_id.in_(active_chal_ids), acc_col.isnot(None))
        .group_by(acc_col)
        .all()
    )

    if not territory_counts:
        return jsonify({
            "success": True,
            "data": {
                "total_territories": total_territories,
                "conquered_territories": 0,
                "unclaimed_territories": total_territories,
                "world_conquest_pct": 0,
                "top_conquerors": [],
                "my_dominance": None,
            }
        })

    account_stats = []
    for acc_id, t_count in territory_counts:
        account_stats.append({
            "account_id": acc_id,
            "territories_count": t_count,
            "first_bloods_count": first_bloods_per_acc.get(acc_id, 0),
        })

    account_stats.sort(key=lambda x: (x["territories_count"], x["first_bloods_count"]), reverse=True)

    top_count = int(get_config("world_dominance_top_count", 4) or 4)
    top_acc_ids = {s["account_id"] for s in account_stats[:top_count]}

    my_acc_id = None
    if authed():
        my_team = get_current_team()
        my_user = get_current_user()
        my_acc_id = my_team.id if is_teams and my_team else (my_user.id if my_user else None)
        if my_acc_id:
            top_acc_ids.add(my_acc_id)

    # 3. Fetch only accounts in top_acc_ids
    if is_teams:
        from CTFd.models import Teams
        accounts_map = {
            t.id: t
            for t in Teams.query.filter(Teams.id.in_(top_acc_ids), Teams.banned == False, Teams.hidden == False).all()
        }
    else:
        from CTFd.models import Users
        accounts_map = {
            u.id: u
            for u in Users.query.filter(Users.id.in_(top_acc_ids), Users.banned == False, Users.hidden == False).all()
        }

    acc_solves = (
        db.session.query(acc_col, Solves.challenge_id)
        .filter(acc_col.in_(top_acc_ids), Solves.challenge_id.in_(active_chal_ids))
        .all()
    )
    acc_countries = {}
    for a_id, c_id in acc_solves:
        if a_id not in acc_countries:
            acc_countries[a_id] = []
        if len(acc_countries[a_id]) < 12:
            iso = chal_to_iso.get(c_id)
            if iso:
                c_name = countries_data.get(iso, {}).get("name", iso)
                acc_countries[a_id].append({"iso": iso, "name": c_name})

    top_conquerors = []
    my_dominance = None

    for rank, stat in enumerate(account_stats, 1):
        a_id = stat["account_id"]
        acc_obj = accounts_map.get(a_id)
        if not acc_obj:
            continue

        item = {
            "account_id": a_id,
            "rank": rank,
            "name": acc_obj.name,
            "account_url": f"/teams/{a_id}" if is_teams else f"/users/{a_id}",
            "territories_count": stat["territories_count"],
            "dominance_pct": round((stat["territories_count"] / total_territories) * 100, 1),
            "first_bloods_count": stat["first_bloods_count"],
            "countries": acc_countries.get(a_id, [])[:12],
        }

        if len(top_conquerors) < top_count:
            top_conquerors.append(item)

        if a_id == my_acc_id:
            my_dominance = item

    if authed() and my_acc_id and not my_dominance:
        my_team = get_current_team()
        my_user = get_current_user()
        my_dominance = {
            "account_id": my_acc_id,
            "name": my_team.name if is_teams and my_team else (my_user.name if my_user else "Operative"),
            "territories_count": 0,
            "dominance_pct": 0.0,
            "first_bloods_count": 0,
            "rank": len(account_stats) + 1,
            "countries": [],
        }

    dominance_payload = {
        "total_territories": total_territories,
        "conquered_territories": conquered_territories,
        "unclaimed_territories": unclaimed_territories,
        "world_conquest_pct": world_conquest_pct,
        "top_conquerors": top_conquerors,
        "my_dominance": my_dominance,
    }
    cache.set(cache_key, dominance_payload, timeout=30)
    resp = jsonify({
        "success": True,
        "data": dominance_payload
    })
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "public, max-age=20, must-revalidate"
    return resp

@world_bp.route("/api/v1/world/challenges/<int:challenge_id>/country", methods=["GET", "POST", "DELETE"])
@admins_only
def manage_challenge_country(challenge_id):
    if request.method == "GET":
        cc = ChallengeCountry.query.filter_by(challenge_id=challenge_id).first()
        b_levels = [
            cc.bonus_first if cc else 0,
            cc.bonus_second if cc else 0,
            cc.bonus_third if cc else 0,
            cc.bonus_fourth if cc else 0,
            cc.bonus_fifth if cc else 0,
        ]
        return jsonify({
            "success": True,
            "data": {
                "challenge_id": challenge_id,
                "country_iso": cc.country_iso if cc else None,
                "bonus_first": b_levels[0],
                "bonus_second": b_levels[1],
                "bonus_third": b_levels[2],
                "bonus_fourth": b_levels[3],
                "bonus_fifth": b_levels[4],
                "bonus_levels": b_levels,
            }
        })

    if request.method == "DELETE":
        cc = ChallengeCountry.query.filter_by(challenge_id=challenge_id).first()
        if cc:
            db.session.delete(cc)
            db.session.commit()
            cache.delete_memoized(get_country_mappings)
        return jsonify({"success": True, "message": "Country assignment removed"})

    data = request.get_json() or request.form
    country_iso = (data.get("country_iso") or "").strip().upper()

    def clamp_bonus(v):
        try:
            return max(0, min(100000, int(v or 0)))
        except (ValueError, TypeError):
            return 0

    bonus_levels = data.get("bonus_levels")
    if isinstance(bonus_levels, list):
        bonus_first = clamp_bonus(bonus_levels[0]) if len(bonus_levels) > 0 else 0
        bonus_second = clamp_bonus(bonus_levels[1]) if len(bonus_levels) > 1 else 0
        bonus_third = clamp_bonus(bonus_levels[2]) if len(bonus_levels) > 2 else 0
        bonus_fourth = clamp_bonus(bonus_levels[3]) if len(bonus_levels) > 3 else 0
        bonus_fifth = clamp_bonus(bonus_levels[4]) if len(bonus_levels) > 4 else 0
    else:
        bonus_first = clamp_bonus(data.get("bonus_first", 0))
        bonus_second = clamp_bonus(data.get("bonus_second", 0))
        bonus_third = clamp_bonus(data.get("bonus_third", 0))
        bonus_fourth = clamp_bonus(data.get("bonus_fourth", 0))
        bonus_fifth = clamp_bonus(data.get("bonus_fifth", 0))

    if not country_iso:
        return jsonify({"success": False, "message": "Country ISO code required"}), 400

    if len(country_iso) != 2:
        return jsonify({"success": False, "message": "Country ISO code must be 2 characters"}), 400

    countries_data = load_countries_data()
    if country_iso not in countries_data:
        return jsonify({"success": False, "message": f"Unknown country ISO: {country_iso}"}), 400

    # Strict 1:1 check
    existing_other = ChallengeCountry.query.filter(
        ChallengeCountry.country_iso == country_iso,
        ChallengeCountry.challenge_id != challenge_id
    ).first()

    if existing_other:
        other_chal = Challenges.query.filter_by(id=existing_other.challenge_id).first()
        other_name = other_chal.name if other_chal else f"#{existing_other.challenge_id}"
        return jsonify({
            "success": False,
            "message": f"Country '{country_iso}' is already assigned to challenge '{other_name}'. Each country can only be assigned to one challenge."
        }), 400

    cc = ChallengeCountry.query.filter_by(challenge_id=challenge_id).first()
    if cc:
        cc.country_iso = country_iso
        cc.bonus_first = bonus_first
        cc.bonus_second = bonus_second
        cc.bonus_third = bonus_third
        cc.bonus_fourth = bonus_fourth
        cc.bonus_fifth = bonus_fifth
    else:
        cc = ChallengeCountry(
            challenge_id=challenge_id,
            country_iso=country_iso,
            bonus_first=bonus_first,
            bonus_second=bonus_second,
            bonus_third=bonus_third,
            bonus_fourth=bonus_fourth,
            bonus_fifth=bonus_fifth,
        )
        db.session.add(cc)

    db.session.commit()
    cache.delete_memoized(get_country_mappings)
    return jsonify({
        "success": True,
        "data": {
            "challenge_id": challenge_id,
            "country_iso": country_iso,
            "bonus_first": bonus_first,
            "bonus_second": bonus_second,
            "bonus_third": bonus_third,
            "bonus_fourth": bonus_fourth,
            "bonus_fifth": bonus_fifth,
            "bonus_levels": [bonus_first, bonus_second, bonus_third, bonus_fourth, bonus_fifth],
        }
    })

def get_bool_config(key, default=False):
    val = get_config(key, default)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(val, int):
        return val != 0
    return bool(val)

@world_bp.route("/admin/world", methods=["GET"])
@admins_only
def admin_world_redirect():
    return redirect("/admin/theme_settings")

@world_bp.route("/admin/theme_settings", methods=["GET"])
@admins_only
def admin_theme_settings():
    challenges = Challenges.query.all()
    all_chal_to_iso, iso_to_chal = get_country_mappings()
    countries_data = load_countries_data()

    assigned_countries = {}
    for iso, cid in iso_to_chal.items():
        c_obj = Challenges.query.filter_by(id=cid).first()
        if c_obj:
            assigned_countries[iso] = {"id": c_obj.id, "name": c_obj.name}

    challenge_list = []
    for c in challenges:
        challenge_list.append({
            "id": c.id,
            "name": c.name,
            "category": c.category,
            "value": c.value,
            "assigned_country": all_chal_to_iso.get(c.id, ""),
        })

    theme_configs = {
        "scanlines_enabled": get_bool_config("world_scanlines_enabled", False),
        "crt_glow_enabled": get_bool_config("world_crt_glow_enabled", True),
        "zoom_animation_enabled": get_bool_config("world_zoom_animation_enabled", True),
        "grid_title": get_config("world_grid_title", "MATRIX COMMAND GRID"),
        "default_view": get_config("world_default_view", "map"),
        "live_feed_enabled": get_bool_config("world_live_feed_enabled", True),
        "live_feed_interval": int(get_config("world_live_feed_interval", 45) or 45),
        "live_feed_limit": int(get_config("world_live_feed_limit", 30) or 30),
        "live_feed_title": get_config("world_live_feed_title", "[ LIVE FEED ]"),
        "live_feed_subtitle": get_config("world_live_feed_subtitle", "ORBITAL UPLINK ACTIVE • REAL-TIME FEED"),
        "filter_all_nodes_enabled": get_bool_config("world_filter_all_nodes_enabled", True),
        "filter_breached_enabled": get_bool_config("world_filter_breached_enabled", True),
        "filter_hostile_enabled": get_bool_config("world_filter_hostile_enabled", True),
        "filter_counts_enabled": get_bool_config("world_filter_counts_enabled", True),
        "sector_filter_enabled": get_bool_config("world_sector_filter_enabled", True),
        "guide_enabled": get_bool_config("world_guide_enabled", True),
        "view_toggle_enabled": get_bool_config("world_view_toggle_enabled", True),
        "tutorial_enabled": get_bool_config("world_tutorial_enabled", True),
        "matrix_home_enabled": get_bool_config("world_matrix_home_enabled", True),
        "matrix_home_format": get_config("world_matrix_home_format", "html"),
        "matrix_home_content": get_config("world_matrix_home_content", ""),
        "matrix_terminal_header": get_config("world_matrix_terminal_header", "TERMINAL // CTF-NET HOST CONNECTION [ACTIVE]"),
        "matrix_status_text": get_config("world_matrix_status_text", "STATUS: OPERATIONAL // 0-DAY MATRIX ACTIVE"),
        "matrix_protocol_text": get_config("world_matrix_protocol_text", "PROTOCOL: GEOPOLITICAL CYBER WARFARE"),
        "matrix_nodes_text": get_config("world_matrix_nodes_text", "NODES: REAL-TIME GLOBAL TARGETS LOADED"),
        "matrix_typing_phrases": get_config("world_matrix_typing_phrases", "Wake up, Operative...\nThe Matrix has you...\nFollow the white rabbit.\nKnock, knock, Hacker."),
        "matrix_btn_primary_label": get_config("world_matrix_btn_primary_label", "ENTER THE GRID"),
        "matrix_btn_primary_url": get_config("world_matrix_btn_primary_url", "/challenges"),
        "matrix_btn_secondary_label": get_config("world_matrix_btn_secondary_label", "SCOREBOARD"),
        "matrix_btn_secondary_url": get_config("world_matrix_btn_secondary_url", "/scoreboard"),
        "countdown_enabled": get_bool_config("world_countdown_enabled", False),
        "countdown_target": get_config("world_countdown_target", ""),
        "countdown_format": get_config("world_countdown_format", "html"),
        "countdown_content": get_config("world_countdown_content", ""),
        "countdown_redirect": get_bool_config("world_countdown_redirect", True),
        "scoreboard_country_flags": get_bool_config("world_scoreboard_country_flags", True),
        "challenge_territory_badge": get_bool_config("world_challenge_territory_badge", True),
        "challenge_first_blood_badge": get_bool_config("world_challenge_first_blood_badge", True),
        "directory_show_team": get_bool_config("world_directory_show_team", True),
        "directory_show_website": get_bool_config("world_directory_show_website", True),
        "directory_show_affiliation": get_bool_config("world_directory_show_affiliation", True),
        "directory_show_country": get_bool_config("world_directory_show_country", True),
        "directory_show_custom_fields": get_bool_config("world_directory_show_custom_fields", True),
        "directory_custom_fields": get_config("world_directory_custom_fields", ""),
        "directory_table_view": get_bool_config("world_directory_table_view", True),
        "directory_card_view": get_bool_config("world_directory_card_view", True),
        "directory_default_view": get_config("world_directory_default_view", "table"),
        "search_enabled": get_bool_config("world_search_enabled", True),
        "global_dominance_enabled": get_bool_config("world_global_dominance_enabled", True),
        "accent_palette": get_config("world_accent_palette", "matrix_green"),
        "sound_effects_enabled": get_bool_config("world_sound_effects_enabled", True),
        "footer_text": get_config("world_footer_text", ""),
        "footer_url": get_config("world_footer_url", ""),
        "dominance_top_count": int(get_config("world_dominance_top_count", 4) or 4),
        "header_operative_directory": get_config("world_header_operative_directory", "[ OPERATIVE DIRECTORY ]"),
        "header_syndicate_directory": get_config("world_header_syndicate_directory", "[ SYNDICATE DIRECTORY ]"),
        "header_scoreboard_graph": get_config("world_header_scoreboard_graph", "[ ORBITAL SCOREBOARD TELEMETRY // TOP CONTENDERS ]"),
        "header_territory_dominance": get_config("world_header_territory_dominance", "[ GEOPOLITICAL TERRITORY DOMINANCE // TOP CONQUERORS ]"),
        "header_scoreboard_table": get_config("world_header_scoreboard_table", "[ OPERATIONAL LEADERBOARD ]"),
        "hide_language_selector": get_bool_config("world_hide_language_selector", False),
        "hide_theme_toggle": get_bool_config("world_hide_theme_toggle", False),
        "navbar_compact_mode": get_config("world_navbar_compact_mode", "auto"),
        "ctf_logo": get_config("ctf_logo"),
        "ctf_logo_light": get_config("ctf_logo_light"),
        "ctf_logo_dark": get_config("ctf_logo_dark"),
        "ctf_small_icon": get_config("ctf_small_icon"),
        "default_theme_mode": get_config("default_theme_mode", "dark"),
    }

    return render_template(
        "admin/theme_settings.html",
        challenges=challenge_list,
        countries=sorted(countries_data.values(), key=lambda x: x["name"]),
        assigned_countries=assigned_countries,
        theme_configs=theme_configs,
        ctf_logo=get_config("ctf_logo"),
        ctf_logo_light=get_config("ctf_logo_light"),
        ctf_logo_dark=get_config("ctf_logo_dark"),
        ctf_small_icon=get_config("ctf_small_icon"),
        default_theme_mode=get_config("default_theme_mode", "dark"),
    )

@world_bp.route("/api/v1/world/settings", methods=["GET", "POST"])
@ratelimit(method="GET", limit=60, interval=60)
def world_settings_api():
    if request.method in ("GET", "HEAD"):
        cache_key = "view/world_theme.world_settings_api"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            settings_payload = cached_data
        else:
            settings_payload = {
                "scanlines_enabled": get_bool_config("world_scanlines_enabled", False),
                "crt_glow_enabled": get_bool_config("world_crt_glow_enabled", True),
                "zoom_animation_enabled": get_bool_config("world_zoom_animation_enabled", True),
                "grid_title": get_config("world_grid_title", "MATRIX COMMAND GRID"),
                "default_view": get_config("world_default_view", "map"),
                "live_feed_enabled": get_bool_config("world_live_feed_enabled", True),
                "live_feed_interval": int(get_config("world_live_feed_interval", 45) or 45),
                "live_feed_limit": int(get_config("world_live_feed_limit", 30) or 30),
                "live_feed_title": get_config("world_live_feed_title", "[ LIVE FEED ]"),
                "live_feed_subtitle": get_config("world_live_feed_subtitle", "ORBITAL UPLINK ACTIVE • REAL-TIME FEED"),
                "filter_all_nodes_enabled": get_bool_config("world_filter_all_nodes_enabled", True),
                "filter_breached_enabled": get_bool_config("world_filter_breached_enabled", True),
                "filter_hostile_enabled": get_bool_config("world_filter_hostile_enabled", True),
                "filter_counts_enabled": get_bool_config("world_filter_counts_enabled", True),
                "sector_filter_enabled": get_bool_config("world_sector_filter_enabled", True),
                "guide_enabled": get_bool_config("world_guide_enabled", True),
                "view_toggle_enabled": get_bool_config("world_view_toggle_enabled", True),
                "tutorial_enabled": get_bool_config("world_tutorial_enabled", True),
                "matrix_home_enabled": get_bool_config("world_matrix_home_enabled", True),
                "matrix_home_format": get_config("world_matrix_home_format", "html"),
                "matrix_home_content": get_config("world_matrix_home_content", ""),
                "matrix_terminal_header": get_config("world_matrix_terminal_header", "TERMINAL // CTF-NET HOST CONNECTION [ACTIVE]"),
                "matrix_status_text": get_config("world_matrix_status_text", "STATUS: OPERATIONAL // 0-DAY MATRIX ACTIVE"),
                "matrix_protocol_text": get_config("world_matrix_protocol_text", "PROTOCOL: GEOPOLITICAL CYBER WARFARE"),
                "matrix_nodes_text": get_config("world_matrix_nodes_text", "NODES: REAL-TIME GLOBAL TARGETS LOADED"),
                "matrix_typing_phrases": get_config("world_matrix_typing_phrases", "Wake up, Operative...\nThe Matrix has you...\nFollow the white rabbit.\nKnock, knock, Hacker."),
                "matrix_btn_primary_label": get_config("world_matrix_btn_primary_label", "ENTER THE GRID"),
                "matrix_btn_primary_url": get_config("world_matrix_btn_primary_url", "/challenges"),
                "matrix_btn_secondary_label": get_config("world_matrix_btn_secondary_label", "SCOREBOARD"),
                "matrix_btn_secondary_url": get_config("world_matrix_btn_secondary_url", "/scoreboard"),
                "countdown_enabled": get_bool_config("world_countdown_enabled", False),
                "countdown_time": get_config("world_countdown_target") or get_config("start") or "",
                "countdown_target": get_config("world_countdown_target") or get_config("start") or "",
                "countdown_format": get_config("world_countdown_format", "html"),
                "countdown_content": get_config("world_countdown_content", ""),
                "countdown_redirect": get_bool_config("world_countdown_redirect", True),
                "scoreboard_country_flags": get_bool_config("world_scoreboard_country_flags", True),
                "challenge_territory_badge": get_bool_config("world_challenge_territory_badge", True),
                "challenge_first_blood_badge": get_bool_config("world_challenge_first_blood_badge", True),
                "directory_show_team": get_bool_config("world_directory_show_team", True),
                "directory_show_website": get_bool_config("world_directory_show_website", True),
                "directory_show_affiliation": get_bool_config("world_directory_show_affiliation", True),
                "directory_show_country": get_bool_config("world_directory_show_country", True),
                "directory_show_custom_fields": get_bool_config("world_directory_show_custom_fields", True),
                "directory_custom_fields": get_config("world_directory_custom_fields", ""),
                "directory_table_view": get_bool_config("world_directory_table_view", True),
                "directory_card_view": get_bool_config("world_directory_card_view", True),
                "directory_default_view": get_config("world_directory_default_view", "table"),
                "search_enabled": get_bool_config("world_search_enabled", True),
                "global_dominance_enabled": get_bool_config("world_global_dominance_enabled", True),
                "accent_palette": get_config("world_accent_palette", "matrix_green"),
                "sound_effects_enabled": get_bool_config("world_sound_effects_enabled", True),
                "footer_text": get_config("world_footer_text", ""),
                "world_footer_text": get_config("world_footer_text", ""),
                "footer_url": get_config("world_footer_url", ""),
                "world_footer_url": get_config("world_footer_url", ""),
                "dominance_top_count": int(get_config("world_dominance_top_count", 4) or 4),
                "world_dominance_top_count": int(get_config("world_dominance_top_count", 4) or 4),
                "header_operative_directory": get_config("world_header_operative_directory", "[ OPERATIVE DIRECTORY ]"),
                "world_header_operative_directory": get_config("world_header_operative_directory", "[ OPERATIVE DIRECTORY ]"),
                "header_syndicate_directory": get_config("world_header_syndicate_directory", "[ SYNDICATE DIRECTORY ]"),
                "world_header_syndicate_directory": get_config("world_header_syndicate_directory", "[ SYNDICATE DIRECTORY ]"),
                "header_scoreboard_graph": get_config("world_header_scoreboard_graph", "[ ORBITAL SCOREBOARD TELEMETRY // TOP CONTENDERS ]"),
                "world_header_scoreboard_graph": get_config("world_header_scoreboard_graph", "[ ORBITAL SCOREBOARD TELEMETRY // TOP CONTENDERS ]"),
                "header_territory_dominance": get_config("world_header_territory_dominance", "[ GEOPOLITICAL TERRITORY DOMINANCE // TOP CONQUERORS ]"),
                "world_header_territory_dominance": get_config("world_header_territory_dominance", "[ GEOPOLITICAL TERRITORY DOMINANCE // TOP CONQUERORS ]"),
                "header_scoreboard_table": get_config("world_header_scoreboard_table", "[ OPERATIONAL LEADERBOARD ]"),
                "world_header_scoreboard_table": get_config("world_header_scoreboard_table", "[ OPERATIONAL LEADERBOARD ]"),
                "hide_language_selector": get_bool_config("world_hide_language_selector", False),
                "world_hide_language_selector": get_bool_config("world_hide_language_selector", False),
                "hide_theme_toggle": get_bool_config("world_hide_theme_toggle", False),
                "world_hide_theme_toggle": get_bool_config("world_hide_theme_toggle", False),
                "navbar_compact_mode": get_config("world_navbar_compact_mode", "auto"),
                "world_navbar_compact_mode": get_config("world_navbar_compact_mode", "auto"),
                "default_theme_mode": get_config("default_theme_mode", "dark"),
                "ctf_logo": get_config("ctf_logo"),
                "ctf_logo_light": get_config("ctf_logo_light"),
                "ctf_logo_dark": get_config("ctf_logo_dark"),
                "ctf_small_icon": get_config("ctf_small_icon"),
        }
        cache.set(cache_key, settings_payload, timeout=120)

        settings_hash = hashlib.md5(json.dumps(settings_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        etag = f'"wsettings-{settings_hash}"'
        if request.headers.get("If-None-Match") == etag:
            resp = make_response("", 304)
            resp.headers["ETag"] = etag
            resp.headers["Cache-Control"] = "public, max-age=60, must-revalidate"
            return resp

        resp = jsonify({
            "success": True,
            "data": settings_payload
        })
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "public, max-age=60, must-revalidate"
        return resp

    # POST requires admin
    if not is_admin():
        return jsonify({"success": False, "message": "Admin privileges required"}), 403

    data = request.get_json() or request.form

    if "scanlines_enabled" in data:
        set_config("world_scanlines_enabled", "true" if data.get("scanlines_enabled") in (True, "true", "on", 1) else "false")
    if "crt_glow_enabled" in data:
        set_config("world_crt_glow_enabled", "true" if data.get("crt_glow_enabled") in (True, "true", "on", 1) else "false")
    if "zoom_animation_enabled" in data:
        set_config("world_zoom_animation_enabled", "true" if data.get("zoom_animation_enabled") in (True, "true", "on", 1) else "false")
    if "grid_title" in data:
        set_config("world_grid_title", (data.get("grid_title") or "MATRIX COMMAND GRID").strip())
    if "default_view" in data:
        set_config("world_default_view", "grid" if data.get("default_view") == "grid" else "map")

    if "live_feed_enabled" in data:
        set_config("world_live_feed_enabled", "true" if data.get("live_feed_enabled") in (True, "true", "on", 1) else "false")
    if "live_feed_interval" in data:
        set_config("world_live_feed_interval", str(max(20, int(data.get("live_feed_interval", 45) or 45))))
    if "live_feed_limit" in data:
        set_config("world_live_feed_limit", str(max(5, int(data.get("live_feed_limit", 30) or 30))))
    if "live_feed_title" in data:
        set_config("world_live_feed_title", (data.get("live_feed_title") or "[ LIVE FEED ]").strip())
    if "live_feed_subtitle" in data:
        set_config("world_live_feed_subtitle", (data.get("live_feed_subtitle") or "ORBITAL UPLINK ACTIVE • REAL-TIME FEED").strip())

    if "filter_all_nodes_enabled" in data:
        set_config("world_filter_all_nodes_enabled", "true" if data.get("filter_all_nodes_enabled") in (True, "true", "on", 1) else "false")
    if "filter_breached_enabled" in data:
        set_config("world_filter_breached_enabled", "true" if data.get("filter_breached_enabled") in (True, "true", "on", 1) else "false")
    if "filter_hostile_enabled" in data:
        set_config("world_filter_hostile_enabled", "true" if data.get("filter_hostile_enabled") in (True, "true", "on", 1) else "false")
    if "filter_counts_enabled" in data:
        set_config("world_filter_counts_enabled", "true" if data.get("filter_counts_enabled") in (True, "true", "on", 1) else "false")
    if "sector_filter_enabled" in data:
        set_config("world_sector_filter_enabled", "true" if data.get("sector_filter_enabled") in (True, "true", "on", 1) else "false")
    if "guide_enabled" in data:
        set_config("world_guide_enabled", "true" if data.get("guide_enabled") in (True, "true", "on", 1) else "false")
    if "view_toggle_enabled" in data:
        set_config("world_view_toggle_enabled", "true" if data.get("view_toggle_enabled") in (True, "true", "on", 1) else "false")

    if "matrix_home_enabled" in data:
        set_config("world_matrix_home_enabled", "true" if data.get("matrix_home_enabled") in (True, "true", "on", 1) else "false")
    if "matrix_home_format" in data:
        set_config("world_matrix_home_format", (data.get("matrix_home_format") or "html").strip())
    if "matrix_home_content" in data:
        set_config("world_matrix_home_content", data.get("matrix_home_content", ""))
    if "matrix_terminal_header" in data:
        set_config("world_matrix_terminal_header", (data.get("matrix_terminal_header") or "TERMINAL // CTF-NET HOST CONNECTION [ACTIVE]").strip())
    if "matrix_status_text" in data:
        set_config("world_matrix_status_text", (data.get("matrix_status_text") or "STATUS: OPERATIONAL // 0-DAY MATRIX ACTIVE").strip())
    if "matrix_protocol_text" in data:
        set_config("world_matrix_protocol_text", (data.get("matrix_protocol_text") or "PROTOCOL: GEOPOLITICAL CYBER WARFARE").strip())
    if "matrix_nodes_text" in data:
        set_config("world_matrix_nodes_text", (data.get("matrix_nodes_text") or "NODES: REAL-TIME GLOBAL TARGETS LOADED").strip())
    if "matrix_typing_phrases" in data:
        set_config("world_matrix_typing_phrases", data.get("matrix_typing_phrases") or "")
    if "matrix_btn_primary_label" in data:
        set_config("world_matrix_btn_primary_label", (data.get("matrix_btn_primary_label") or "ENTER THE GRID").strip())
    if "matrix_btn_primary_url" in data:
        set_config("world_matrix_btn_primary_url", (data.get("matrix_btn_primary_url") or "/challenges").strip())
    if "matrix_btn_secondary_label" in data:
        set_config("world_matrix_btn_secondary_label", (data.get("matrix_btn_secondary_label") or "SCOREBOARD").strip())
    if "matrix_btn_secondary_url" in data:
        set_config("world_matrix_btn_secondary_url", (data.get("matrix_btn_secondary_url") or "/scoreboard").strip())

    if "tutorial_enabled" in data:
        set_config("world_tutorial_enabled", "true" if data.get("tutorial_enabled") in (True, "true", "on", 1) else "false")

    if "countdown_enabled" in data:
        set_config("world_countdown_enabled", "true" if data.get("countdown_enabled") in (True, "true", "on", 1) else "false")
    if "countdown_target" in data:
        set_config("world_countdown_target", (data.get("countdown_target") or "").strip())
    if "countdown_time" in data:
        set_config("world_countdown_target", (data.get("countdown_time") or "").strip())
    if "countdown_format" in data:
        set_config("world_countdown_format", (data.get("countdown_format") or "html").strip())
    if "countdown_content" in data:
        set_config("world_countdown_content", data.get("countdown_content", ""))
    if "countdown_redirect" in data:
        set_config("world_countdown_redirect", "true" if data.get("countdown_redirect") in (True, "true", "on", 1) else "false")

    if "scoreboard_country_flags" in data:
        set_config("world_scoreboard_country_flags", "true" if data.get("scoreboard_country_flags") in (True, "true", "on", 1) else "false")
    if "challenge_territory_badge" in data:
        set_config("world_challenge_territory_badge", "true" if data.get("challenge_territory_badge") in (True, "true", "on", 1) else "false")
    if "challenge_first_blood_badge" in data:
        set_config("world_challenge_first_blood_badge", "true" if data.get("challenge_first_blood_badge") in (True, "true", "on", 1) else "false")
    if "directory_show_team" in data:
        set_config("world_directory_show_team", "true" if data.get("directory_show_team") in (True, "true", "on", 1) else "false")
    if "directory_show_website" in data:
        set_config("world_directory_show_website", "true" if data.get("directory_show_website") in (True, "true", "on", 1) else "false")
    if "directory_show_affiliation" in data:
        set_config("world_directory_show_affiliation", "true" if data.get("directory_show_affiliation") in (True, "true", "on", 1) else "false")
    if "directory_show_country" in data:
        set_config("world_directory_show_country", "true" if data.get("directory_show_country") in (True, "true", "on", 1) else "false")
    if "directory_show_custom_fields" in data:
        set_config("world_directory_show_custom_fields", "true" if data.get("directory_show_custom_fields") in (True, "true", "on", 1) else "false")
    if "directory_custom_fields" in data:
        set_config("world_directory_custom_fields", (data.get("directory_custom_fields") or "").strip())
    if "directory_table_view" in data:
        set_config("world_directory_table_view", "true" if data.get("directory_table_view") in (True, "true", "on", 1) else "false")
    if "directory_card_view" in data:
        set_config("world_directory_card_view", "true" if data.get("directory_card_view") in (True, "true", "on", 1) else "false")
    if "directory_default_view" in data:
        set_config("world_directory_default_view", "card" if data.get("directory_default_view") == "card" else "table")
    if "search_enabled" in data:
        set_config("world_search_enabled", "true" if data.get("search_enabled") in (True, "true", "on", 1) else "false")
    if "global_dominance_enabled" in data:
        set_config("world_global_dominance_enabled", "true" if data.get("global_dominance_enabled") in (True, "true", "on", 1) else "false")
    if "accent_palette" in data:
        palette = (data.get("accent_palette") or "matrix_green").strip().lower()
        if palette not in ("matrix_green", "cyberpunk_cyan", "solar_amber", "hostile_crimson"):
            palette = "matrix_green"
        set_config("world_accent_palette", palette)
    if "sound_effects_enabled" in data:
        set_config("world_sound_effects_enabled", "true" if data.get("sound_effects_enabled") in (True, "true", "on", 1) else "false")
    if "footer_text" in data or "world_footer_text" in data:
        val = data.get("world_footer_text") if "world_footer_text" in data else data.get("footer_text")
        set_config("world_footer_text", (val or "").strip())
    if "footer_url" in data or "world_footer_url" in data:
        val = data.get("world_footer_url") if "world_footer_url" in data else data.get("footer_url")
        set_config("world_footer_url", (val or "").strip())
    if "dominance_top_count" in data or "world_dominance_top_count" in data:
        val = data.get("world_dominance_top_count") if "world_dominance_top_count" in data else data.get("dominance_top_count")
        try:
            val_int = max(1, min(20, int(val or 4)))
            set_config("world_dominance_top_count", str(val_int))
        except (ValueError, TypeError):
            pass
    if "header_operative_directory" in data or "world_header_operative_directory" in data:
        val = data.get("world_header_operative_directory") if "world_header_operative_directory" in data else data.get("header_operative_directory")
        set_config("world_header_operative_directory", (val or "[ OPERATIVE DIRECTORY ]").strip())
    if "header_syndicate_directory" in data or "world_header_syndicate_directory" in data:
        val = data.get("world_header_syndicate_directory") if "world_header_syndicate_directory" in data else data.get("header_syndicate_directory")
        set_config("world_header_syndicate_directory", (val or "[ SYNDICATE DIRECTORY ]").strip())
    if "header_scoreboard_graph" in data or "world_header_scoreboard_graph" in data:
        val = data.get("world_header_scoreboard_graph") if "world_header_scoreboard_graph" in data else data.get("header_scoreboard_graph")
        set_config("world_header_scoreboard_graph", (val or "[ ORBITAL SCOREBOARD TELEMETRY // TOP CONTENDERS ]").strip())
    if "header_territory_dominance" in data or "world_header_territory_dominance" in data:
        val = data.get("world_header_territory_dominance") if "world_header_territory_dominance" in data else data.get("header_territory_dominance")
        set_config("world_header_territory_dominance", (val or "[ GEOPOLITICAL TERRITORY DOMINANCE // TOP CONQUERORS ]").strip())
    if "header_scoreboard_table" in data or "world_header_scoreboard_table" in data:
        val = data.get("world_header_scoreboard_table") if "world_header_scoreboard_table" in data else data.get("header_scoreboard_table")
        set_config("world_header_scoreboard_table", (val or "[ OPERATIONAL LEADERBOARD ]").strip())
    if "hide_language_selector" in data or "world_hide_language_selector" in data:
        val = data.get("world_hide_language_selector") if "world_hide_language_selector" in data else data.get("hide_language_selector")
        set_config("world_hide_language_selector", "true" if val in (True, "true", "on", 1) else "false")
    if "hide_theme_toggle" in data or "world_hide_theme_toggle" in data:
        val = data.get("world_hide_theme_toggle") if "world_hide_theme_toggle" in data else data.get("hide_theme_toggle")
        set_config("world_hide_theme_toggle", "true" if val in (True, "true", "on", 1) else "false")
    if "navbar_compact_mode" in data or "world_navbar_compact_mode" in data:
        val = data.get("world_navbar_compact_mode") if "world_navbar_compact_mode" in data else data.get("navbar_compact_mode")
        set_config("world_navbar_compact_mode", (val or "auto").strip().lower())
    if "default_theme_mode" in data:
        val = data.get("default_theme_mode")
        if val in ("dark", "light"):
            set_config("default_theme_mode", val)
    if "ctf_logo_light" in data:
        set_config("ctf_logo_light", data.get("ctf_logo_light"))
    if "ctf_logo_dark" in data:
        set_config("ctf_logo_dark", data.get("ctf_logo_dark"))
    if "ctf_small_icon" in data:
        set_config("ctf_small_icon", data.get("ctf_small_icon"))

    try:
        from CTFd.cache import clear_config
        clear_config()
    except Exception:
        pass
    try:
        cache.delete("view/world_theme.world_settings_api")
    except Exception:
        pass

    return jsonify({
        "success": True, 
        "message": "Theme Settings updated successfully!",
        "data": {
            "footer_text": get_config("world_footer_text", ""),
            "world_footer_text": get_config("world_footer_text", ""),
            "footer_url": get_config("world_footer_url", ""),
            "world_footer_url": get_config("world_footer_url", ""),
            "dominance_top_count": int(get_config("world_dominance_top_count", 4) or 4),
            "world_dominance_top_count": int(get_config("world_dominance_top_count", 4) or 4),
            "header_operative_directory": get_config("world_header_operative_directory", "[ OPERATIVE DIRECTORY ]"),
            "world_header_operative_directory": get_config("world_header_operative_directory", "[ OPERATIVE DIRECTORY ]"),
            "header_syndicate_directory": get_config("world_header_syndicate_directory", "[ SYNDICATE DIRECTORY ]"),
            "world_header_syndicate_directory": get_config("world_header_syndicate_directory", "[ SYNDICATE DIRECTORY ]"),
            "header_scoreboard_graph": get_config("world_header_scoreboard_graph", "[ ORBITAL SCOREBOARD TELEMETRY // TOP CONTENDERS ]"),
            "world_header_scoreboard_graph": get_config("world_header_scoreboard_graph", "[ ORBITAL SCOREBOARD TELEMETRY // TOP CONTENDERS ]"),
            "header_territory_dominance": get_config("world_header_territory_dominance", "[ GEOPOLITICAL TERRITORY DOMINANCE // TOP CONQUERORS ]"),
            "world_header_territory_dominance": get_config("world_header_territory_dominance", "[ GEOPOLITICAL TERRITORY DOMINANCE // TOP CONQUERORS ]"),
            "header_scoreboard_table": get_config("world_header_scoreboard_table", "[ OPERATIONAL LEADERBOARD ]"),
            "world_header_scoreboard_table": get_config("world_header_scoreboard_table", "[ OPERATIONAL LEADERBOARD ]"),
            "hide_language_selector": get_bool_config("world_hide_language_selector", False),
            "world_hide_language_selector": get_bool_config("world_hide_language_selector", False),
            "hide_theme_toggle": get_bool_config("world_hide_theme_toggle", False),
            "world_hide_theme_toggle": get_bool_config("world_hide_theme_toggle", False),
            "navbar_compact_mode": get_config("world_navbar_compact_mode", "auto"),
            "world_navbar_compact_mode": get_config("world_navbar_compact_mode", "auto"),
        }
    })

@world_bp.route("/countdown", methods=["GET"])
def countdown_page():
    countdown_config = {
        "target": get_config("world_countdown_target") or get_config("start") or "",
        "format": get_config("world_countdown_format", "html"),
        "content": get_config("world_countdown_content", ""),
        "redirect": get_bool_config("world_countdown_redirect", True),
    }
    return render_template("countdown.html", config=countdown_config)
