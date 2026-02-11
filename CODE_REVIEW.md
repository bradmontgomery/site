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

---

## Not Actually Bugs (Investigated and Cleared)

- ~~Incorrect `fe.author()` call syntax~~ - keyword arguments ARE supported by feedgen
- ~~Timezone missing on pubdate~~ - Arrow's `.to('utc').datetime` already produces timezone-aware datetimes

---

## Remaining Issues

### Medium Severity

#### Variable shadowing in `render()`
**File:** `src/sitebuilder/cli.py:148-158`

Parameters `template` and `path` are reassigned within the function.

```python
def render(env, path, template, context):
    filename = "index.html" if template.endswith("html") else "index.md"
    template = env.get_template(template)  # Shadows parameter
    path = Path(path)  # Shadows parameter
    path = path / Path(filename)  # Reassigned again
```

**Recommendation:** Use distinct variable names like `template_name`, `dest_dir`, `dest_file`.

#### Duplicate Jinja environment creation
**File:** `src/sitebuilder/cli.py:383, 424`

Same environment setup code repeated in `new()` and `build()`.

**Recommendation:** Extract to a helper function:
```python
def get_jinja_env():
    return Environment(
        loader=PackageLoader("sitebuilder"),
        autoescape=select_autoescape()
    )
```

#### Inconsistent Path vs os usage
**Files:** Multiple locations

The code mixes `os.makedirs` (line 243, 247) and `Path.mkdir` (line 135).

**Recommendation:** Standardize on `pathlib.Path` throughout.

#### No error handling for file operations
**File:** `src/sitebuilder/cli.py:104, 156-157, 436-437`

File operations lack try/except blocks.

```python
content = Path(filename).read_text()  # No error handling
with open(path, "w") as f:  # No error handling
```

#### Server binds to all interfaces by default
**File:** `src/sitebuilder/cli.py:366`

Default `--addr=""` exposes the server to the network.

```python
@click.option("--addr", default="", help="Address to listen on")
# Should default to "127.0.0.1"
```

#### Missing type hints
**File:** Throughout `src/sitebuilder/cli.py`

Most functions lack type annotations.

#### Inconsistent URL casing
**File:** `src/sitebuilder/cli.py:252, 255`

```python
fg.id("https://BradMontgomery.net")  # Capital letters
fg.link(href="https://bradmontgomery.net", rel="alternate")  # Lowercase
```

#### `ruff` in production dependencies
**File:** `pyproject.toml:22`

The linter should be a dev dependency, not a runtime dependency.

---

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
