"""
A simple static site generator.

Markdown content goes in content/blog/ or content/pages/
Templates are powered by Jinja2
Run `site build` to build the site.
"""
import http.server
import logging
import os
import re
import shutil
import string
import unicodedata
from collections import defaultdict
from glob import glob
from itertools import chain
from pathlib import Path
from time import time

import arrow
import click
from feedgen.feed import FeedGenerator
from jinja2 import Environment, PackageLoader, select_autoescape
from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
import yaml

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_time=False)]
)
logger = logging.getLogger(__name__)


def to_slug(value):
    """Convert a string to a URL-safe slug."""
    def _slugify(s):
        for c in s.lower().replace(" ", "-"):
            if c in string.ascii_lowercase + "-":
                yield c

    return "".join(list(_slugify(value)))


def find_markdown_files(parent: str) -> list:
    """Return a list of all .md files in the given parent directory."""
    files = list(glob(f"{parent}/**/*.md", recursive=True))
    logger.info("Found %s markdown files in %s", len(files), parent)
    return files


def parse_front_matter(tokens: list) -> dict:
    """Parse front matter (YAML) from markdown tokens.
    
    Supports keys like: title, date, draft, tags, slug, url, 
    aliases, description.
    """
    tokens = [t for t in tokens if t.type == "front_matter"]
    if len(tokens) == 0:
        return {}

    t = tokens[0]
    fm = yaml.safe_load(t.content) or {}

    try:
        # Parse dates into datetime objects
        if "date" in fm:
            dt = arrow.get(fm["date"]).to("utc").datetime
            fm["date"] = dt
    except Exception as err:
        logger.error("Failed to convert date %s: %s", fm.get("date"), str(err))
    
    return fm


def get_template_context(filename):
    """Build template context from a markdown file."""
    logger.info("Building context for %s", filename)
    content = Path(filename).read_text()
    md = MarkdownIt().use(front_matter_plugin).enable("table")
    context = parse_front_matter(md.parse(content))
    context["html_content"] = md.render(content)
    return context


def get_template_name(
    filename: str, content_dir: str, default: str = "page.html"
) -> str:
    """Determine which template to use based on file location."""
    if "/blog/" in filename:
        return "blog.html"
    return default


def get_output_paths(output_dir, context, file):
    """Determine output path(s) for a file, handling aliases."""
    urls = []
    if "url" in context:
        urls.append(context["url"].strip("/"))
    
    if "aliases" in context:
        urls += [u.strip("/") for u in context["aliases"]]

    if len(urls) == 0:
        urls = [Path(file).stem]

    results = []
    for url in urls:
        path = Path(output_dir) / Path(url)
        path.mkdir(parents=True, exist_ok=True)
        path = path / Path("index.html")
        results.append(str(path))
    return results


def build_static(output):
    """Copy static files to output directory."""
    static_output = Path(output) / Path("static")
    logger.info("Building Static output in: %s", static_output)
    shutil.copytree(Path("static"), static_output, dirs_exist_ok=True)


def render(env, path, template, context):
    """Render a Jinja template and write to disk."""
    filename = "index.html" if template.endswith("html") else "index.md"
    template = env.get_template(template)
    content = template.render(**context)
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    path = path / Path(filename)
    with open(path, "w") as f:
        f.write(content)
        logger.info("Wrote %s", path)


def build_index(env, output: str, index: list, top: int = 20):
    """Build index page with latest articles."""
    index = sorted(index, key=lambda d: d["date"], reverse=True)

    context = {
        "title": "Brad Montgomery",
        "subtitle": "Latest posts...",
        "posts": index[:top],
    }
    render(env, Path(output), "index.html", context)

    context = {
        "title": "Brad Montgomery",
        "subtitle": "Brad's Blog. All of it.",
        "posts": index,
    }
    render(env, Path(output) / Path("blog"), "index.html", context)


