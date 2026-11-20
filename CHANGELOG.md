# Changelog

All notable changes to Library Updatarr are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0] - 2026-11-20

### Added

- **Cross-invocation run lock** — prevents overlapping manual, context-menu, and scheduled runs via `lib/run_lock.py`.
- **Episode & expanded local artwork** — supports `.png` and `.jpeg` alongside `.jpg`, episode `<base>-thumb.<ext>` / `<base>.tbn`, movie `<base>-poster.<ext>` / `-fanart` / `-thumb`, `movie.nfo` fallback, and legacy `<rating>…</rating>` NFO tags.
- **Unit test suite** — added `pytest` suite under `tests/` with Kodi module stubs.

### Changed

- **Batched artwork updates** — applies all resolved art types for an item in a single `Set*Details` JSON-RPC call.
- **Season scanning** — builds season items directly from `VideoLibrary.GetSeasons` instead of per-season `GetSeasonDetails` calls; removed unused `fetch_season()`.
- **Atomic, minimal job checkpoints** — `update_job.json` stores minimal item identifiers and writes via `.tmp` + rename.
- **Abort-aware service throttling** — background runs use `monitor.waitForAbort()` and clear folder/NFO caches at run start.
- **Localization** — moved remaining dialog/status strings into `strings.po` (`32061`–`32068`).

### Fixed

- **Resume Job dialog buttons** — fixed inverted `Dialog.yesnocustom` button mapping (`Resume Job` / `Start Fresh` / `Cancel`).
- **Season metadata & duplicate refreshes** — excluded non-Kodi-v22 season fields (`plot`, `rating`, `cast`) from missing-field checks and deduplicated `RefreshTVShow` calls per show within a run.
- **Context menu scoping & job safety** — restricted `context.py` visibility in `addon.xml` to `movie`/`tvshow`/`season`/`episode`, prevented unsupported types from falling through to a full-library scan, bypassed global type toggles, and preserved paused `update_job.json` jobs.
- **Settings & missing detection** — preserved `delay_ms = 0`, treated `rating <= 0` as missing, skipped `apply_local_nfo()` when no requested metadata fields are missing, checked `refresh_item()` JSON-RPC errors, and removed duplicate scheduled-run notifications.

## [2.2.2] - 2026-06-16

### Changed

- **Remove from library** — context menu limited to video library types again (movie, TV show, season, episode, music video). Music artists/albums/songs are not supported: Kodi has no JSON-RPC API to remove them from the database while keeping files on disk.

## [2.2.1] - 2026-06-16

### Added

- **Suspect `tvshow.path` warning** — logs when Kodi’s stored show path looks like a TV source root (e.g. `Media/TV`) while `tvshow.nfo` lives in a subfolder; warns before scraper refresh that local NFO/season plot may not apply via JSON-RPC.
- **Music context menu** — “Remove from library” now appears for artist/album/song/musicvideo. Artists, albums, and songs show a Kodi limitation notice (no DB-only remove API). Music videos use `VideoLibrary.RemoveMusicVideo`.

### Fixed

- **Remove menu visibility** — was intentionally limited to video types in `addon.xml`; music types were excluded by the `visible` condition, not a runtime bug.

## [2.2.0] - 2026-06-16

### Fixed

- **Kodi v22 artwork API** — `VideoLibrary.SetArt` no longer exists (`Method not found`). Artwork is now set via `SetMovieDetails` / `SetTVShowDetails` / `SetSeasonDetails` / `SetEpisodeDetails` with an `art` object.
- **Artwork loop** — try local files and NFO URLs once per art type instead of once per candidate path (fewer duplicate JSON-RPC calls and log lines).
- **Show thumb from NFO** — `characterart` aspect can satisfy missing `thumb`.

## [2.1.9] - 2026-06-16

### Fixed

- **Season/show artwork from NFO URLs** — TMM and similar tools store season art as `<thumb aspect="poster">`; Kodi expects `thumb` and `fanart`. Added aspect fallbacks (e.g. poster → thumb, landscape/banner → fanart) including per-season `<thumb season="N">` entries from `tvshow.nfo`.
- **Local artwork fallbacks** — use `poster.jpg` when `thumb.jpg` is missing (show/movie); use show-level `fanart.jpg` and season-folder `poster.jpg` for season fanart/thumb.
- **Verbose artwork logging** — lists which NFO URL aspects were found when no match applies.

