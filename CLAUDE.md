# sitebuilder

A minimal static site generator. Single source file: `src/sitebuilder/cli.py`.

## Commands

```bash
uv run --extra dev pytest tests/   # run tests
uv run site build                  # build site
uv run site server                 # preview at localhost:8000
```

## Key facts

- `pyproject.toml` is the single source of truth for the version
- `site.toml` in the project root configures title, url, author, subtitle, templates_dir, static_dir
- `build_static()` always copies vendored assets from `src/sitebuilder/templates/static/` first, then overlays the user's `static/` dir
- `get_jinja_env(config)` uses `ChoiceLoader` when `templates_dir` is set — user templates win, package templates are fallback
- `load_config()` returns `SiteConfig()` defaults when no `site.toml` exists (fully backward compatible)
- `build_feeds()` requires a non-empty subtitle; falls back to `config.title` if subtitle is blank

## Structure

```
src/sitebuilder/
    cli.py              # everything: SiteConfig, load_config, build_*, CLI commands
    __init__.py         # exports cli; reads __version__ from importlib.metadata
    templates/
        static/js/timezone.js   # vendored JS, always copied to build output
        *.html                  # default Jinja2 templates
tests/
    test_cli.py         # unit + integration tests; use tmp_path / CliRunner
```
