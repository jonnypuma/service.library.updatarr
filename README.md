# Library Updatarr

Kodi add-on that fills in **missing metadata and artwork for items already in your video library**. It does not scan source folders for new files or wipe the database — it only updates existing library entries that are incomplete.

**Provider:** Skippy-McSkipface  
**Add-on ID:** `service.library.updatarr`  
**Version:** 2.3.0  
**Requires:** Kodi 19+ (tested on Kodi v22 Piers)

## What it does

For each library item in scope, Library Updatarr:

1. **Scans** the Kodi database for missing posters, fanart, thumbs, plot, and other configured fields.
2. **Applies local fixes** — reads sidecar `poster.jpg`, `fanart.jpg`, `*.nfo`, etc. next to the media file and pushes them into the library via JSON-RPC.
3. **Re-checks** whether anything is still missing.
4. **Refreshes via scrapers** — calls `VideoLibrary.RefreshMovie`, `RefreshTVShow`, or `RefreshEpisode` using your installed metadata scrapers.

## How to run

| Entry point | Description |
|---|---|
| **Add-on settings → Run Now** | Full update for the configured scope |
| **Add-on settings → Dry Run** | Scan only; shows counts and missing-field breakdown. If items need updates, offers **Run the update now?** without scanning again |
| **Context menu** | *Fix Missing Metadata/Artwork* or *Remove from library* (scoped; see below) |
| **Background service** | Optional scheduled runs when enabled in settings |

### Context menu scope

| Selected item | What gets updated |
|---|---|
| **Movie** | That movie only |
| **TV show** | Show + all seasons + all episodes (when *Include seasons and episodes…* is enabled; show-only when off) |
| **Season** | That season + episodes in that season only |
| **Episode** | That episode only |

**Remove from library** (separate context action) works for **video library** items only: movie, TV show, season, episode, and music video. It removes the entry from Kodi’s database without deleting files on disk. Music artists, albums, and songs are not supported — Kodi provides no equivalent remove API for the audio library.

Local files used (`.jpg`, `.png`, and `.jpeg` supported for artwork):

- **Movie:** `<movie>.nfo` or `movie.nfo`, `<movie>-poster.<ext>` / `poster.<ext>`, `<movie>-fanart.<ext>` / `fanart.<ext>`, `<movie>-thumb.<ext>` / `thumb.<ext>`
- **Show:** `tvshow.nfo`, `poster.<ext>`, etc. in the show folder — if Kodi's library path points at the TV root, Updatarr resolves the folder from episode paths or a subdir containing `tvshow.nfo`
- **Season:** walks show subfolders for `season.nfo` / `seasonNN.nfo` (matched by `<seasonnumber>`), artwork beside that NFO, plus `seasonNN-poster.<ext>` at show root and NFO `<thumb>` URLs (note: Kodi v22 does not expose season `plot` via JSON-RPC, so local season plots cannot be pushed directly)
- **Episode:** sidecar `*.nfo`, `<episode>-thumb.<ext>`, and `<episode>.tbn` next to the video file

### Dry run follow-up

After a dry run finds items needing work, a single dialog shows the summary and asks whether to start the real update. If you confirm:

- A **resumable job** is created from the dry-run candidate list (no second library scan).
- If a **previous partial job** exists, you can Resume, Start Fresh, or Cancel first.

Dry runs alone do not write `update_job.json`.

### Resumable jobs

Long runs save progress to:

`special://profile/addon_data/service.library.updatarr/update_job.json`

If Kodi closes or you cancel mid-run, the next **Run Now** (or dry-run follow-up) offers to resume. The scheduled service auto-resumes an incomplete job on its next tick.

## Settings overview

### Scope

Choose which item types to process and which fields count as “missing” (poster, fanart, thumb, plot, title, rating, cast).

### Local sources

- **Apply local artwork files** — import sidecar images into the library.
- **Apply local NFO metadata** — parse local NFO XML for missing text fields.

### Online scrapers

- **Enable scraper refresh pass** — call Kodi’s refresh APIs for items still incomplete after local fixes.
- **Ignore local NFO when refreshing** — passed through to `Refresh*` as `ignorenfo`.
- **Refresh episodes when refreshing a TV show** — `refreshepisodes` on show refresh.
- **Delay between scraper refreshes** — pause between items (default **3000 ms**); increase if you see MySQL deadlock errors during large batch runs.
- **Library query batch size** — paginated JSON-RPC page size when scanning.

### Scheduling

- **Enable scheduled background runs** — start the `xbmc.service` loop on login.
- **Schedule interval (hours)** — minimum time between completed scheduled runs.
- **Only run when no video is playing** — skip while playback is active.
- **Show notification after scheduled run** — summary toast when finished.
- **Verbose local source logging** — detailed Kodi log lines for NFO/artwork discovery (paths searched, found, applied, skipped with file size/mtime).

## Requirements

- A populated Kodi video library (movies and/or TV).
- Installed metadata scrapers if you use the online refresh pass.
- Local artwork/NFO files are optional but recommended for fastest fixes.

## Logging

Enable **debug logging** for JSON-RPC request/response detail. Enable **verbose local source logging** for NFO and artwork path tracing (searched paths, which file was used, skip reasons). Log prefix:

`[service.library.updatarr]`

Verbose lines are prefixed with `[verbose]`.

## License

GPL-2.0-or-later
