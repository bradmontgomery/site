# Code Review Findings

Remaining issues from code review of sitebuilder project.

## Fixed Issues

- [x] **CRITICAL**: Incorrect `str.strip()` usage when checking blog paths (cli.py:424)
- [x] **CRITICAL**: Missing `date` key crashes build - added validation
- [x] **CRITICAL**: Date parsing exception silently continues with unparsed date
- [x] **CRITICAL**: Missing `title`/`url` keys crash feed generation - added validation
- [x] **HIGH**: Path traversal vulnerability in `get_output_paths`
- [x] **HIGH**: Unused `--templates` option in `build()` - removed dead option
- [x] **HIGH**: Deprecated `pubdate()` API - changed to `pubDate()`
- [x] **MEDIUM**: Duplicate Jinja environment creation - extracted to `get_jinja_env()`
- [x] **MEDIUM**: Variable shadowing in `render()` - renamed params to `dest_dir`, `template_name`
- [x] **MEDIUM**: Inconsistent `os.makedirs` vs `Path.mkdir` - standardized on pathlib
- [x] **MEDIUM**: Removed unused `os` import
- [x] **MEDIUM**: `ruff` in production dependencies - moved to dev dependencies
- [x] **MEDIUM**: Server binds to all interfaces - changed default to `127.0.0.1`
- [x] **MEDIUM**: Inconsistent URL casing in feed generation - standardized to lowercase
- [x] **LOW**: Magic strings for hardcoded author/site info - extracted to constants
- [x] **LOW**: `to_slug()` duplicates `normalize_tag()` - now uses `normalize_tag()`
- [x] **LOW**: Removed unused `string` import (after `to_slug` refactor)

---

## Features Implemented

### Client-Side Timezone Conversion (NEW)
**Status**: Implemented ✓

Feature allows blog dates to be displayed in user's local timezone on the client side while all dates remain stored/transmitted in UTC.

**Implementation**:
- Backend: Added `date_iso` field to all post contexts containing ISO 8601 UTC timestamp
- Frontend: Created `timezone.js` module for automatic client-side conversion
- Templates: Added date formatting macros for consistency

**Files**:
- `src/sitebuilder/cli.py`: Added `date_iso` generation in `get_template_context()`
- `src/sitebuilder/templates/static/js/timezone.js`: Client-side conversion logic (~2.2 KB)
- `src/sitebuilder/templates/macros/dates.html`: Reusable date formatting macros
- `src/sitebuilder/templates/example-blog.html`: Example template usage
- `TIMEZONE_CONVERSION.md`: Complete feature documentation

**Key Features**:
- Automatic browser timezone detection
- Locale-aware date formatting via `Intl.DateTimeFormat`
- No external dependencies (pure JavaScript)
- Graceful fallback if JS disabled
- Accessible: uses semantic `<time>` elements with `datetime` attributes
- RSS/Atom feeds unaffected (continue using UTC)

See `TIMEZONE_CONVERSION.md` for usage guide.

---

## Not Actually Bugs (Investigated and Cleared)

- ~~Incorrect `fe.author()` call syntax~~ - keyword arguments ARE supported by feedgen
- ~~Timezone missing on pubdate~~ - Arrow's `.to('utc').datetime` already produces timezone-aware datetimes

---

## Remaining Issues

### Low Severity (Won't Fix / Acceptable)

#### Inconsistent logging vs console.print
**File:** Throughout

The code uses both `logger.info()` and `console.print()` for user feedback.

**Status:** Acceptable - `logger` is used for build operations, `console.print` for interactive CLI feedback (init command). This is a reasonable pattern.

#### Package name mismatch
**File:** `pyproject.toml:6, 26`

Package is named `site` but module is `sitebuilder`. While functional, this can be confusing.

**Status:** Won't fix - changing would break existing installations.

#### Confusing module/function naming in `__main__.py`
**File:** `src/sitebuilder/__main__.py`

`cli` is both a module name and a function name, which can cause confusion.

**Status:** Acceptable - this is a common Python CLI pattern.
