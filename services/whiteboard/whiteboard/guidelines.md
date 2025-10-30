# Whiteboard – Working Guidelines

Last updated: 2025-10-29 19:15 (updated)
Owner: team

IMPORTANT: Always-Update Rule
- These guidelines must be kept up to date. Whenever you add a feature, change behavior, restructure files, or adjust workflows, update this document in the same change (same PR/commit) with a concise summary of what changed and the current state.

## Project Summary
- Purpose: A lightweight planning “whiteboard” for production (VFX/animation/games) to visualize Shots and Assets across weekdays, assign artists or groups to tasks, annotate, and publish changes back to ShotGrid/Shotgun.
- Tech stack:
  - Backend: FastAPI app serving a small REST API and static assets. Key domain models are in `whiteboard/models.py`. Endpoints expose projects, weekly boards, assignments, and publishing.
  - Frontend: Static web UI (index + JS + CSS) under `whiteboard/static/` that renders boards Mon–Fri for current and upcoming weeks, supports drag-and-drop of items and artist thumbnails, selection of tasks, and a Publish dialog. (There is also a proto area under `proto/` used during early iterations.)
  - Integrations: ShotGrid/Shotgun via helper functions (see `whiteboard/sg_helpers.py` or the backend helpers). Artist thumbnails and entity thumbnails are displayed; deterministic identicons or solid-color placeholders are used when images are missing.
- Core concepts:
  - Entities: `Shot` and `Asset`
  - Boards: per weekday (Mon–Fri) for multiple weeks (current + next weeks)
  - Items: cards for shots/assets with parent info (sequence or asset type) and thumbnails
  - Artists: users or groups, with avatars
  - Assignments: artist/group + task per shot; UI shows task color on avatar outline
  - Annotations: per-project annotations with text + color
  - Moves: drag cards across days/weeks; pending changes are batched and can be published

## Repository Layout (top-level)
- `whiteboard/` – main application
  - `app.py` – FastAPI routes, static mount, request handlers
  - `models.py` – Pydantic models and enums (`Day`, `Week`, `EntityType`, etc.)
  - `sg_helpers.py` & `helpers.py` – ShotGrid helpers and UI helpers (thumbnails, dates); in some setups these live under a `backend` subpackage
  - `static/` – frontend assets: `index.html`, `app.js` (or `App.jsx` in newer setups), `styles.css`, `favicon.png`
  - `README.md` – local TODOs and testing notes
- `proto/` – prototype server/UI and notes used during initial development (`whiteboard_proto.py`, `README.md`)

## Key API Endpoints (representative)
- `GET /` – serves the UI
- `GET /api/projects` – list available projects
- `GET /api/tasks?project_id=<id>` – load tasks per entity for a project
- `GET /api/week/{week}?project_id=<id>` – load a weekly snapshot (boards, items, artists, assignments, annotations)
- `POST /api/move_item` – move an item to another week/day
- `POST /api/remove_due_date` – remove due date for an item (moves to No Due Date)
- `POST /api/assign` – assign an artist/group to a shot task
- `POST /api/unassign` – unassign an artist/group from a task
- `GET /api/annotations` – fetch per-project annotations
- `POST /api/annotations` – set or remove a per-project annotation
- `GET /api/changes` – list local pending changes
- `POST /api/publish` – publish changes to ShotGrid/Shotgun

## What’s Been Done So Far (high level)
- Projects & datasets
  - Projects dropdown populated from ShotGrid [done]
  - Project code included in the URL for shareability [done]
- Artists & groups
  - Query project artists; display thumbnails; fall back to generated identicons when absent [done]
  - Display groups with thumbnails when available [done]
- Shots & assets
  - Query shots with delivery dates and place them on the correct weekday boards [done]
  - Query assets similarly (where applicable) [done]
  - Use real entity thumbnails or solid-color placeholders [done]
  - Naming conventions: shots like `seq001_s1020`; assets like `chair`, `table`, etc. [done]
- Boards & navigation
  - Boards for current week plus upcoming weeks [done]
  - Horizontal overflow with bars/scroll when content exceeds width [done]
  - Highlight the current day’s board [done]
- Drag & drop interactions
  - Drag a shot or asset card to another day/week [done]
  - Drag an artist thumbnail onto a shot to assign; show task picker; apply task color to avatar outline; larger outline for visibility [done]
  - Bugfix: restored drag/drop for shots after 404 on `/api/move_week_day` [done]
- Tasks & annotations
  - Discover tasks from project; store/reflect per entity [done]
  - Per-project annotations with text and color; normalized on load [done]
- Publish workflow
  - Modal dialog lists pending changes with Publish/Cancel [done]
  - Publish pushes assignments/moves to ShotGrid; errors logged [done]
- Polishing & fixes
  - Thumbnails scaled to remain fully visible in shot cards [done]
  - On load, ensure artist assignments reflect current state [done]

## Open Items / Next Work
- See `whiteboard/README.md` for current TODOs, including:
  - Add button/menu to remove due date from an item
  - Fetch tasks per entity rather than sampling across the whole project
  - Prepare/prod deployment versioning (`0.0.0-prod` addon)

## Conventions & Practices
- Keep API and UI in sync; when adding endpoints, document them here and wire the frontend.
- Use deterministic placeholder images for missing thumbnails to avoid broken UIs.
- Preserve drag-and-drop affordances with clear visual feedback and keyboard/mouse accessibility where practical.
- When integrating ShotGrid, prefer robust error handling; log exceptions without breaking the UI.

