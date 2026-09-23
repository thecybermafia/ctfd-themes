# 🌐 CTFd World Tactical Warfare Theme & Companion Plugin

An immersive, military-grade cyberpunk world map interface and gamification engine for [CTFd](https://ctfd.io/). Transforms traditional CTF challenges into a global cyberwarfare operations theater where competitors breach territories, capture hostile nodes, and intercept live network telemetry.

Developed and defensively hardened by **CyberMafia**.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Security Audited](https://img.shields.io/badge/Security%20Audit-Defensively%20Hardened-brightgreen.svg)](#-security-audit--defensive-hardening)
[![CTFd Compatibility](https://img.shields.io/badge/CTFd-v3.5%20--%20v3.8%2B-orange.svg)](https://github.com/CTFd/CTFd)

---

## 🏛️ Architecture Overview

The World Theme consists of two integrated components:
1. **`world/`**: The complete frontend CTFd theme (`CTFd/themes/world/`) containing custom cyberpunk templates, styles, SVG vector maps, HUD overlays, and sound synthesizers.
2. **`world_theme/`**: The backend companion plugin (`CTFd/plugins/world_theme/`) powering real-time country assignment APIs, live feed telemetry streams, multi-tier first blood bonuses, and admin configuration controls.

---

## ⚡ Key Features

### 🗺️ Global Tactical Warfare Map
- **176 Interactive SVG Countries**: High-definition vector map supporting 176 sovereign territories with fluid zoom, pan, and hover animations.
- **Calibrated Land Centroids**: Every country beacon is mathematically positioned inside landmass bounds using polylabel algorithms (including multi-island nations like the United States Lower 48, Japan, Australia, and New Zealand).
- **Territory Status Visualizations**:
  - 🟢 **Breached (You)**: Glowing neon green land highlight indicating territories compromised by your team.
  - 🔴 **Hostile Presence**: Territories breached by rival teams display tactical red radar icons while preserving clean land styling.
  - ⚪ **Unclaimed**: Neutral dark cyber grid awaiting initial compromise.

### 📡 Real-Time Live Feed Telemetry
- **Live Event Stream**: Real-time ticker streaming first blood compromises, tactical solves, and territory captures.
- **Interactive Links**:
  - **Operator Squads**: Clicking a team name opens their public dossier in a new tab.
  - **Challenge Nodes**: Clicking a challenge title instantly triggers the tactical briefing modal in-place.
- **Persistent State Drawer**: Competitors can minimize or expand the Live Feed drawer; state is remembered across page reloads via `localStorage`.

### 💻 Retro Matrix Terminal Homepage
- **Cyberpunk Terminal**: Animated terminal interface with typewriter animations, blinking command prompts, and operational diagnostics.
- **Auto-Replay**: Automatically reinitializes animations on page refresh for maximum immersion.
- **Dynamic Admin Content**: Terminal cards, typewriter phrases, buttons, and redirect targets can be toggled and configured directly from the admin panel in markdown or HTML.

### 🎛️ Tactical HUD & Filtering System
- **Real-Time Stats Counter**: Breached territories, compromised flags, score totals, and active operators.
- **Sectors Dropdown**: Filter visible map nodes by geographic region (Americas, Europe, Asia-Pacific, Africa, Middle East).
- **View Toggle**: Switch effortlessly between the Tactical World Map and a high-density Matrix Grid View.
- **Interactive Guide Button**: Instant access to mission rules and operational briefings.

### 📊 Orbital Scoreboard Telemetry
- Dark cybernetic scoreboard table with glowing neon ranking badges and integrated ECharts progression telemetry.

### ⚙️ Dedicated Admin Console (`/admin/theme_settings`)
- **Visual Effects**: Toggle scanlines, CRT screen glow, and zoom transitions.
- **Warfare Modules**: Enable or disable Live Feed, Sector Filters, Guide Button, Grid View Toggle, and Countdown redirects.
- **Homepage Terminal Tab**: Live toggle and custom content editor for the terminal intro card.
- **Country Assignment Matrix**: Assign challenges to any country with 1:1 uniqueness validation, custom country codes, and multi-tier bonus points (1st, 2nd, and 3rd solver awards).

---

## 🔒 Security Audit & Defensive Hardening

The World Theme and its companion plugin have undergone an end-to-end security audit:
- **Zero Information Leakage**: Challenges in a `hidden` state are filtered from `/api/v1/world/countries` and `/api/v1/world/feed` for standard competitors.
- **Scoreboard Privacy**: When `score_visibility` is restricted to admins, non-admin live feeds suppress solve telemetry.
- **Bonus Clamp Verification**: Bonus point values are strictly clamped between 0 and 100,000 to prevent score corruption.
- **Race Condition & Duplicate Award Protection**: Bonus queries verify team identity to ensure awards are granted exactly once per squad.
- **Accessibility & WAI-ARIA Compliance**: Modal windows utilize proper focus handling to prevent `aria-hidden` descendant warnings.

---

## 🚀 Installation & Deployment

### Step 1: Copy Files into your CTFd Instance

Copy the theme and companion plugin into your CTFd directory:
```bash
# 1. Copy the world theme to CTFd themes directory
cp -r world /path/to/CTFd/CTFd/themes/

# 2. Copy the world_theme plugin to CTFd plugins directory
cp -r world_theme /path/to/CTFd/CTFd/plugins/
```

### Step 2: Restart CTFd

```bash
docker compose restart ctfd
# Or for systemd / gunicorn:
sudo systemctl restart ctfd
```

### Step 3: Activate the Theme

1. Log into your CTFd instance as an administrator.
2. Navigate to **Admin Panel > Config > Theme**.
3. Select **world** from the theme dropdown and click **Update**.
4. Navigate to **Admin Panel > World Theme Settings** (`/admin/theme_settings`) to customize your tactical operations center!

---

## 📜 Attribution & License

This project is licensed under the **Apache License 2.0** with mandatory attribution.

### Attribution Requirements (Section 4d of Apache 2.0)
You are free to use, fork, and modify this software provided that:
1. **Notice File**: You must preserve the `NOTICE` file in all redistributions and derivative works.
2. **Prominent Credit**:
   - The theme attribution link in the website footer must be preserved:
     ```text
     Theme: World by CyberMafia (https://github.com/thecybermafia/ctfd-world-theme)
     ```
   - In any public CTF competition or promotional media using this theme, visible attribution to **CyberMafia** is required.
3. **State Changes**: Any modified files must carry prominent notices documenting that changes were made.

See [LICENSE](LICENSE) and [NOTICE](NOTICE) for full terms.
