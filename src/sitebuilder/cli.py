"""
A simple static site generator.

Markdown content goes in content/blog/ or content/pages/
Templates are powered by Jinja2
Run `site build` to build the site.
"""

import http.server
import logging
import re
import shutil
import tomllib
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date as date_cls, datetime, timezone
from glob import glob
from itertools import chain
from pathlib import Path
from time import time

import arrow
import rich_click as click
from feedgen.feed import FeedGenerator
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader, select_autoescape
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
    handlers=[RichHandler(console=console, show_time=False)],
)
logger = logging.getLogger(__name__)

@dataclass
class SiteConfig:
    title: str = "My Site"
    url: str = "http://localhost"
    author: str = ""
    subtitle: str = ""
    templates_dir: str | None = None  # path relative to CWD; None = package templates only
    static_dir: str = "static"        # user's static assets dir, relative to CWD


def load_config(config_path: Path | None = None) -> SiteConfig:
    """Load site configuration from site.toml, returning defaults if absent."""
    path = config_path or Path("site.toml")
    if not path.exists():
        return SiteConfig()
    with path.open("rb") as f:
        data = tomllib.load(f)
    site = data.get("site", {})
    build = data.get("build", {})
    return SiteConfig(
        title=site.get("title", "My Site"),
        url=site.get("url", "http://localhost"),
        author=site.get("author", ""),
        subtitle=site.get("subtitle", ""),
        templates_dir=build.get("templates_dir"),
        static_dir=build.get("static_dir", "static"),
    )


def normalize_tag(value: str) -> str:
    """Normalize a string to a URL-safe slug.

    Handles unicode characters, collapses multiple dashes, and strips
    leading/trailing dashes and underscores.
    """
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def to_slug(value: str) -> str:
    """Convert a string to a URL-safe slug.

    This is an alias for normalize_tag() for semantic clarity when working with
    post titles rather than tags.
    """
    return normalize_tag(value)


def get_jinja_env(config: SiteConfig | None = None) -> Environment:
    """Create and return a configured Jinja2 environment."""
    package_loader = PackageLoader("sitebuilder")
    if config and config.templates_dir:
        user_dir = Path(config.templates_dir)
        if user_dir.is_dir():
            loader = ChoiceLoader([FileSystemLoader(str(user_dir)), package_loader])
        else:
            logger.warning("templates_dir %r not found; using package templates", config.templates_dir)
            loader = package_loader
    else:
        loader = package_loader
    return Environment(loader=loader, autoescape=select_autoescape())


def tag_base_template(env, tag: str, default: str = "base.html") -> str:
    """Return the base template name for a tag's archive page.

    Uses ``base_<tag>.html`` when a template by that name exists in the Jinja
    environment (user ``templates_dir`` first, package templates as fallback);
    otherwise returns ``default``.
    """
    if not tag:
        return default
    return env.select_template([f"base_{tag}.html", default]).name


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
        fm.pop("date", None)  # Remove invalid date to prevent downstream errors

    return fm


def validate_post(context: dict, filename: str) -> bool:
    """Validate that a post has required fields for indexing.

    Required fields: date, title, url
    Returns True if valid, False otherwise.
    """
    required_fields = ["date", "title", "url"]
    missing = [field for field in required_fields if field not in context]
    if missing:
        logger.warning(
            "Skipping %s: missing required fields: %s", filename, ", ".join(missing)
        )
        return False
    return True


def get_template_context(filename):
    """Build template context from a markdown file."""
    logger.info("Building context for %s", filename)
    content = Path(filename).read_text()
    md = MarkdownIt().use(front_matter_plugin).enable("table")
    context = parse_front_matter(md.parse(content))
    context["html_content"] = md.render(content)
    context["tags"] = context.get("tags") or []
    if "date" in context:
        context["date_iso"] = context["date"].isoformat()
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
    output_root = Path(output_dir).resolve()
    urls = []
    if "url" in context:
        urls.append(context["url"].strip("/"))

    if "aliases" in context:
        urls += [u.strip("/") for u in context["aliases"]]

    if len(urls) == 0:
        urls = [Path(file).stem]

    results = []
    for url in urls:
        path = (output_root / url).resolve()
        if not path.is_relative_to(output_root):
            logger.warning("Skipping invalid path outside output directory: %s", url)
            continue
        path.mkdir(parents=True, exist_ok=True)
        path = path / Path("index.html")
        results.append(str(path))
    return results