## CodeStyle
- keep it simple as much as possible
- avoid using too much comments, code should speak for itselt
- use full name varibles ie. pid -> project_id, a -> artist

## How to Contribute
- For any change that affects behavior, data shape, or UX flows:
  1) Update this `guidelines.md` (this file) with a summary of the change and any new conventions.
  2) Update `whiteboard/README.md` TODOs/tests accordingly.
  3) If endpoints or models changed, document them in the Key API Endpoints section above.
  4) If the change is experimental, note it under `proto/` and reference it here.

## Changelog (human-friendly)
- the project started as pure javascrip, check the app_deprecated.js file to see the history
- 2025-10-29: First consolidated guidelines created with project summary, completed work recap, open items, and the Always-Update rule.
- 2025-10-29 10:29: UI: assignees moved to right of cards with task-colored outlines; day header right-click annotations added; per-card right-click to remove due date. API: added POST /api/remove_due_date; documented annotations endpoints; fixed move endpoint name to /api/move_item.
- 2025-10-29 11:07: Backend now serves built frontend at root paths. Added mounts for /assets and explicit routes for /styles.css and /favicon.png so Vite build works when running `python -m whiteboard --dev`. Updated docs accordingly.

- 2025-10-29 15:11: Bugfix: Normalized `EntityType` keys to `Shot`/`Asset` (were `Shots`/`Assets`), fixing undefined mode on load and ensuring only the correct tab is active on startup.
- 2025-10-29 15:35: UI polish & filters: brighter current-day highlight; day headers show short weekday + day number (e.g., "Thu, 25"); added top-of-board filter combobox (sequences for Shots, asset types for Assets); per-card right-click context menu to remove due date retained. No API changes.
- 2025-10-29 15:55: No Due Date filter moved into the No Due Date board header (left side) and now only filters Shot items in that board. Weekday boards unaffected. No backend changes.
- 2025-10-29 16:20: UI: Replaced item card confirm dialog with a right-click context menu containing an “Unschedule” action. No API changes. Updated README TODOs.
- 2025-10-29 16:29: UI: Added context menu on assignee avatars with an “Unassign” action (replaces window.prompt). Layout: No Due Date, On Hold, and Omitted boards now display fixed-width cards in a left-to-right, top-to-bottom wrap. Backend: fixed /api/unassign to use entity_id instead of shot_id. Docs updated.
- 2025-10-29 16:54: UI: Day headers now use a right-click context menu for annotations with actions: Add annotation, Remove annotation, and Set Color (submenu with 5 colors). Removed confirmation dialogs for annotations. No API changes.
- 2025-10-29 17:02: Backend: Implemented Pattern C for ShotGrid helpers: `whiteboard.sg_helpers` is now a package that selects real vs mocked implementation via `WHITEBOARD_SG_MODE` env var (values: `real` [default], `mock`, `test`). `app.py` now imports from `whiteboard.sg_helpers`. Updated README TODO accordingly.
- 2025-10-29 17:58: Mock data: Expanded mocked assets dataset with ~20 assets across types (Character, Prop, Vehicle, Environment, Set, Weapon, Creature, FX) and auto-generated basic tasks per asset. No API surface changes.
- 2025-10-29 17:58: Bugfix: Unscheduling an Asset now moves it to the Assets No Due Date board. Frontend aggregates snapshot.assets_no_due_date in Asset mode; backend already exposed this field. No API changes.
- 2025-10-29 17:58 (later): UI parity fix for Assets: asset cards now use the same compact layout and avatar sizing as shots; fixed a className bug preventing `.card-asset` styles from applying. No backend changes.
- 2025-10-29 17:58 (later+): UI: No Due Date board header title is left-aligned; filter combobox remains at the left side of the header. No API changes.
- 2025-10-29 18:24: UI: No Due Date shots now lay out row-first (left-to-right with wrapping) instead of column-first. Weekday boards unchanged. No API changes.
- 2025-10-29 18:24 (later): UI: Added asset type filter combobox to the Assets tab for weekday boards. Selection is persisted in localStorage. No backend changes.
- 2025-10-29 19:03: Bugfix: Asset tab weekday alignment fixed. Backend now uses the same baseline Monday for shots and assets when mapping due dates to week/day, preventing a one-day shift in Assets. No API changes.
- 2025-10-29 19:15: UI: Moved the Asset type filter into the No Due Date board header (left side). The filter now only affects items in the No Due Date board; weekday boards are unaffected. Removed the Assets filter from the weekday sections. No backend changes.
- 2025-10-29 19:12: UI: All entity cards (shots and assets) now have a fixed width and height across all boards for visual consistency. Implemented via CSS variables --card-w and --card-h; removed inline width overrides. No API changes.
- 2025-10-30: Docker: Migrated to a multi-stage Dockerfile. Stage 1 builds the React frontend with Vite (Node 20 alpine) and emits assets into `backend/whiteboard/static`; Stage 2 installs Python deps with Poetry and copies the built static into `/service/whiteboard/static`. Run with `python -m whiteboard`. No API changes.


- 2025-10-30 (later): Docker: Kept single-stage Python image and minimally added Node.js and npm steps (`npm ci` + `npm run build`) to bake the React frontend into `backend/whiteboard/static` during image build. Reverts the earlier multi-stage change. No API changes.