## [2.1.8] - 2026-06-16

### Fixed

- **`xbmcvfs.listdir` tuple order** — Kodi returns `(dirs, files)`; treating the first list as files marked every show-root image/NFO as a directory and recursed into them (`NFS3ERR_NOTDIR` spam). Season walks now only descend into real subfolders (e.g. `Season 1/`).
- **`vfs_isdir` listdir fallback** — Removed probing directories via `listdir` on ambiguous paths; avoids NFS errors when a path is a file.

## [2.1.7] - 2026-06-16

### Fixed

- **`xbmcvfs.listdir` tuple return** — Kodi returns `(dirs, files)` not a flat list; iterating it caused `'list' object has no attribute 'rstrip'` when walking season folders for NFO/artwork. New `vfs_listdir()` helper used in `local_fixer` and `show_folder`.

## [2.1.6] - 2026-06-16

### Fixed

- **GetSeasonDetails** — removed invalid `plot` property; Kodi v22 only allows season fields from `Video.Fields.Season`. Uses `seasonid` from `GetSeasons` response (required on v22; `tvshowid`+`season` no longer used).
- **SetTVShowDetails** — sanitize payload to Kodi-allowed fields: drop `year`/`tagline`, map `year`→`premiered`, map `imdb`→`imdbnumber`, send one `uniqueid` provider at a time (fixes “Too many parameters” / invalid `uniqueid` errors).
- **SetSeasonDetails** — only sends `title`/`art`/`userrating`; season `plot` from NFO is logged as non-writable (Kodi API limitation) and left for scraper refresh.

## [2.1.5] - 2026-06-16

### Fixed

- **`xbmcvfs.isdir`** — Kodi Python has no `isdir`; new `lib/vfs.py` uses `xbmcvfs.Stat` + `stat.S_ISDIR` (with `listdir` fallback) for directory checks in show-folder and season NFO walks.
- **GetSeasons invalid property** — removed `seasonid` from requested properties (not in Kodi v22 enum); still uses `seasonid` from the response when Kodi returns it, otherwise falls back to `tvshowid` + `season` for `GetSeasonDetails`.

## [2.1.4] - 2026-06-16

### Fixed

- **GetTVShowDetails crash** — removed `tagline` from requested properties; Kodi v22 JSON-RPC does not accept it in `Item.Fields.Base` (invalid params at index 2). Tagline is still parsed from `tvshow.nfo` and sent via `SetTVShowDetails` when other show fields are applied.

## [2.1.3] - 2026-06-16

### Changed

- **Show folder resolution order** — episode `file` paths (JSON-RPC) are now tried before title subfolder matching; title match remains a verified fallback only.
- **Episode parent walk** — walks up from each episode directory checking for `tvshow.nfo` and `season.nfo` at every level; when a season folder is found, checks its parent for `tvshow.nfo` instead of blind parent traversal.

## [2.1.2] - 2026-06-16

### Fixed

- **TV show folder resolution** — when Kodi's show `file` path is the library root (e.g. `Media/TV`), resolve the real show folder by title subfolder, walking up from episode paths, or scanning subdirs for `tvshow.nfo` (fixes Kaiju No. 8-style layouts).
- **Season fetch on Kodi v22** — `GetSeasonDetails` now uses `seasonid` from `GetSeasons` instead of failing with a missing-parameter error.

### Added

- **Tagline** — detected as missing (when Check plot is enabled), read from `tvshow.nfo`, applied via `SetTVShowDetails`.
- **TMM NFO format** — parses `<ratings>/<rating>` blocks, `<seasonplot number="N">`, and per-season `<thumb season="N">` URLs from `tvshow.nfo`.
- **Season plot/art fallback** — when no `season.nfo` exists, season plot can come from `<seasonplot>` in `tvshow.nfo`; season posters from `<thumb season="N">` entries.

## [2.1.1] - 2026-06-16

### Changed

- **Season NFO discovery** — walks the TV show folder (depth-limited) for any `season.nfo` or `seasonNN.nfo`, matches by `<seasonnumber>` in the XML (or `NN` from flat filenames), instead of hardcoded folder names like `Season 1` or `Season02`.
- **Season artwork** — looks for poster/fanart/banner files in the **same folder** as the matched `season.nfo`; still falls back to `seasonNN-poster.jpg` at show root and NFO `<thumb>` URLs.