def build_static(output: str, config: SiteConfig | None = None) -> None:
    """Copy static files to output directory."""
    static_output = Path(output) / "static"
    logger.info("Building static output in: %s", static_output)
    static_output.mkdir(parents=True, exist_ok=True)

    # Always copy vendored package assets first
    vendored = Path(__file__).parent / "templates" / "static"
    if vendored.is_dir():
        shutil.copytree(vendored, static_output, dirs_exist_ok=True)

    # Overlay user's static dir on top (user files win on conflict)
    user_static = Path(config.static_dir if config else "static")
    if user_static.is_dir():
        shutil.copytree(user_static, static_output, dirs_exist_ok=True)
    else:
        logger.info("No user static dir at %r; skipping overlay", str(user_static))


def render(env, dest_dir, template_name, context):
    """Render a Jinja template and write to disk."""
    filename = "index.html" if template_name.endswith("html") else "index.md"
    template = env.get_template(template_name)
    content = template.render(**context)
    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)
    dest_file = dest_path / Path(filename)
    with open(dest_file, "w") as f:
        f.write(content)
        logger.info("Wrote %s", dest_file)


def compute_sparkline_weeks(
    index: list, today: date_cls | None = None, weeks: int = 13
) -> list[int]:
    """Return a list of post counts per week over the last `weeks` weeks.

    Oldest week first; the final element covers the 7 days ending on `today`.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()
    buckets = [0] * weeks
    span_days = weeks * 7
    for post in index:
        post_date = post.get("date")
        if post_date is None:
            continue
        if hasattr(post_date, "date"):
            post_date = post_date.date()
        days_ago = (today - post_date).days
        if days_ago < 0 or days_ago >= span_days:
            continue
        bucket = (weeks - 1) - days_ago // 7
        buckets[bucket] += 1
    return buckets


def build_index(env, output: str, index: list, config: SiteConfig, top: int = 20):
    """Build index page with latest articles."""
    index = sorted(index, key=lambda d: d["date"], reverse=True)
    sparkline_weeks = compute_sparkline_weeks(index)
    sparkline_max = max(sparkline_weeks) if sparkline_weeks else 0

    context = {
        "title": config.title,
        "subtitle": config.subtitle,
        "posts": index[:top],
        "sparkline_weeks": sparkline_weeks,
        "sparkline_max": sparkline_max,
    }
    render(env, Path(output), "index.html", context)

    context = {
        "title": config.title,
        "subtitle": config.subtitle,
        "posts": index,
        "sparkline_weeks": sparkline_weeks,
        "sparkline_max": sparkline_max,
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


def build_tags(env, output: str, index: list, config: SiteConfig) -> None:
    """Build tag index and tag archive pages."""
    tags = sorted(set(chain(*[post.get("tags") or [] for post in index])))
    tags = [normalize_tag(tag) for tag in tags]
    context = {
        "title": config.title,
        "subtitle": "Tags",
        "tags": [(tag, f"/blog/tags/{tag}/") for tag in tags],
    }
    render(env, f"{output}/blog/tags/", "tags.html", context)

    by_tags = defaultdict(list)
    for post in index:
        for tag in post.get("tags") or []:
            tag = normalize_tag(tag)
            by_tags[tag].append(post)

    for tag, posts in by_tags.items():
        posts = sorted(posts, key=lambda d: d["date"], reverse=True)
        context = {
            "title": config.title,
            "subtitle": f"Tagged {tag}",
            "tag": tag,
            "posts": posts,
            "base_template": tag_base_template(env, tag),
        }
        render(env, f"{output}/blog/tags/{tag}", "index.html", context)


def build_feeds(output: str, index: list, config: SiteConfig) -> None:
    """Build RSS and Atom feeds."""
    rss_path = Path(output) / Path("feed/rss/")
    rss_file = rss_path / Path("rss.xml")
    rss_path.mkdir(parents=True, exist_ok=True)
    rss_file.touch(exist_ok=True)

    atom_path = Path(output) / Path("feed/atom/")
    atom_file = atom_path / Path("atom.xml")
    atom_path.mkdir(parents=True, exist_ok=True)
    atom_file.touch(exist_ok=True)

    fg = FeedGenerator()
    fg.id(config.url)
    fg.title(config.title)
    fg.author({"name": config.author})
    fg.link(href=config.url, rel="alternate")
    fg.subtitle(config.subtitle or config.title)
    fg.language("en")

    items = sorted(
        [post for post in index if not post.get("draft", False)],
        key=lambda p: p["date"],
    )
    for post in items:
        fe = fg.add_entry()
        fe.id(config.url + post["url"])
        fe.author(name=config.author)
        fe.title(post["title"])
        fe.link(href=config.url + post["url"])
        fe.content(post["html_content"])
        fe.description(description=post.get("description"))
        fe.pubDate(post["date"])

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
    "--output",
    default="docs",
    help="Output directory to create",
)
def init(content, output):
    """Initialize a new site structure."""
    dirs_to_create = [
        (content, content),
        (f"{content}/blog", f"{content}/blog"),
        (f"{content}/pages", f"{content}/pages"),
        (f"{content}/texts", f"{content}/texts"),
        (output, output),
    ]

    existing = []
    for path, display_name in dirs_to_create:
        if Path(path).exists():
            existing.append(display_name)

    if existing:
        console.print(
            "[bold yellow]⚠️  Warning: The following directories already exist:[/bold yellow]"
        )
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

2. Build your site with: [bold]site build[/bold]
"""
    console.print(Panel(next_steps, title="[bold blue]Getting Started[/bold blue]"))


