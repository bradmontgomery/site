# 🌐 site

[![Tests](https://github.com/bradmontgomery/site/actions/workflows/test.yml/badge.svg)](https://github.com/bradmontgomery/site/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/bradmontgomery/site/graph/badge.svg)](https://codecov.io/gh/bradmontgomery/site)
[![Version](https://img.shields.io/github/v/tag/bradmontgomery/site?label=version&sort=semver)](https://github.com/bradmontgomery/site/tags)

_my very own little static site generator_.

Extracted from [bradmontgomery.github.io](https://github.com/bradmontgomery/bradmontgomery.github.io)

## Goals

Why did I do this?

> mostly because I'm lazy and got tired of trying to learn the other sysems (hugo)

I also had some very clear goals:

- Ability to write content in markdown (with support for [CommonMark](https://commonmark.org/)
- I just wanted simple, easy-to-learn template engine (Hello Jinja)
- Ability to keep the same URLs that I had in django-blargg (good urls don't change)
- A command-line tool to build content (this is it!)
- Ability to just publish on github pages

## Content

Directory structure is broken into

```
content/
    blog/
        <title-slug>/index.md
    page/
        <title>.md
```

The index page should be a listing of _recent_ posts.

## Setup

This is a modern Python project using [uv](https://docs.astral.sh/uv/) for dependency management.

### Quick Start (with uvx)

If you have [uv](https://docs.astral.sh/uv/getting-started/installation/) installed, you can run the commands directly from this repository without cloning:

```bash
# Initialize a new site
uvx --from git+https://github.com/bradmontgomery/site site init

# Build the site
uvx --from git+https://github.com/bradmontgomery/site site build

# Create a new post (interactive — prompts for date, title, tags, description, draft)
uvx --from git+https://github.com/bradmontgomery/site site new

# Or pass everything as flags to skip the prompts
uvx --from git+https://github.com/bradmontgomery/site site new \
  --title "My Post" --tags "python,web" --description "A quick note." --no-draft

# Run local preview server
uvx --from git+https://github.com/bradmontgomery/site site server
```

### Local Development

Clone this repository and install dependencies:

```bash
git clone https://github.com/bradmontgomery/site
cd site
uv sync
```

Then use the commands with `uv run`:

```bash
uv run site init   # Initialize site structure
uv run site build  # Build the site
uv run site new    # Create a new post
uv run site server # Run preview server
```

### Commands

- **`site init`** — Initialize a new site structure (creates content/, templates/, and output/ directories)
- **`site build`** — Build the static site from content/
- **`site new`** — Create a new blog post. Pass `--date`, `--title`, `--tags`, `--description`, `--draft`/`--no-draft` for non-interactive use; any option you omit falls back to a prompt.
- **`site server`** — Run a local preview server on localhost:8000

## Configuration

Create a `site.toml` file in your project root (where you run `site build`) to configure your site:

```toml
[site]
title = "My Site"
url = "https://example.com"
author = "Your Name"
subtitle = "a description"

[build]
templates_dir = "templates"  # optional: directory of custom Jinja2 templates
static_dir = "static"        # optional: directory of CSS/JS/assets (default: "static")
```

Both sections are optional — any missing key falls back to a safe default. If `site.toml` doesn't exist at all, the build still works with defaults.

### Custom Templates

Set `templates_dir` to a directory containing your own Jinja2 templates. Templates found there take priority over the built-in ones; any template not present in your directory falls back to the package default. Available template names: `base.html`, `page.html`, `blog.html`, `index.html`, `tags.html`, `_sparkline.html`, `macros/dates.html`, `content.md`.

#### Template Inheritance

Every shipped page template extends `base.html`, which holds the one HTML
skeleton and exposes these blocks:

| Block                 | Contains                                              |
|-----------------------|-------------------------------------------------------|
| `title`               | The `<title>` text (defaults to `{{ title }}`)         |
| `head`                | Empty — your stylesheets and meta tags go here         |
| `header`              | Wraps `page_header`                                    |
| `content`             | Wraps `page_content`                                   |
| `footer`              | Empty                                                  |
| `scripts`             | The `timezone.js` `<script>` tag                       |

`header` and `content` are deliberately thin wrappers. The shipped templates
fill the inner `page_header` and `page_content` blocks instead, which leaves the
outer pair free for a [tag theme](#tag-themes) to replace wholesale.

### Static Assets

Place your CSS, JavaScript, and other static files in `static_dir` (default: `static/`). During a build they are merged into `{output}/static/`, on top of the vendored package assets (e.g. `timezone.js`). Your files win on any name conflict.

```
static/
    css/
        main.css
    js/
        app.js
```

## Features

### Client-Side Timezone Conversion

Blog post dates are stored and transmitted in UTC. When a page loads, a small
JavaScript module (`timezone.js`) converts `<time>` elements to the reader's
local timezone using the browser's `Intl.DateTimeFormat` API.

Use the Jinja macro for consistent markup:

```jinja2
{% import 'macros/dates.html' as dates %}

{{ dates.local_date(post.date, post.date_iso) }}
{{ dates.local_date(post.date, post.date_iso, format='long') }}
{{ dates.local_date(post.date, post.date_iso, format='date-only') }}
```

If JavaScript is disabled, readers see the UTC fallback text rendered by the
server. RSS/Atom feeds are unaffected and continue to use UTC.

### Publishing Cadence Sparkline

A small inline-SVG sparkline shows blog post counts per week over the last 90
days (13 weekly buckets). Bar height encodes the number of posts published in
that 7-day window; weeks with zero posts render no bar. The graphic is
non-interactive — purely a visual indicator of how often you publish.

The default `index.html` includes it inside the page `<header>`, just below the
subtitle. Users with their own templates can opt in by adding:

```jinja2
{% include "_sparkline.html" %}
```

If there are no posts within the last 90 days the partial renders nothing, so
it's safe to include unconditionally.

#### Styling

The partial ships with minimal default styling and exposes two CSS hooks so you
can fully restyle it from your own stylesheet:

| Selector          | Purpose                                      |
|-------------------|----------------------------------------------|
| `.sparkline`      | The `<svg>` container — `width`, `height`, `color` |
| `.sparkline-bar`  | Each `<rect>` bar — `fill`, `opacity`        |

Example overrides:

```css
.sparkline { width: 200px; height: 28px; color: #2a7ae2; }
.sparkline-bar { fill: currentColor; opacity: 1; }
```

For deeper customization, drop your own `_sparkline.html` into your
`templates_dir`; it wins over the package template via Jinja's `ChoiceLoader`.

### Tag Themes

Any tag archive page (`/blog/tags/<tag>/`) can get its own look. Drop a template
named `base_<tag>.html` into your `templates_dir` and it becomes the Jinja
**parent** for that tag's list page. The convention is opt-in, one tag at a time:
without a matching file the tag page renders from the default `base.html`.

> **Note:** the shipped templates now share a common `base.html` skeleton. Output is
> functionally the same, but not byte-identical to earlier versions — for example the
> tag index (`tags.html`) now loads `timezone.js`, and some whitespace and HTML
> comments changed.

The filename uses the *normalized* tag — the same `normalize_tag()` rule that builds
the URL: the tag is ASCII-folded (accents dropped, non-ASCII characters removed),
lowercased, stripped of non-word characters, has runs of spaces and dashes collapsed
to a single `-`, and has leading/trailing `-` and `_` removed. Underscores inside a
tag are kept.

| Tag in front matter | URL                      | Theme file                |
|---------------------|--------------------------|---------------------------|
| `food`              | `/blog/tags/food/`       | `base_food.html`          |
| `Home Cooking`      | `/blog/tags/home-cooking/` | `base_home-cooking.html` |
| `Café`              | `/blog/tags/cafe/`       | `base_cafe.html`          |

A tag made only of non-ASCII characters (e.g. `日本語`) normalizes to an empty string
and can't be themed. Filenames are matched exactly, so use the lowercase,
normalized form.

Your theme extends `base.html` and overrides the outer blocks. Anything you
leave out falls through to the shipped markup:

```jinja2
{# templates/base_food.html #}
{% extends "base.html" %}

{% block head %}
    <link rel="stylesheet" href="/static/css/food.css">
{% endblock %}

{% block header %}
    <header class="food-theme">
        <h1>🍜 {{ tag }}</h1>
        <p>{{ posts|length }} recipes</p>
    </header>
{% endblock %}
```

That replaces the page header and adds a stylesheet, while the post list itself
is still rendered by the shipped `index.html`. Override `content` too if you want
to replace the list markup as well.

`base.html` exposes two layers of blocks. The **outer** blocks (`title`, `head`,
`header`, `content`, `footer`, `scripts`) are for themes; the **inner** blocks
(`page_header`, `page_content`) are what the shipped page templates fill. Because a
theme overrides the outer layer, it always wins. Overriding `header` replaces
everything inside it, including the subtitle and sparkline; call `{{ super() }}`
to keep the default and add to it:

```jinja2
{% block header %}
    <div class="food-banner">🍜</div>
    {{ super() }}
{% endblock %}
```

Overriding `page_header`/`page_content` in a theme will *not* work, since
`index.html` fills those itself.

Tag list pages receive:

| Variable   | Value                                                   |
|------------|---------------------------------------------------------|
| `tag`      | The normalized tag, e.g. `food`                          |
| `posts`    | That tag's posts, newest first                           |
| `title`    | Your site title from `site.toml`                         |
| `subtitle` | `"Tagged <tag>"`                                         |

Only the per-tag archive pages are themable. The tag index at `/blog/tags/`
always renders from `tags.html`.

> **Using your own `index.html`?** A custom `index.html` in your `templates_dir`
> wins over the package one, so it keeps working — but tag themes won't reach it
> until it opts in. To convert it:
>
> 1. Make the first line `{% extends base_template|default("base.html", true) %}`.
> 2. **Delete its own `<!DOCTYPE>`, `<html>`, `<head>` and `<body>` tags** —
>    `base.html` supplies the skeleton now, and leaving them in produces a
>    doubled document.
> 3. Move what's left into `{% block page_header %}` and `{% block page_content %}`,
>    putting any stylesheet or meta tags into `{% block head %}`.

#### Build warnings

Existing sites keep building unchanged. If your `templates_dir` contains something that
interacts with tag themes, the build logs a warning (it never fails the build):

| Warning mentions | Meaning |
|------------------|---------|
| `base.html shadows the shipped base.html and defines no 'page_content' block` | Your own `base.html` wins over the shipped one, so shipped templates you haven't overridden render without content. Add `page_header`/`page_content` blocks, or rename the file. |
| `... exists for tag 'x', but your index.html doesn't extend it` | You have both `base_x.html` and a custom full-document `index.html`; the theme isn't applied until `index.html` is converted (steps above). |
| `base_X.html will never be used as a tag theme` | The filename isn't in normalized form (case, accents, spaces); the message suggests the right name. |
| `base_x.html is used as the theme for tag 'x' but doesn't extend base.html` | A `base_<word>.html` file you wrote for another purpose matches a tag name and is being used as its parent. Rename it or make it extend `base.html`. |

## Built with

- [jinja](https://jinja.palletsprojects.com/)
- [markdown-it-py](https://github.com/executablebooks/markdown-it-py)
- [click](https://click.palletsprojects.com/)
- [arrow](https://arrow.readthedocs.io/)
- [feedgen](https://github.com/danboo/python-feedgen)

