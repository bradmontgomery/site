# 🌐 site

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

# Create a new post
uvx --from git+https://github.com/bradmontgomery/site site new

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
- **`site new`** — Create a new blog post (interactive)
- **`site server`** — Run a local preview server on localhost:8000

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

## Built with

- [jinja](https://jinja.palletsprojects.com/)
- [markdown-it-py](https://github.com/executablebooks/markdown-it-py)
- [click](https://click.palletsprojects.com/)
- [arrow](https://arrow.readthedocs.io/)
- [feedgen](https://github.com/danboo/python-feedgen)

