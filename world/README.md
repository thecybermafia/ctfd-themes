# CTFd World Matrix Theme (Tactical Cyber Warfare Theme)

A tactical, map-centric cyber warfare theme for CTFd inspired by modern cyber-range operations and visual mission control interfaces. Built on Bootstrap 5, Alpine.js, and Leaflet.js with complete dark and light mode support.

---

## 🛰️ Core Features & Highlights

### 1. Interactive Tactical Gameboard (`/challenges`)
- **GeoJSON World Map**: Full interactive vector world map featuring 280+ countries with custom node pins, dynamic country borders, and responsive coordinate projection.
- **Node Filtering Cluster**:
  - **All Nodes**: View all active combat nodes across the globe.
  - **Breached (You)**: Highlights nodes compromised by you or your team (green tactical beacons).
  - **Hostile**: Highlights nodes claimed by competing teams (red hostile indicators).
  - **Sector Select**: Dropdown filter to focus on specific challenge categories (e.g. Web, Crypto, Reverse, Pwn, OSINT).
  - **Toggleable Challenge Counts**: Admin can configure whether numeric solve counts e.g. `(282)`, `(11)` appear next to node filter buttons.
- **Multi-Modal Viewing**:
  - **Map View**: Full-screen tactical world map with zoom controls, reset coordinate centering, and live sector beacons.
  - **Grid View**: Instant toggle to an organized, categorical matrix grid view for fast challenge browsing.
- **Integrated Custom Challenge Views**:
  - Native modals for standard challenges, dynamic scoring challenges, photo/image verification challenges, interactive bingo boards, crossword puzzles, and textarea writeup reviews.

### 2. Tactical Live Activity Feed Drawer
- **Slide-Out Command Drawer**: One-click slide-out panel accessible via the HUD navbar (`LIVE FEED`).
- **Telemetry Streaming**: Real-time polling showing solves, first blood announcements, team registrations, recruit qualifications, and system notifications.
- **Adaptive Visual Theming**: Seamless dark and light mode styling with clean badge contrasts, smooth scroll telemetry, and zero backdrop bleeding.

### 3. Interactive Tactical Onboarding Guide
- **5-Step Interactive Walkthrough**:
  - *Step 1*: Strategic Concept & Objectives.
  - *Step 2*: World Map Navigation & Controls (with automatic map camera pan & zoom demo).
  - *Step 3*: Sector Classification & Filtering.
  - *Step 4*: Infiltrating a Country Node & Flag Submission.
  - *Step 5*: Live Intelligence Feed & Team Telemetry.
- Remembers dismissal status in local browser state and can be reopened anytime via the `GUIDE` button in the HUD.

### 4. Matrix Command Homepage
- **Digital Rain Canvas**: Sleek canvas matrix rain animation matching the tactical cyber theme.
- **Quick Deployment Actions**: Direct shortcuts to Challenges, Scoreboard, and Team Syndicate terminals.

### 5. Settings & Recruitment Hub (`/settings`)
- Dedicated **Referrals** tab embedded directly within participant settings when hidden from the main navbar.
- Displays personal recruitment directives, invite codes, 1-click clipboard copy buttons, and real-time recruited operatives rosters with progress bars.

### 6. Admin Control Panel (`/admin/theme_settings`)
Super-configurable administration panel:
- **Challenge Count Display**: Enable or disable numeric counts next to All Nodes, Breached, and Hostile filter buttons.
- **Sector Filtering**: Toggle sector dropdown on the gameboard HUD.
- **Tactical Guide**: Enable or disable the interactive tutorial button.
- **Live Feed Drawer**: Enable or disable the real-time activity feed slide-out.
- **Matrix Rain Animation**: Enable or disable the canvas effect on the homepage.
- **Node Visibility**: Individually toggle display of All Nodes, Breached, and Hostile filters.

---

## 🚀 Installation

1. Copy the `world/` folder into your CTFd themes directory:
   ```bash
   cp -r world /opt/CTFd/CTFd/themes/
   ```
2. In CTFd Admin Panel, navigate to **Config > Theme** and select **world**.
3. Configure theme parameters under **Plugins > World Theme Settings** (`/admin/theme_settings`).

---

## 🛠️ Development & Building

The theme source code is structured as follows:
- `templates/`: Jinja2 template files (`base.html`, `challenges.html`, `settings.html`, etc.).
- `assets/`: Uncompiled SCSS styles and ES6 JavaScript sources.
- `static/`: Compiled distribution CSS and JS bundles.

To rebuild assets:
```bash
yarn install
yarn build
```

---

## 📜 License
Apache-2.0
