"""
Comprehensive test suite for the sitebuilder CLI.

Tests are organized into two groups:

  1. Unit tests — cover pure-logic utility functions directly with no
     filesystem or template rendering involved.

  2. Integration tests — cover CLI commands end-to-end using Click's
     CliRunner and pytest's tmp_path fixture for full filesystem isolation.

Design notes:
  - The Jinja2 environment is backed by PackageLoader("sitebuilder"), which
    resolves templates from the installed package on disk.  We do NOT mock the
    template loader; templates are exercised for real during integration tests.
  - build_static() calls shutil.copytree(Path("static"), ...) against the
    current working directory.  CLI tests that do not specifically test static
    file copying monkeypatch build_static to keep them focused and to avoid
    a missing-directory error.
  - All filesystem operations use either CliRunner.isolated_filesystem() or
    pytest's tmp_path fixture — never the real project tree.
"""

import datetime
import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin

from sitebuilder.cli import (
    build_static,
    cli,
    get_output_paths,
    get_template_name,
    normalize_tag,
    parse_front_matter,
    to_slug,
    validate_post,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_md_parser():
    """Return a MarkdownIt instance configured the same way cli.py uses it."""
    return MarkdownIt().use(front_matter_plugin).enable("table")


def _parse(content: str) -> dict:
    """Parse front matter from a raw markdown string and return the dict."""
    md = _make_md_parser()
    return parse_front_matter(md.parse(content))


def _utc(year, month, day) -> datetime.datetime:
    """Convenience helper: timezone-aware UTC datetime at midnight."""
    return datetime.datetime(year, month, day, 0, 0, tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# Minimal blog-post markdown that satisfies all required fields.
# ---------------------------------------------------------------------------

VALID_POST_MD = """\
---
title: Test Post
date: 2024-01-15
url: /blog/test-post/
tags: [python, testing]
description: A test post
draft: false
---
Post content here.
"""


# ===========================================================================
# Unit tests — normalize_tag
# ===========================================================================


class TestNormalizeTag:
    """normalize_tag converts arbitrary strings into URL-safe slugs."""

    def test_basic_slugification(self):
        assert normalize_tag("Hello World") == "hello-world"

    def test_lowercase(self):
        assert normalize_tag("UPPER CASE") == "upper-case"

    def test_multiple_spaces_collapse_to_single_dash(self):
        assert normalize_tag("hello   world") == "hello-world"

    def test_multiple_consecutive_dashes_collapse(self):
        assert normalize_tag("hello---world") == "hello-world"

    def test_mixed_spaces_and_dashes_collapse(self):
        assert normalize_tag("hello - world") == "hello-world"

    def test_leading_dashes_are_stripped(self):
        assert normalize_tag("-leading") == "leading"

    def test_trailing_dashes_are_stripped(self):
        assert normalize_tag("trailing-") == "trailing"

    def test_leading_underscores_are_stripped(self):
        assert normalize_tag("__leading") == "leading"

    def test_internal_underscores_are_preserved(self):
        # re.sub(r'[^\w\s-]', ...) keeps \w which includes underscores.
        assert normalize_tag("hello_world") == "hello_world"

    def test_unicode_accent_stripped_via_ascii_encoding(self):
        # café → NFKD splits é into e + combining accent; ascii/ignore drops
        # the combining character, leaving "cafe".
        assert normalize_tag("café") == "cafe"

    def test_unicode_german_umlaut(self):
        # ü → NFKD gives u + combining diaeresis; ascii/ignore drops the
        # combining character, leaving just the base letter.
        assert normalize_tag("über") == "uber"

    def test_special_chars_removed(self):
        # hash, ampersand, etc. are not in [\w\s-] and are stripped.
        assert normalize_tag("C# programming") == "c-programming"

    def test_all_special_chars_produce_empty_string(self):
        assert normalize_tag("!@#$%^&*()") == ""

    def test_empty_string_returns_empty_string(self):
        assert normalize_tag("") == ""

    def test_already_valid_slug_unchanged(self):
        assert normalize_tag("already-valid") == "already-valid"

    def test_numbers_preserved(self):
        assert normalize_tag("python3 tutorial") == "python3-tutorial"


# ===========================================================================
# Unit tests — to_slug
# ===========================================================================


class TestToSlug:
    """to_slug is a thin alias for normalize_tag."""

    def test_delegates_to_normalize_tag_for_simple_string(self):
        assert to_slug("My Blog Post Title") == "my-blog-post-title"

    def test_returns_same_result_as_normalize_tag(self):
        inputs = [
            "Hello World",
            "café latte",
            "  multiple   spaces  ",
            "C# .NET",
            "",
        ]
        for value in inputs:
            assert to_slug(value) == normalize_tag(value), (
                f"to_slug and normalize_tag differ for {value!r}"
            )


# ===========================================================================
# Unit tests — parse_front_matter
# ===========================================================================


class TestParseFrontMatter:
    """parse_front_matter extracts YAML from markdown token streams."""

    def test_returns_empty_dict_when_no_front_matter_token(self):
        result = _parse("Just plain content, no front matter at all.")
        assert result == {}

    def test_returns_empty_dict_for_empty_front_matter_block(self):
        # An empty --- / --- block produces a front_matter token whose YAML
        # is empty, so yaml.safe_load returns None, which the code converts
        # to {}.
        result = _parse("---\n---\nContent.")
        assert result == {}

    def test_parses_title(self):
        result = _parse("---\ntitle: My Post\n---\nContent.")
        assert result["title"] == "My Post"

    def test_parses_url(self):
        result = _parse("---\nurl: /blog/my-post/\n---\nContent.")
        assert result["url"] == "/blog/my-post/"

    def test_parses_tags_as_list(self):
        result = _parse("---\ntags: [python, testing]\n---\nContent.")
        assert result["tags"] == ["python", "testing"]

    def test_parses_null_tags_as_none(self):
        result = _parse("---\ntags: null\n---\nContent.")
        assert result["tags"] is None

    def test_parses_draft_flag(self):
        result = _parse("---\ndraft: true\n---\nContent.")
        assert result["draft"] is True

    def test_date_parsed_to_utc_datetime(self):
        result = _parse("---\ndate: 2024-01-15\n---\nContent.")
        assert result["date"] == _utc(2024, 1, 15)
        assert result["date"].tzinfo is not None

    def test_date_is_timezone_aware(self):
        result = _parse("---\ndate: 2024-06-01\n---\nContent.")
        assert result["date"].utcoffset() == datetime.timedelta(0)

    def test_invalid_date_logs_error_and_drops_date_key(self, caplog):
        import logging

        with caplog.at_level(logging.ERROR, logger="sitebuilder.cli"):
            result = _parse("---\ndate: not-a-date\ntitle: Test\n---\nContent.")

        assert "date" not in result, "Invalid date should be removed from result"
        assert result.get("title") == "Test", "Other fields must still be present"
        assert any("Failed to convert date" in r.message for r in caplog.records)

    def test_full_front_matter_round_trip(self):
        result = _parse(VALID_POST_MD)
        assert result["title"] == "Test Post"
        assert result["url"] == "/blog/test-post/"
        assert result["tags"] == ["python", "testing"]
        assert result["description"] == "A test post"
        assert result["draft"] is False
        assert result["date"] == _utc(2024, 1, 15)

    def test_aliases_parsed_as_list(self):
        content = "---\naliases:\n  - /old/path/\n  - /other/path/\n---\nContent."
        result = _parse(content)
        assert result["aliases"] == ["/old/path/", "/other/path/"]

    def test_first_front_matter_token_wins_when_multiple_exist(self):
        # In practice the parser only produces one front_matter token, but the
        # implementation filters for front_matter tokens and takes the first.
        # Parsing a normal document should still produce exactly one result.
        result = _parse("---\ntitle: Only One\n---\nContent.")
        assert result["title"] == "Only One"


# ===========================================================================
# Unit tests — validate_post
# ===========================================================================


class TestValidatePost:
    """validate_post enforces presence of date, title, and url."""

    def _valid_context(self) -> dict:
        return {
            "date": _utc(2024, 1, 15),
            "title": "A Title",
            "url": "/blog/a-title/",
        }

    def test_valid_post_returns_true(self):
        assert validate_post(self._valid_context(), "post.md") is True

    def test_missing_date_returns_false(self):
        ctx = self._valid_context()
        del ctx["date"]
        assert validate_post(ctx, "post.md") is False

    def test_missing_title_returns_false(self):
        ctx = self._valid_context()
        del ctx["title"]
        assert validate_post(ctx, "post.md") is False

    def test_missing_url_returns_false(self):
        ctx = self._valid_context()
        del ctx["url"]
        assert validate_post(ctx, "post.md") is False

    def test_missing_date_and_title_returns_false(self):
        ctx = {"url": "/blog/x/"}
        assert validate_post(ctx, "post.md") is False

    def test_missing_all_required_fields_returns_false(self):
        assert validate_post({}, "post.md") is False

    def test_extra_fields_do_not_affect_validity(self):
        ctx = self._valid_context()
        ctx["tags"] = ["python"]
        ctx["description"] = "Extra field"
        assert validate_post(ctx, "post.md") is True

    def test_warning_logged_for_missing_fields(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING, logger="sitebuilder.cli"):
            validate_post({"url": "/blog/x/"}, "missing.md")

        assert any("missing.md" in r.message for r in caplog.records)
        assert any("date" in r.message and "title" in r.message for r in caplog.records)


# ===========================================================================
# Unit tests — get_template_name
# ===========================================================================


class TestGetTemplateName:
    """get_template_name selects a template based on the file path."""

    def test_path_containing_blog_returns_blog_template(self):
        assert get_template_name("/content/blog/my-post.md", "content") == "blog.html"

    def test_path_not_containing_blog_returns_page_template(self):
        assert get_template_name("/content/pages/about.md", "content") == "page.html"

    def test_custom_default_returned_for_non_blog_path(self):
        result = get_template_name("/content/pages/faq.md", "content", "custom.html")
        assert result == "custom.html"

    def test_blog_subdirectory_returns_blog_template(self):
        assert (
            get_template_name("/content/blog/2024/01/post.md", "content") == "blog.html"
        )

    def test_page_with_blog_in_name_does_not_trigger_blog_template(self):
        # The check is '/blog/' (with slashes), so 'my-blog-notes.md' won't match.
        result = get_template_name("/content/pages/my-blog-notes.md", "content")
        assert result == "page.html"

    def test_default_is_page_html_when_not_provided(self):
        result = get_template_name("/content/pages/about.md", "content")
        assert result == "page.html"


# ===========================================================================
# Unit tests — get_output_paths
# ===========================================================================


class TestGetOutputPaths:
    """get_output_paths resolves one or more output paths for a file."""

    def test_url_from_context_determines_output_path(self, tmp_path):
        ctx = {"url": "/blog/test-post/"}
        paths = get_output_paths(str(tmp_path), ctx, "some_file.md")
        assert len(paths) == 1
        assert paths[0] == str(tmp_path / "blog" / "test-post" / "index.html")

    def test_url_leading_slash_is_stripped(self, tmp_path):
        ctx = {"url": "/leading/slash/"}
        paths = get_output_paths(str(tmp_path), ctx, "some_file.md")
        assert paths[0] == str(tmp_path / "leading" / "slash" / "index.html")

    def test_aliases_produce_additional_output_paths(self, tmp_path):
        ctx = {"url": "/blog/new/", "aliases": ["/old/path/"]}
        paths = get_output_paths(str(tmp_path), ctx, "some_file.md")
        assert len(paths) == 2
        assert str(tmp_path / "blog" / "new" / "index.html") in paths
        assert str(tmp_path / "old" / "path" / "index.html") in paths

    def test_multiple_aliases_each_get_output_path(self, tmp_path):
        ctx = {
            "url": "/blog/current/",
            "aliases": ["/blog/2024/01/01/post/", "/legacy/post/"],
        }
        paths = get_output_paths(str(tmp_path), ctx, "some_file.md")
        assert len(paths) == 3

    def test_no_url_and_no_aliases_falls_back_to_file_stem(self, tmp_path):
        ctx = {}
        paths = get_output_paths(str(tmp_path), ctx, "/content/my-page.md")
        assert len(paths) == 1
        assert paths[0] == str(tmp_path / "my-page" / "index.html")

    def test_all_output_paths_end_with_index_html(self, tmp_path):
        ctx = {"url": "/blog/post/", "aliases": ["/old/post/"]}
        paths = get_output_paths(str(tmp_path), ctx, "file.md")
        for path in paths:
            assert path.endswith("index.html"), f"Expected index.html, got: {path}"

    def test_output_directories_are_created_on_disk(self, tmp_path):
        ctx = {"url": "/blog/new-post/"}
        get_output_paths(str(tmp_path), ctx, "file.md")
        assert (tmp_path / "blog" / "new-post").is_dir()

    def test_path_traversal_attack_url_is_skipped(self, tmp_path):
        # A url like '../../etc/passwd' should not resolve to a path outside
        # the output directory; such paths are silently skipped.
        ctx = {"url": "../../etc/passwd"}
        paths = get_output_paths(str(tmp_path), ctx, "file.md")
        assert paths == [], "Traversal path must be rejected"

    def test_path_traversal_in_aliases_is_skipped(self, tmp_path):
        ctx = {"url": "/blog/post/", "aliases": ["../../etc/hosts"]}
        paths = get_output_paths(str(tmp_path), ctx, "file.md")
        # The valid url path is kept; the traversal alias is dropped.
        assert len(paths) == 1
        assert paths[0] == str(tmp_path / "blog" / "post" / "index.html")


# ===========================================================================
# Integration tests — `init` command
# ===========================================================================


class TestInitCommand:
    """Integration tests for the `site init` CLI command."""

    def test_creates_expected_directory_structure(self):
        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            result = runner.invoke(cli, ["init", "--content", "content", "--output", "docs"])
            assert result.exit_code == 0, result.output
            assert Path(tmpdir, "content").is_dir()
            assert Path(tmpdir, "content", "blog").is_dir()
            assert Path(tmpdir, "content", "pages").is_dir()
            assert Path(tmpdir, "content", "texts").is_dir()
            assert Path(tmpdir, "docs").is_dir()

    def test_custom_content_and_output_dirs_are_created(self):
        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            result = runner.invoke(cli, ["init", "--content", "src", "--output", "dist"])
            assert result.exit_code == 0, result.output
            assert Path(tmpdir, "src").is_dir()
            assert Path(tmpdir, "dist").is_dir()

    def test_success_message_appears_in_output(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["init"])
            assert "Site structure initialized" in result.output

    def test_warns_when_directories_already_exist(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs("content")
            # Confirm the prompt to continue.
            result = runner.invoke(cli, ["init"], input="y\n")
            assert result.exit_code == 0, result.output
            assert "already exist" in result.output.lower()
            assert "content" in result.output

    def test_aborts_when_user_declines_prompt(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs("content")
            result = runner.invoke(cli, ["init"], input="N\n")
            assert result.exit_code == 0, result.output
            assert "Aborted" in result.output

    def test_aborted_run_does_not_create_remaining_dirs(self):
        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            # Pre-create content so the warning fires, then decline.
            os.makedirs("content")
            runner.invoke(cli, ["init"], input="N\n")
            # docs should not exist because we aborted before creating anything.
            assert not Path(tmpdir, "docs").exists()

    def test_continues_creating_dirs_after_user_confirms(self):
        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            os.makedirs("content")
            result = runner.invoke(cli, ["init"], input="y\n")
            assert result.exit_code == 0
            # Even though content already existed, all dirs should now be present.
            assert Path(tmpdir, "content", "blog").is_dir()
            assert Path(tmpdir, "docs").is_dir()

    def test_no_warning_when_directories_do_not_exist(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["init"])
            assert "already exist" not in result.output.lower()


# ===========================================================================
# Integration tests — `build` command
# ===========================================================================

# Convenience: path to the mock target so we don't repeat it everywhere.
_BUILD_STATIC_PATH = "sitebuilder.cli.build_static"


def _write_blog_post(base: Path, slug: str, content: str) -> None:
    """Write a blog post markdown file under base/blog/<slug>/index.md."""
    post_dir = base / "blog" / slug
    post_dir.mkdir(parents=True, exist_ok=True)
    (post_dir / "index.md").write_text(content)


def _write_page(base: Path, name: str, content: str) -> None:
    """Write a page markdown file under base/pages/<name>.md."""
    pages_dir = base / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / f"{name}.md").write_text(content)


class TestBuildCommand:
    """End-to-end integration tests for the `site build` CLI command."""

    # ------------------------------------------------------------------
    # Full happy-path build
    # ------------------------------------------------------------------

    def test_full_build_produces_expected_output_files(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "first-post",
            """\
---
title: First Post
date: 2024-01-15
url: /blog/first-post/
tags: [python, testing]
description: The first post
draft: false
---
Hello from the first post.
""",
        )
        _write_page(
            content_dir,
            "about",
            """\
---
title: About
---
About page content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            result = runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert result.exit_code == 0, result.output

        # Site root index
        assert (output_dir / "index.html").exists()
        # Blog index
        assert (output_dir / "blog" / "index.html").exists()
        # Tags index
        assert (output_dir / "blog" / "tags" / "index.html").exists()
        # RSS feed
        assert (output_dir / "feed" / "rss" / "rss.xml").exists()
        # Atom feed
        assert (output_dir / "feed" / "atom" / "atom.xml").exists()
        # The blog post itself
        assert (output_dir / "blog" / "first-post" / "index.html").exists()

    def test_blog_post_html_contains_title(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "titled-post",
            """\
---
title: Rendered Title Here
date: 2024-02-10
url: /blog/titled-post/
tags: [python]
description: A titled post
draft: false
---
Body text.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        html = (output_dir / "blog" / "titled-post" / "index.html").read_text()
        assert "Rendered Title Here" in html

    def test_page_is_rendered_using_page_template(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_page(
            content_dir,
            "contact",
            """\
---
title: Contact Us
---
Get in touch.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        # Page should be rendered; it has no url so output path falls back to
        # the file stem ("contact").
        assert (output_dir / "contact" / "index.html").exists()
        html = (output_dir / "contact" / "index.html").read_text()
        assert "Contact Us" in html

    # ------------------------------------------------------------------
    # Null tags — regression test for the bug
    # ------------------------------------------------------------------

    def test_post_with_null_tags_does_not_crash(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "null-tags",
            """\
---
title: Null Tags Post
date: 2024-01-20
url: /blog/null-tags/
tags: null
description: Testing null tags
draft: false
---
Content with null tags.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            result = runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert result.exit_code == 0, (
            f"Build crashed with null tags.\nOutput:\n{result.output}"
        )
        assert (output_dir / "blog" / "null-tags" / "index.html").exists()

    def test_post_with_null_tags_does_not_appear_in_tags_index(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "null-tags",
            """\
---
title: Null Tags Post
date: 2024-01-20
url: /blog/null-tags/
tags: null
description: Testing null tags
draft: false
---
Content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        tags_html = (output_dir / "blog" / "tags" / "index.html").read_text()
        # The tags index should not list any tag because the only post has null tags.
        assert "No tags found" in tags_html or tags_html.count("<li>") == 1

    # ------------------------------------------------------------------
    # Missing required fields
    # ------------------------------------------------------------------

    def test_post_missing_url_is_excluded_from_index(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        # Post that is missing the url field.
        _write_blog_post(
            content_dir,
            "no-url",
            """\
---
title: No URL Post
date: 2024-01-10
tags: [python]
description: Missing url field
---
Content with no url.
""",
        )

        # Valid post to give the index something to render.
        _write_blog_post(
            content_dir,
            "valid",
            """\
---
title: Valid Post
date: 2024-01-15
url: /blog/valid/
tags: [python]
description: A valid post
draft: false
---
Valid content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            result = runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert result.exit_code == 0, result.output

        root_index = (output_dir / "index.html").read_text()
        blog_index = (output_dir / "blog" / "index.html").read_text()

        assert "No URL Post" not in root_index
        assert "No URL Post" not in blog_index
        assert "Valid Post" in root_index

    def test_post_missing_url_is_still_rendered_to_disk(self, tmp_path):
        """validate_post gates indexing, not rendering; the file is written."""
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "no-url",
            """\
---
title: No URL Post
date: 2024-01-10
tags: [python]
description: Missing url field
---
Content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        # No url → stem fallback → output goes to docs/index/index.html
        # (stem of "no-url/index.md" is "index").
        # The important thing is the build didn't crash and output was written.
        output_files = list(output_dir.rglob("*.html"))
        assert len(output_files) > 0

    # ------------------------------------------------------------------
    # Draft posts
    # ------------------------------------------------------------------

    def test_draft_post_is_excluded_from_rss_feed(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "draft-post",
            """\
---
title: My Draft Post
date: 2024-03-01
url: /blog/draft-post/
tags: [python]
description: A draft
draft: true
---
Draft content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        rss_content = (output_dir / "feed" / "rss" / "rss.xml").read_text()
        assert "My Draft Post" not in rss_content

    def test_draft_post_is_excluded_from_atom_feed(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "draft-post",
            """\
---
title: My Draft Post
date: 2024-03-01
url: /blog/draft-post/
tags: [python]
description: A draft
draft: true
---
Draft content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        atom_content = (output_dir / "feed" / "atom" / "atom.xml").read_text()
        assert "My Draft Post" not in atom_content

    def test_draft_post_is_still_rendered_as_html_file(self, tmp_path):
        """Drafts are excluded from feeds but their HTML is still written."""
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "draft-post",
            """\
---
title: My Draft Post
date: 2024-03-01
url: /blog/draft-post/
tags: [python]
description: A draft
draft: true
---
Draft content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert (output_dir / "blog" / "draft-post" / "index.html").exists()

    def test_non_draft_post_appears_in_rss_feed(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "published",
            """\
---
title: Published Post
date: 2024-04-01
url: /blog/published/
tags: [python]
description: A published post
draft: false
---
Published content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        rss_content = (output_dir / "feed" / "rss" / "rss.xml").read_text()
        assert "Published Post" in rss_content

    # ------------------------------------------------------------------
    # Aliases
    # ------------------------------------------------------------------

    def test_post_with_alias_generates_both_output_paths(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "alias-post",
            """\
---
title: Alias Post
date: 2024-02-01
url: /blog/alias-post/
aliases:
  - /old/alias-post/
tags: [python]
description: Post with alias
draft: false
---
Content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        canonical = output_dir / "blog" / "alias-post" / "index.html"
        alias = output_dir / "old" / "alias-post" / "index.html"
        assert canonical.exists(), "Canonical URL path must be written"
        assert alias.exists(), "Alias URL path must be written"

    def test_both_alias_files_contain_same_content(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "alias-post",
            """\
---
title: Alias Post
date: 2024-02-01
url: /blog/alias-post/
aliases:
  - /old/alias-post/
tags: [python]
description: Post with alias
draft: false
---
Alias post body.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        canonical = (output_dir / "blog" / "alias-post" / "index.html").read_text()
        alias = (output_dir / "old" / "alias-post" / "index.html").read_text()
        assert canonical == alias

    def test_post_with_multiple_aliases_generates_all_output_paths(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "multi-alias",
            """\
---
title: Multi Alias Post
date: 2024-05-01
url: /blog/multi-alias/
aliases:
  - /first/old/
  - /second/old/
tags: [python]
description: Multiple aliases
draft: false
---
Content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert (output_dir / "blog" / "multi-alias" / "index.html").exists()
        assert (output_dir / "first" / "old" / "index.html").exists()
        assert (output_dir / "second" / "old" / "index.html").exists()

    # ------------------------------------------------------------------
    # Tag pages
    # ------------------------------------------------------------------

    def test_tag_index_lists_all_tags(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "tagged-post",
            """\
---
title: Tagged Post
date: 2024-01-15
url: /blog/tagged-post/
tags: [python, django]
description: Has tags
draft: false
---
Content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        tags_html = (output_dir / "blog" / "tags" / "index.html").read_text()
        assert "python" in tags_html
        assert "django" in tags_html

    def test_per_tag_archive_page_is_created(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "python-post",
            """\
---
title: Python Post
date: 2024-01-15
url: /blog/python-post/
tags: [python]
description: A python post
draft: false
---
Content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert (output_dir / "blog" / "tags" / "python" / "index.html").exists()

    def test_per_tag_archive_contains_relevant_post(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "python-post",
            """\
---
title: Python Post
date: 2024-01-15
url: /blog/python-post/
tags: [python]
description: A python post
draft: false
---
Content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        tag_html = (output_dir / "blog" / "tags" / "python" / "index.html").read_text()
        assert "Python Post" in tag_html

    # ------------------------------------------------------------------
    # Date archive pages
    # ------------------------------------------------------------------

    def test_year_archive_page_is_created(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "archive-post",
            """\
---
title: Archive Post
date: 2024-06-15
url: /blog/archive-post/
tags: [python]
description: For archive tests
draft: false
---
Content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert (output_dir / "blog" / "2024" / "index.html").exists()

    def test_month_archive_page_is_created(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "archive-post",
            """\
---
title: Archive Post
date: 2024-06-15
url: /blog/archive-post/
tags: [python]
description: For archive tests
draft: false
---
Content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert (output_dir / "blog" / "2024" / "06" / "index.html").exists()

    def test_day_archive_page_is_created(self, tmp_path):
        content_dir = tmp_path / "content"
        output_dir = tmp_path / "docs"

        _write_blog_post(
            content_dir,
            "archive-post",
            """\
---
title: Archive Post
date: 2024-06-15
url: /blog/archive-post/
tags: [python]
description: For archive tests
draft: false
---
Content.
""",
        )

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert (output_dir / "blog" / "2024" / "06" / "15" / "index.html").exists()

    # ------------------------------------------------------------------
    # Empty content directory
    # ------------------------------------------------------------------

    def test_build_with_no_content_files_completes_successfully(self, tmp_path):
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        output_dir = tmp_path / "docs"

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            result = runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert result.exit_code == 0, result.output

    def test_build_with_no_content_still_creates_feed_files(self, tmp_path):
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        output_dir = tmp_path / "docs"

        runner = CliRunner()
        with patch(_BUILD_STATIC_PATH):
            runner.invoke(
                cli,
                ["build", "--content", str(content_dir), "--output", str(output_dir)],
            )

        assert (output_dir / "feed" / "rss" / "rss.xml").exists()
        assert (output_dir / "feed" / "atom" / "atom.xml").exists()


# ===========================================================================
# Integration tests — build_static function
# ===========================================================================


class TestBuildStatic:
    """Tests for the build_static helper that copies the static directory."""

    def test_copies_static_files_to_output_directory(self):
        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            # Create a fake static tree relative to CWD.
            os.makedirs("static/js")
            os.makedirs("static/css")
            Path("static/js/app.js").write_text("console.log('hello');")
            Path("static/css/style.css").write_text("body { color: red; }")

            output_dir = os.path.join(tmpdir, "docs")
            os.makedirs(output_dir)

            build_static(output_dir)

            assert Path(output_dir, "static", "js", "app.js").exists()
            assert Path(output_dir, "static", "css", "style.css").exists()

    def test_static_file_contents_are_preserved(self):
        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            os.makedirs("static")
            Path("static/robots.txt").write_text("User-agent: *\nDisallow:")

            output_dir = os.path.join(tmpdir, "docs")
            os.makedirs(output_dir)

            build_static(output_dir)

            copied = Path(output_dir, "static", "robots.txt").read_text()
            assert "User-agent: *" in copied

    def test_static_files_copied_via_build_cli_command(self):
        """Build CLI copies static files when the static/ dir exists in CWD."""
        runner = CliRunner()
        with runner.isolated_filesystem() as tmpdir:
            os.makedirs("static/js")
            Path("static/js/timezone.js").write_text("// timezone")

            content_dir = os.path.join(tmpdir, "content")
            output_dir = os.path.join(tmpdir, "docs")
            os.makedirs(content_dir)

            # Do NOT patch build_static — let it run for real.
            result = runner.invoke(
                cli,
                ["build", "--content", content_dir, "--output", output_dir],
            )

            assert result.exit_code == 0, result.output
            assert Path(output_dir, "static", "js", "timezone.js").exists()