## [2.1.0] - 2026-06-16

### Added

- **Verbose local source logging** — optional setting logs every NFO path searched (found/missing), fields applied or skipped, artwork candidates with file size/mtime, and why each art type was applied or skipped.
- **Season NFO thumb URLs** — remote `<thumb aspect="poster">` (and other aspects) in `season.nfo` are applied via `SetArt` when no local image file exists.

### Fixed

- **Season plot** — `GetSeasonDetails` now requests `plot`; context season scope uses the same detail fetch as other item types.
- **Season folder layouts** — NFO lookup includes `Season 1/season.nfo`, `Season 01/season.nfo`, and similar variants; artwork also checks poster/fanart/banner files inside those subfolders.
- **Flat NFO IDs** — `<tvdbid>`, `<tmdbid>`, `<imdbid>`, etc. in season/show NFO are mapped into `uniqueid` when applying metadata.

## [2.0.0] - 2026-06-16

### Added

- **Remove from library** context menu action — removes movie, TV show (with seasons/episodes), season, episode, or music video from the Kodi database only (`deletefile=false`); media files on disk are kept. Video library only; not available for music artists/albums/songs (no Kodi API).

### Changed

- **Default scraper delay** increased from 1000 ms to **3000 ms** to reduce MySQL deadlocks during rapid `RefreshEpisode` runs.
- Throttle delay also applies after successful local-only fixes (NFO/artwork) before moving to the next item.

## [1.0.4] - 2026-06-16

### Fixed

- **Context menu label** — reverted to `<label>32000</label>` (literal text change in 1.0.3 was unnecessary).

## [1.0.3] - 2026-06-16

### Fixed

- **TV show local fixes** — `name 'settings' is not defined` when processing show/season artwork and NFO (`_nfo_path_for_item` / `_artwork_candidates` now receive `settings`).
- **Context scoping** — TV show: show + seasons + episodes; season: that season + its episodes only; episode/movie: single item only.

### Added

- **Season support** — fetch seasons for TV show context and full-library runs; local `seasonNN.nfo`, `seasonNN/season.nfo`, and `seasonNN-*.jpg` artwork; `VideoLibrary.SetSeasonDetails` for season NFO.

## [1.0.2] - 2026-06-14

### Fixed

- **Context menu label** — use numeric string id `32000` in `addon.xml` (Kodi context items expect a language id, not `$ADDON[32000]`).
- **Episode/context refresh crash** — `DialogProgress.update()` on Kodi v22 accepts two arguments only; merged status into a single line.
- **Library scan detection** — replaced removed `VideoLibrary.GetProgress` JSON-RPC with `Library.IsScanningVideo` / `Library.IsScanning` infolabels.

## [1.0.1] - 2026-06-14

### Fixed

- **Context menu** showed a blank row — `strings.po` had empty `msgstr` values so `$ADDON[32000]` resolved to no text; all English strings now populated.
- **Scan cancel** hung the progress dialog — library scan now checks cancel between JSON-RPC batches and exits cleanly without a follow-up modal.
- **Language packs** — added `en_us` and `English` string catalogs for Windows Kodi locales.

## [1.0.0] - 2026-06-14

### Added

- **Initial release** — populate missing metadata and artwork for items already in the Kodi video library (no new-file library scan).
- **Pipeline:** scan → detect missing fields → apply local artwork/NFO → re-check → scraper refresh (`RefreshMovie` / `RefreshTVShow` / `RefreshEpisode`).
- **Scope settings** for movies, TV shows, and episodes; configurable missing-field checks (poster, fanart, thumb, plot, title, rating, cast).
- **Local sources** — sidecar artwork via `SetArt`; NFO XML parse into `Set*Details` for missing fields only.
- **Online scrapers** — refresh pass using installed Kodi scrapers; optional ignore-NFO; TV show episode refresh options.
- **Dry Run** — scan-only preview with missing-field breakdown; optional **Run the update now?** follow-up without re-scanning.
- **Resumable jobs** — `update_job.json` checkpointing; Resume / Start Fresh / Cancel when a partial run exists.
- **Scheduled service** — background runs on interval, idle guard, defer during library scan or playback.
- **Context menu** — fix missing data for the selected movie, show, season, or episode.
- **Programs launcher** — Run Now and Dry Run from add-on settings.
- **Kodi v22 (Piers) settings schema** and `xbmc.Monitor` service API.