@cli.command()
@click.option(
    "--output", default="docs", help="Output directory from which files are served"
)
@click.option("--addr", default="127.0.0.1", help="Address to listen on")
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
@click.option("--date", default=None, help="Post date; blank or omitted = now.")
@click.option("--title", default=None, help="Post title.")
@click.option("--tags", default=None, help="Comma-separated tags.")
@click.option("--description", default=None, help="Post description.")
@click.option("--draft/--no-draft", "draft", default=None, help="Mark post as draft.")
def new(date, title, tags, description, draft):
    """Create a new blog post.

    Any option not supplied is prompted for interactively, so the legacy
    `site new` flow still works when called with no arguments.
    """
    config = load_config()
    env = get_jinja_env(config)

    if date is None:
        date = input("Date (default is now): ")
    if title is None:
        title = input("Title: ")
    if tags is None:
        tags = input("Tags (comma-separated): ")
    if description is None:
        description = input("Description: ")
    if draft is None:
        draft = input("Draft (false): ") == "true"

    parsed_date = (
        arrow.utcnow().datetime if not date else arrow.get(date).datetime
    )
    tag_list = [normalize_tag(t) for t in tags.split(",") if t.strip()] if tags else []
    slug = to_slug(title)
    datestring = parsed_date.strftime("%Y/%m/%d")

    context = {
        "date": parsed_date,
        "title": title,
        "slug": slug,
        "tags": tag_list,
        "description": description,
        "draft": draft,
        "url": f"/blog/{slug}/",
        "alias": f"/blog/{datestring}/{slug}/",
    }
    render(env, f"content/blog/{slug}", "content.md", context)


@cli.command()
@click.option("--content", default="content", help="Content directory")
@click.option("--output", default="docs", help="Output directory")
def build(content, output):
    """Build the site."""
    start = time()

    config = load_config()
    env = get_jinja_env(config)

    index = []

    for file in find_markdown_files(content):
        context = get_template_context(file)
        context.setdefault("site_title", config.title)
        context.setdefault("site_subtitle", config.subtitle)
        context.setdefault("site_author", config.author)
        template = env.get_template(get_template_name(file, content))
        html_content = template.render(**context)

        for path in get_output_paths(output, context, file):
            with open(path, "w") as f:
                f.write(html_content)
                logger.info("Wrote: %s", path)

        if file.removeprefix(content).startswith("/blog"):
            if validate_post(context, file):
                index.append(context)

    build_index(env, output, index, config)
    build_tags(env, output, index, config)
    build_date_archives(env, output, index)
    build_feeds(output, index, config)

    build_static(output, config)
    copy_texts(content, output)

    elapsed = round(time() - start, 2)
    logger.info("Completed in %s seconds", elapsed)


if __name__ == "__main__":
    cli()
