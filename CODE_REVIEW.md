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

---

## Not Actually Bugs (Investigated and Cleared)

- ~~Incorrect `fe.author()` call syntax~~ - keyword arguments ARE supported by feedgen
- ~~Timezone missing on pubdate~~ - Arrow's `.to('utc').datetime` already produces timezone-aware datetimes

---

## Remaining Issues

### Low Severity

#### Magic strings for hardcoded author/site info
**File:** `src/sitebuilder/cli.py:165-166, 252-256`

Site title, URL, and author are hardcoded in multiple places.

**Recommendation:** Extract to a config dict or constants.

#### Unused `os` import
**File:** `src/sitebuilder/cli.py:11`

Only used for `os.makedirs` which could be replaced with `Path.mkdir`.

#### `to_slug()` duplicates `normalize_tag()` functionality
**File:** `src/sitebuilder/cli.py:43-51`

The `to_slug()` function could reuse `normalize_tag()` which handles more edge cases.

#### Inconsistent logging vs console.print
**File:** Throughout

The code uses both `logger.info()` and `console.print()` for user feedback.

#### Package name mismatch
**File:** `pyproject.toml:6, 26`

Package is named `site` but module is `sitebuilder`. While functional, this can be confusing.

#### Confusing module/function naming in `__main__.py`
**File:** `src/sitebuilder/__main__.py`

`cli` is both a module name and a function name, which can cause confusion.