def build_date_archives(env, output: str, index: list):
    """Build archive pages organized by year/month/day."""
    articles = defaultdict(list)
    for post in index:
        pub_year = post["date"].strftime("%Y")
        pub_month = post["date"].strftime("%Y/%m")
        pub_day = post["date"].strftime("%Y/%m/%d")
        year_path = f"blog/{pub_year}"
        month_path = f"blog/{pub_month}"
        day_path = f"blog/{pub_day}"
        articles[year_path].append(post)
        articles[month_path].append(post)
        articles[day_path].append(post)

    for path, posts in articles.items():
        context = {
            "title": "Archive",
            "subtitle": "",
            "posts": posts,
        }
        render(env, f"{output}/{path}", "index.html", context)


def normalize_tag(value: str) -> str:
    """Normalize tags to URL-safe strings."""
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def build_tags(env, output: str, index: list) -> None:
    """Build tag index and tag archive pages."""
    tags = sorted(set(chain(*[post.get("tags", []) for post in index])))
    tags = [normalize_tag(tag) for tag in tags]
    context = {
        "title": "Brad Montgomery",
        "subtitle": "Tags",
        "tags": [(tag, f"/blog/tags/{tag}/") for tag in tags],
    }
    render(env, f"{output}/blog/tags/", "tags.html", context)

    by_tags = defaultdict(list)
    for post in index:
        for tag in post.get("tags", []):
            tag = normalize_tag(tag)
            by_tags[tag].append(post)

    for tag, posts in by_tags.items():
        context = {
            "title": "Brad Montgomery",
            "subtitle": f"Tagged {tag}",
            "posts": posts,
        }
        render(env, f"{output}/blog/tags/{tag}", "index.html", context)


def build_feeds(output: str, index: list) -> None:
    """Build RSS and Atom feeds."""
    rss_path = Path(output) / Path("feed/rss/")
    rss_file = rss_path / Path("rss.xml")
    os.makedirs(rss_path, exist_ok=True)
    rss_file.touch(exist_ok=True)

    atom_path = Path(output) / Path("feed/atom/")
    atom_file = atom_path / Path("atom.xml")
    os.makedirs(atom_path, exist_ok=True)
    atom_file.touch(exist_ok=True)

    fg = FeedGenerator()
    fg.id("https://BradMontgomery.net")
    fg.title("BradMontgomery.net")
    fg.author({"name": "Brad Montgomery"})
    fg.link(href="https://bradmontgomery.net", rel="alternate")
    fg.subtitle("brad's blog")
    fg.language("en")

    items = sorted(
        [post for post in index if not post.get("draft", False)], key=lambda p: p["date"]
    )
    for post in items:
        fe = fg.add_entry()
        fe.id("https://bradmontgomery.net" + post["url"])
        fe.author(name="Brad Montgomery")
        fe.title(post["title"])
        fe.link(href="https://bradmontgomery.net" + post["url"])
        fe.content(post["html_content"])
        fe.description(description=post.get("description"))
        fe.pubdate(post["date"])

    logger.info("Generating ATOM feed")
    fg.atom_file(atom_file)
    logger.info("Wrote ATOM feed to %s", atom_file)

    logger.info("Generating RSS feed")
    fg.rss_file(rss_file)
    logger.info("Wrote RSS feed to %s", rss_file)


def copy_texts(content: str, output: str) -> None:
    """Copy .txt files from content/texts/ to root of output."""
    src_path = Path(content) / Path("texts")
    dst_path = Path(output)
    for file in glob(f"{src_path}/*.txt"):
        logger.info("Copying %s to %s", file, dst_path)
        shutil.copyfile(file, str(dst_path / Path(file).name))


# --- CLI Commands ---


@click.group()
def cli():
    """Static site generator."""
    pass


