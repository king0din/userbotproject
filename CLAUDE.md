# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KingTG UserBot Service (v2.1.0) — a multi-user Telegram userbot hosting service. A central Telegram bot (Telethon) lets users connect their own Telegram accounts (phone login or session string), then activates plugins on their behalf. Code comments, docs, and commit messages are in **Turkish**.

## Commands

```bash
pip install -r requirements.txt   # install deps
python main.py                    # run the bot (requires a filled .env, see .env.example)
bash temizle.sh                   # dry-run cleanup of dead code / secret files
bash temizle.sh --uygula          # actually delete them
```

There are no automated tests and no linter configured. Verification is manual (run the bot against Telegram).

## Architecture

Startup flow: `main.py` loads `.env` → connects `database` → starts the bot client (`bot_session`) → registers handlers → `smart_session_manager` restores user sessions → `plugin_manager.preinstall_all_dependencies()`.

Key layers:

- **`config.py`** — all settings from env vars; also creates `data/`, `sessions/`, `plugins/`, `logs/` dirs and defines file paths.
- **`database/`** — unified interface (`from database import database as db`). Uses MongoDB (motor) when connected, falls back to local JSON files in `data/`; keeps both in sync. Never bypass this interface with direct file/Mongo access.
- **`userbot/smart_manager.py`** — the session manager (`smart_session_manager`). Hybrid model: "always-on" plugins keep a user's client connected permanently; others run "on-demand" with a 5-minute idle timeout. `userbot/manager.py` is emptied dead code — do not use or resurrect it; `userbot/__init__.py` aliases `userbot_manager = smart_session_manager` for old imports.
- **`userbot/plugins.py`** — `plugin_manager`: loads plugin files, tracks per-user handlers, auto-installs plugin pip dependencies. Each user gets a SEPARATE module instance per plugin (`plugin_<name>_<user_id>`), so module-level globals are per-user. Uses `_activation_lock` because legacy-style plugins read a global `_client` — concurrent activations without the lock bind handlers to the wrong account.
- **`userbot/orphan_sweeper.py`** — startup cleanup of data left by deleted users; its hardcoded data paths must stay in sync with plugins' own storage paths.
- **`userbot_compat/`** — compatibility shim (CMD_HELP, CmdHelp, events, zalgo lists…) so legacy SedUserBot/AsenaUserBot-style plugins run unmodified.
- **`handlers/`** — bot UI. `handlers/user/` (login flows, menus, plugin activation) and `handlers/admin/` (users, settings, system, plugin admin). Registered via `register_user_handlers` / `register_admin_handlers`. `handlers/admin/_state.py` holds shared "send an ID" input state for admin flows.
- **`utils/`** — `logger.py` (use `get_logger(__name__)`, not `print`), `bot_api.py` (raw Bot API HTTP calls for colored buttons/premium emoji), `premium.py` (plugin access tiers: genel/ozel/premium paid via Telegram Stars; atomic JSON writes in `data/`).

## Plugins

Plugins are single `.py` files in `plugins/`, required header comments: `# description:`, `# author:`, `# version:`. Two styles exist:

1. **Modern (preferred):** `def register(client):` attaching Telethon handlers, optional `def unregister()`. Template: `plugins/_sablon.py`; guide: `docs/PLUGIN_REHBERI.md`.
2. **Legacy:** old userbot-style plugins using `from userbot.events import register` (compat shim). Supported but don't write new ones this way.

**Cross-user isolation rule:** plugins run one module instance per user and use `event.client`, so accounts don't cross — BUT any plugin that writes to a shared filesystem path (temp download dir, temp file) must namespace it by the operator's own user id (e.g. `os.path.join(TEMP_DOWNLOAD_DIRECTORY, f"yt_music_{owner_id}")`). A shared temp dir lets two users' simultaneous commands clobber each other (wrong file sent to wrong person). If a plugin stores per-user data, update `orphan_sweeper.py` accordingly.

## Critical Cautions

- **Live secrets in the working tree:** `.env`, `bot_session.session`, and `data/users.json` (contains real users' plaintext session strings — full account access). Never commit, copy, log, or share these. Sessions are stored **unencrypted** despite older README claims.
- **The admin "Güncelle" (update) button runs `git pull`/reset against origin/main and restarts.** It will discard any UNCOMMITTED local changes in the working tree. Commit or back up local work before anyone presses it.
- Known debt (see `docs/ANALIZ_VE_YOL_HARITASI.md`): very large handler functions, widespread bare `except:` clauses that swallow errors, no tests. Prefer specific exceptions and `utils.logger` in any code you touch.
