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

### Installation

First, [install uv](https://docs.astral.sh/uv/getting-started/installation/).

Then, clone this repository and run:

```bash
uv sync
```

This will create a virtual environment and install all dependencies.

### Usage

#### Build the site

```bash
uv run site build
```

#### Create a new post

```bash
uv run site new
```

This will prompt you for post metadata (title, date, tags, etc.) and create a new markdown file in `content/blog/`.

#### Run a local preview server

```bash
uv run site server
```

This starts an HTTP server on `localhost:8000` serving the output directory.

## Built with

- [jinja](https://jinja.palletsprojects.com/)
- [markdown-it-py](https://github.com/executablebooks/markdown-it-py)
- [click](https://click.palletsprojects.com/)
- [arrow](https://arrow.readthedocs.io/)
- [feedgen](https://github.com/danboo/python-feedgen)