@cli.command()
@click.option(
    "--content",
    default="content",
    help="Content directory to create",
)
@click.option(
    "--templates",
    default="templates",
    help="Templates directory to create",
)
@click.option(
    "--output",
    default="docs",
    help="Output directory to create",
)
def init(content, templates, output):
    """Initialize a new site structure."""
    dirs_to_create = [
        (content, content),
        (f"{content}/blog", f"{content}/blog"),
        (f"{content}/pages", f"{content}/pages"),
        (f"{content}/texts", f"{content}/texts"),
        (templates, templates),
        (output, output),
    ]
    
    existing = []
    for path, display_name in dirs_to_create:
        if Path(path).exists():
            existing.append(display_name)
    
    if existing:
        console.print("[bold yellow]⚠️  Warning: The following directories already exist:[/bold yellow]")
        for name in existing:
            console.print(f"  • {name}", style="yellow")
        if not click.confirm("Continue anyway?"):
            console.print("[red]Aborted.[/red]")
            return
    
    for path, display_name in dirs_to_create:
        Path(path).mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created [cyan]{display_name}[/cyan]")
    
    console.print()
    console.print("[bold green]✓ Site structure initialized![/bold green]")
    
    next_steps = f"""[bold]Next steps:[/bold]

1. Add your markdown files to:
   • [cyan]{content}/blog/[/cyan] (for blog posts)
   • [cyan]{content}/pages/[/cyan] (for pages)

2. Create or customize Jinja2 templates in: [cyan]{templates}/[/cyan]

3. Build your site with: [bold]site build[/bold]
"""
    console.print(Panel(next_steps, title="[bold blue]Getting Started[/bold blue]"))


@cli.command()
@click.option(
    "--output", default="docs", help="Output directory from which files are served"
)
@click.option("--addr", default="", help="Address to listen on")
@click.option("--port", default=8000, help="Port to listen on")
def server(output, addr, port):
    """Run a local preview HTTP server."""
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, request, client_address, server, directory=output):
            super().__init__(request, client_address, server, directory=output)

    httpd = http.server.HTTPServer((addr, port), Handler)
    logger.info("Listening on %s:%s in %s...", addr, port, output)
    httpd.serve_forever()


@cli.command()
def new():
    """Create a new blog post."""
    env = Environment(loader=PackageLoader("sitebuilder"), autoescape=select_autoescape())

    prompts = [
        ("date", "Date (default is now): "),
        ("title", "Title: "),
        ("tags", "Tags (comma-separated): "),
        ("description", "Description: "),
        ("draft", "Draft (false): "),
    ]
    context = {}
    for key, prompt in prompts:
        context[key] = input(prompt)
        if key == "title":
            context["slug"] = to_slug(context[key])
        elif key == "date":
            context[key] = (
                arrow.utcnow().datetime
                if not context[key]
                else arrow.get(context[key]).datetime
            )
        elif key == "draft":
            context[key] = True if context[key] == "true" else False
        elif key == "tags":
            context[key] = [normalize_tag(tag) for tag in context[key].split(",")]

    context["url"] = f"/blog/{context['slug']}/"
    datestring = context["date"].strftime("%Y/%m/%d")
    context["alias"] = f"/blog/{datestring}/{context['slug']}/"
    render(env, f"content/blog/{context['slug']}", "content.md", context)


@cli.command()
@click.option("--content", default="content", help="Content directory")
@click.option("--templates", default="templates", help="Template directory")
@click.option("--output", default="docs", help="Output directory")
def build(content, templates, output):
    """Build the site."""
    start = time()

    env = Environment(loader=PackageLoader("sitebuilder"), autoescape=select_autoescape())

    index = []

    for file in find_markdown_files(content):
        context = get_template_context(file)
        template = env.get_template(get_template_name(file, content))
        html_content = template.render(**context)

        for path in get_output_paths(output, context, file):
            with open(path, "w") as f:
                f.write(html_content)
                logger.info("Wrote: %s", path)

        if file.strip(content).startswith("/blog"):
            index.append(context)

    build_index(env, output, index)
    build_tags(env, output, index)
    build_date_archives(env, output, index)
    build_feeds(output, index)

    build_static(output)
    copy_texts(content, output)

    elapsed = round(time() - start, 2)
    logger.info("Completed in %s seconds", elapsed)


if __name__ == "__main__":
    cli()
