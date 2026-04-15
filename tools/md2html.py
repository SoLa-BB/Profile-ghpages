#!/usr/bin/env python3
"""
md2html — Markdown to HTML converter for the portfolio site.

依存パッケージ不要（Python 3.9+ 標準ライブラリのみ）。

Usage:
    python md2html.py <input.md> [--output <dir>] [--type post|research]

Examples:
    python tools/md2html.py content/posts/my-article.md
    python tools/md2html.py content/posts/my-article.md --output posts
    python tools/md2html.py content/research/vr-study.md --type research

Markdown front matter (YAML-style):
    ---
    title: 記事タイトル
    date: 2025-01-01
    slug: my-article
    pdf: path/to/paper.pdf
    slides: https://docs.google.com/presentation/d/e/XXXX/embed
    ---
"""

import argparse
import html as html_module
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path


# ============================================================
# Lightweight Markdown → HTML converter (no dependencies)
# ============================================================

def md_to_html(text: str) -> str:
    """Convert Markdown text to HTML using only stdlib.
    
    Supports: headings, paragraphs, bold, italic, inline code,
    code blocks (fenced), blockquotes, unordered/ordered lists,
    links, images, horizontal rules, tables.
    """
    lines = text.split("\n")
    output = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # --- Fenced code blocks (``` or ~~~) ---
        fence_match = re.match(r"^(`{3,}|~{3,})(\w*)\s*$", line)
        if fence_match:
            fence_char = fence_match.group(1)[0]
            fence_len = len(fence_match.group(1))
            lang = fence_match.group(2)
            code_lines = []
            i += 1
            while i < len(lines):
                close_match = re.match(
                    rf"^{re.escape(fence_char)}{{{fence_len},}}\s*$", lines[i]
                )
                if close_match:
                    i += 1
                    break
                code_lines.append(lines[i])
                i += 1
            # Mermaid: render as <pre class="mermaid"> without escaping
            if lang == "mermaid":
                code_content = "\n".join(code_lines)
                output.append(
                    f'<pre class="mermaid">\n{code_content}\n</pre>'
                )
            else:
                code_content = "\n".join(
                    html_module.escape(l) for l in code_lines
                )
                if lang:
                    output.append(
                        f'<pre><code class="language-{lang}">{code_content}</code></pre>'
                    )
                else:
                    output.append(f"<pre><code>{code_content}</code></pre>")
            continue

        # --- Horizontal rule ---
        if re.match(r"^(\*{3,}|-{3,}|_{3,})\s*$", line):
            output.append("<hr>")
            i += 1
            continue

        # --- Headings ---
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            content = _inline(heading_match.group(2))
            output.append(f"<h{level}>{content}</h{level}>")
            i += 1
            continue

        # --- Blockquote ---
        if line.startswith(">"):
            bq_lines = []
            while i < len(lines) and (lines[i].startswith(">") or lines[i].strip() == ""):
                if lines[i].startswith(">"):
                    bq_lines.append(re.sub(r"^>\s?", "", lines[i]))
                elif bq_lines:
                    bq_lines.append("")
                else:
                    break
                i += 1
                if i < len(lines) and not lines[i].startswith(">") and lines[i].strip() != "":
                    break
            inner = md_to_html("\n".join(bq_lines))
            output.append(f"<blockquote>{inner}</blockquote>")
            continue

        # --- Unordered list ---
        if re.match(r"^[\*\-\+]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^[\*\-\+]\s+", lines[i]):
                item_text = re.sub(r"^[\*\-\+]\s+", "", lines[i])
                items.append(f"<li>{_inline(item_text)}</li>")
                i += 1
            output.append("<ul>\n" + "\n".join(items) + "\n</ul>")
            continue

        # --- Ordered list ---
        if re.match(r"^\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                item_text = re.sub(r"^\d+\.\s+", "", lines[i])
                items.append(f"<li>{_inline(item_text)}</li>")
                i += 1
            output.append("<ol>\n" + "\n".join(items) + "\n</ol>")
            continue

        # --- Table ---
        if i + 1 < len(lines) and "|" in line and re.match(r"^\|?\s*[-:]+", lines[i + 1]):
            table_lines = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            output.append(_parse_table(table_lines))
            continue

        # --- Empty line ---
        if line.strip() == "":
            i += 1
            continue

        # --- Paragraph (collect consecutive non-empty lines) ---
        para_lines = []
        while i < len(lines) and lines[i].strip() != "":
            # Break if next line is a special block
            if re.match(r"^(#{1,6}\s|```|~~~|>|\*{3,}|-{3,}|_{3,}|[\*\-\+]\s|\d+\.\s)", lines[i]) and para_lines:
                break
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            # Join lines with placeholder, escape inline content, then convert placeholder to <br>
            content = _inline("\x00BR\x00\n".join(para_lines))
            content = content.replace("\x00BR\x00", "<br>")
            output.append(f"<p>{content}</p>")

    return "\n".join(output)


def _inline(text: str) -> str:
    """Convert inline Markdown to HTML."""
    # Step 1: Extract inline code spans FIRST (protect from escaping)
    code_spans = []
    def _save_code(m):
        code_spans.append(html_module.escape(m.group(1)))
        return f'\x00CODE{len(code_spans) - 1}\x00'
    text = re.sub(r"`([^`]+)`", _save_code, text)

    # Step 2: Escape HTML entities in remaining text
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')

    # Step 3: Apply Markdown formatting
    # Images: ![alt](src)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', text)
    # Links: [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Bold + Italic: ***text*** or ___text___
    text = re.sub(r"\*{3}(.+?)\*{3}", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"<strong><em>\1</em></strong>", text)
    # Bold: **text** or __text__
    text = re.sub(r"\*{2}(.+?)\*{2}", r"<strong>\1</strong>", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"<strong>\1</strong>", text)
    # Italic: *text* or _text_
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", text)

    # Step 4: Restore inline code spans
    for i, code in enumerate(code_spans):
        text = text.replace(f'\x00CODE{i}\x00', f'<code>{code}</code>')
    return text


def _parse_table(lines: list[str]) -> str:
    """Parse a Markdown table into HTML."""
    def split_row(line: str) -> list[str]:
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        return [cell.strip() for cell in line.split("|")]

    if len(lines) < 2:
        return ""

    headers = split_row(lines[0])
    # Skip separator line (lines[1])
    rows = [split_row(line) for line in lines[2:]]

    html_parts = ["<table>", "<thead>", "<tr>"]
    for h in headers:
        html_parts.append(f"<th>{_inline(h)}</th>")
    html_parts.extend(["</tr>", "</thead>", "<tbody>"])

    for row in rows:
        html_parts.append("<tr>")
        for cell in row:
            html_parts.append(f"<td>{_inline(cell)}</td>")
        html_parts.append("</tr>")

    html_parts.extend(["</tbody>", "</table>"])
    return "\n".join(html_parts)


# ============================================================
# Template & Site Generator
# ============================================================

FALLBACK_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{title}} — 橋本 空輝</title>
  <link rel="stylesheet" href="{{asset_prefix}}/assets/css/style.css">
  <link rel="icon" href="{{asset_prefix}}/assets/images/favicon.svg" type="image/svg+xml">
</head>
<body>
  <nav class="nav">
    <div class="nav__inner">
      <a href="{{asset_prefix}}/index.html" class="nav__logo">S. Hashimoto</a>
      <button class="nav__toggle" aria-label="メニュー" aria-expanded="false">
        <span></span>
        <span></span>
        <span></span>
      </button>
      <ul class="nav__links">
        <li><a href="{{asset_prefix}}/index.html" class="nav__link">ホーム</a></li>
        <li><a href="{{asset_prefix}}/works.html" class="nav__link">実績</a></li>
        <li><a href="{{asset_prefix}}/research.html" class="nav__link">研究</a></li>
      </ul>
    </div>
  </nav>
  <article class="container">
    <header class="article-header">
      <div class="article-header__date">{{date}}</div>
      <h1 class="article-header__title">{{title}}</h1>
    </header>
    {{embeds}}
    <div class="article-content">
      {{content}}
    </div>
  </article>
  <footer class="footer" style="margin-top: var(--space-section);">
    <div class="container">
      <p>&copy; 2025 橋本 空輝. All rights reserved.</p>
    </div>
  </footer>
  <script src="{{asset_prefix}}/assets/js/main.js"></script>
  <script type="module">
    if (document.querySelector('.mermaid')) {
      import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs')
        .then(function (mod) {
          mod.default.initialize({
            startOnLoad: false,
            theme: 'default',
            fontFamily: '"Inter", "Noto Sans JP", sans-serif'
          });
          mod.default.run({ querySelector: '.mermaid' }).then(function() {
            // Add click-to-zoom functionality to mermaid diagrams
            document.querySelectorAll('.mermaid').forEach(function(el) {
              el.style.cursor = 'zoom-in';
              el.title = 'クリックして拡大';
              el.addEventListener('click', function() {
                const svg = el.querySelector('svg');
                if (!svg) return;
                
                // Create modal
                const modal = document.createElement('div');
                modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:10000;display:flex;align-items:center;justify-content:center;cursor:zoom-out;';
                
                // Clone SVG for modal
                const clonedSvg = svg.cloneNode(true);
                clonedSvg.style.cssText = 'max-width:95%;max-height:95%;background:white;border-radius:8px;';
                
                modal.appendChild(clonedSvg);
                document.body.appendChild(modal);
                
                // Close on click
                modal.addEventListener('click', function() {
                  document.body.removeChild(modal);
                });
                
                // Close on Escape key
                const closeOnEscape = function(e) {
                  if (e.key === 'Escape') {
                    document.body.removeChild(modal);
                    document.removeEventListener('keydown', closeOnEscape);
                  }
                };
                document.addEventListener('keydown', closeOnEscape);
              });
            });
          });
        });
    }
  </script>
</body>
</html>
"""


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Parse YAML-like front matter from markdown text."""
    meta = {}
    content = text

    pattern = r"^---\s*\n(.*?)\n---\s*\n"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        raw = match.group(1)
        content = text[match.end():]
        for line in raw.strip().split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()

    return meta, content


def compute_asset_prefix(output_path: str, project_root: str) -> str:
    """Compute relative path from output HTML to project root."""
    output_dir = os.path.dirname(os.path.abspath(output_path))
    root = os.path.abspath(project_root)
    rel = os.path.relpath(root, output_dir)
    return rel.replace("\\", "/")


def load_template(project_root: str, template_name: str = "post.html") -> str:
    """Load template from templates/ directory, falling back to built-in."""
    template_path = os.path.join(project_root, "templates", template_name)
    if os.path.isfile(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    print(f"  テンプレート {template_path} が見つかりません。内蔵テンプレートを使用します。")
    return FALLBACK_TEMPLATE


def extract_youtube_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    # https://www.youtube.com/watch?v=VIDEO_ID
    # https://youtu.be/VIDEO_ID
    # https://www.youtube.com/embed/VIDEO_ID
    # https://www.youtube.com/shorts/VIDEO_ID
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',  # Direct video ID
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def generate_embeds(meta: dict) -> str:
    """Generate HTML embed blocks for PDF, slides, and YouTube from front matter."""
    parts = []

    # YouTube videos (single or multiple)
    youtube_entries = []
    # Check for 'youtube' field (comma-separated or single)
    if "youtube" in meta and meta["youtube"]:
        youtube_entries.extend([url.strip() for url in meta["youtube"].split(",") if url.strip()])
    # Check for numbered youtube fields (youtube1, youtube2, ...)
    for key in sorted(meta.keys()):
        if key.startswith("youtube") and key != "youtube" and meta[key]:
            youtube_entries.extend([url.strip() for url in meta[key].split(",") if url.strip()])
    
    for i, youtube_url in enumerate(youtube_entries):
        video_id = extract_youtube_id(youtube_url)
        if video_id:
            label = "YouTube動画" if i == 0 else f"YouTube動画 ({i + 1})"
            parts.append(f"""\
    <div class="embed-container" style="margin-top: var(--space-l);">
      <div class="embed-label" style="padding: var(--space-s) var(--space-s) 0;">{label}</div>
      <iframe src="https://www.youtube.com/embed/{video_id}" width="100%" height="540" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
    </div>""")

    if "pdf" in meta and meta["pdf"]:
        pdf_path = meta["pdf"]
        parts.append(f"""\
    <div class="embed-container" style="margin-top: var(--space-l);">
      <div class="embed-label" style="padding: var(--space-s) var(--space-s) 0;">論文 PDF</div>
      <object data="{pdf_path}" type="application/pdf" width="100%" height="720">
        <p class="embed-fallback">
          PDFを表示できません。<a href="{pdf_path}">PDFをダウンロード</a>してください。
        </p>
      </object>
    </div>""")

    if "slides" in meta and meta["slides"]:
        slides_url = meta["slides"]
        parts.append(f"""\
    <div class="embed-container" style="margin-top: var(--space-l);">
      <div class="embed-label" style="padding: var(--space-s) var(--space-s) 0;">発表スライド</div>
      <iframe src="{slides_url}" width="100%" height="540" allowfullscreen></iframe>
    </div>""")

    return "\n".join(parts)


def convert(input_path: str, output_dir: str | None, content_type: str, project_root: str) -> str:
    """Convert a Markdown file to a styled HTML page."""
    with open(input_path, "r", encoding="utf-8") as f:
        raw = f.read()

    meta, md_content = parse_front_matter(raw)

    title = meta.get("title", Path(input_path).stem.replace("-", " ").title())
    date_str = meta.get("date", str(date.today()))
    slug = meta.get("slug", Path(input_path).stem)

    if output_dir is None:
        if content_type == "research":
            output_dir = os.path.join(project_root, "research", slug)
        elif content_type == "page":
            output_dir = os.path.join(project_root, "pages", slug)
        else:
            output_dir = os.path.join(project_root, "posts", slug)

    os.makedirs(output_dir, exist_ok=True)

    # Copy non-MD assets (PDF, images, etc.) from source directory to output
    source_dir = os.path.dirname(os.path.abspath(input_path))
    ASSET_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.mp4', '.webm', '.zip'}
    for item in os.listdir(source_dir):
        item_path = os.path.join(source_dir, item)
        if os.path.isfile(item_path) and Path(item).suffix.lower() in ASSET_EXTENSIONS:
            dest_path = os.path.join(output_dir, item)
            if not os.path.exists(dest_path) or os.path.getmtime(item_path) > os.path.getmtime(dest_path):
                shutil.copy2(item_path, dest_path)
                print(f"  Copied asset: {item}")
    output_path = os.path.join(output_dir, "index.html")

    html_content = md_to_html(md_content)
    embeds = generate_embeds(meta)
    asset_prefix = compute_asset_prefix(output_path, project_root)

    template = load_template(project_root)

    if "{{embeds}}" not in template:
        template = template.replace(
            "{{content}}\n    </div>",
            "{{content}}\n    </div>\n    {{embeds}}"
        )

    html_out = template.replace("{{title}}", title)
    html_out = html_out.replace("{{date}}", date_str)
    html_out = html_out.replace("{{content}}", html_content)
    html_out = html_out.replace("{{asset_prefix}}", asset_prefix)
    html_out = html_out.replace("{{embeds}}", embeds)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    return output_path


def _generate_card_html(article: dict, index: int, card_type: str) -> str:
    """Generate a single card HTML for listing pages."""
    delay_class = f" reveal-delay-{index % 3}" if index % 3 else ""
    date_html = f'<span class="card__date">{article["date"]}</span>' if article["date"] else ""
    desc = article.get("description", "")
    desc_html = f'<p class="card__description">{desc}</p>' if desc else ""

    if card_type == "research":
        item_class = "research-item"
    else:
        item_class = "research-item works-item"

    meta_html = article["date"]
    return (
        f'      <div class="{item_class} reveal{delay_class}">\n'
        f'        <a href="{article["url"]}" style="text-decoration:none;color:inherit;">\n'
        f'          <h2 class="research-item__title">{article["title"]}</h2>\n'
        f'          <div class="research-item__meta">{meta_html}</div>\n'
        + (f'          <p class="research-item__description">{desc}</p>\n' if desc else '')
        + f'        </a>\n'
        f'      </div>'
    )


def update_listing_page(html_path: str, articles: list[dict], card_type: str,
                        marker_name: str = "AUTO_GENERATED_CARDS",
                        max_items: int | None = None) -> None:
    """Replace content between <!-- {marker_name} --> and <!-- /{marker_name} --> markers."""
    if not os.path.isfile(html_path):
        print(f"  ⚠️  一覧ページが見つかりません: {html_path}")
        return

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    start_marker = f"<!-- {marker_name} -->"
    end_marker = f"<!-- /{marker_name} -->"
    if start_marker not in html or end_marker not in html:
        print(f"  ⚠️  マーカーが見つかりません: {html_path} ({marker_name})")
        return

    # Sort by date descending
    sorted_articles = sorted(articles, key=lambda a: a.get("date", ""), reverse=True)
    if max_items is not None:
        sorted_articles = sorted_articles[:max_items]

    if sorted_articles:
        cards = "\n\n".join(
            _generate_card_html(a, i, card_type)
            for i, a in enumerate(sorted_articles)
        )
        inner = f"\n{cards}\n"
    else:
        inner = "\n"

    # Replace everything between the two markers (exclusive)
    pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
    replacement = f"{start_marker}{inner}{end_marker}"
    html = re.sub(pattern, replacement, html, count=1, flags=re.DOTALL)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"📝 一覧ページ更新: {html_path} [{marker_name}] ({len(sorted_articles)} 件)")

def detect_content_type(input_path: str) -> str:
    """Detect content type from file path (posts/, research/, or pages/)."""
    parts = Path(input_path).parts
    for p in parts:
        if p == "research":
            return "research"
        if p == "pages":
            return "page"
    return "post"


def convert_all(project_root: str) -> list[str]:
    """Convert all Markdown files under content/ directory.
    Also updates listing pages (works.html, research.html) with article cards.
    """
    content_dir = os.path.join(project_root, "content")
    if not os.path.isdir(content_dir):
        print(f"Error: content/ ディレクトリが見つかりません: {content_dir}")
        sys.exit(1)

    md_files = sorted(Path(content_dir).rglob("*.md"))
    if not md_files:
        print("content/ 内に .md ファイルがありません。")
        return []

    results = []
    articles: list[dict] = []
    for md_path in md_files:
        md_str = str(md_path)
        content_type = detect_content_type(md_str)
        print(f"📄 変換中: {md_str} (type: {content_type})")
        output_path = convert(
            input_path=md_str,
            output_dir=None,
            content_type=content_type,
            project_root=project_root
        )
        print(f"   ✅ → {output_path}")
        results.append(output_path)

        # Collect metadata for listing pages (skip 'page' type — unlisted)
        if content_type == "page":
            continue
        with open(md_str, "r", encoding="utf-8") as f:
            meta, _ = parse_front_matter(f.read())
        slug = meta.get("slug", Path(md_str).stem)
        rel_url = f"research/{slug}/index.html" if content_type == "research" else f"posts/{slug}/index.html"
        articles.append({
            "title": meta.get("title", Path(md_str).stem.replace("-", " ").title()),
            "date": meta.get("date", ""),
            "description": meta.get("description", ""),
            "type": content_type,
            "url": rel_url,
        })

    # Update listing pages
    update_listing_page(
        os.path.join(project_root, "works.html"),
        [a for a in articles if a["type"] == "post"],
        "post"
    )
    update_listing_page(
        os.path.join(project_root, "research.html"),
        [a for a in articles if a["type"] == "research"],
        "research"
    )

    # Update index.html home page cards (latest 3 each)
    index_path = os.path.join(project_root, "index.html")
    update_listing_page(
        index_path,
        [a for a in articles if a["type"] == "post"],
        "post",
        marker_name="HOME_WORKS_CARDS",
        max_items=3
    )
    update_listing_page(
        index_path,
        [a for a in articles if a["type"] == "research"],
        "research",
        marker_name="HOME_RESEARCH_CARDS",
        max_items=3
    )

    return results


def resolve_project_root(args_root: str | None) -> str:
    """Resolve project root directory."""
    if args_root:
        return args_root
    candidate = Path(__file__).resolve().parent.parent
    if (candidate / "assets" / "css" / "style.css").is_file():
        return str(candidate)
    return os.getcwd()


def main():
    parser = argparse.ArgumentParser(
        description="Markdown → HTML 変換ツール（ポートフォリオサイト用）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python tools/md2html.py content/posts/my-article.md
  python tools/md2html.py content/research/vr-study.md --type research
  python tools/md2html.py --all                          # content/ 配下を一括変換

Markdownファイルの先頭にフロントマターを記述できます:
  ---
  title: 記事タイトル
  date: 2025-01-01
  slug: my-article
  pdf: paper.pdf
  slides: https://docs.google.com/presentation/d/e/XXXX/embed
  ---
        """
    )
    parser.add_argument("input", nargs="?", help="入力Markdownファイルのパス")
    parser.add_argument("--all", "-a", action="store_true", help="content/ 配下の全MDを一括変換")
    parser.add_argument("--output", "-o", help="出力ディレクトリ（省略時は自動決定）")
    parser.add_argument(
        "--type", "-t",
        choices=["post", "research", "page"],
        default=None,
        help="コンテンツタイプ (省略時はパスから自動判定)"
    )
    parser.add_argument(
        "--root", "-r",
        help="プロジェクトルートのパス（省略時は自動検出）"
    )

    args = parser.parse_args()
    project_root = resolve_project_root(args.root)
    print(f"📁 プロジェクトルート: {project_root}")

    # --all mode: convert everything under content/
    if args.all:
        results = convert_all(project_root)
        print(f"\n🎉 {len(results)} 件のファイルを変換しました。")
        return

    # Single file mode
    if not args.input:
        parser.error("入力ファイルを指定するか、--all で一括変換してください。")

    if not os.path.isfile(args.input):
        print(f"Error: ファイルが見つかりません: {args.input}")
        sys.exit(1)

    content_type = args.type or detect_content_type(args.input)
    print(f"📄 変換中: {args.input} (type: {content_type})")

    output_path = convert(
        input_path=args.input,
        output_dir=args.output,
        content_type=content_type,
        project_root=project_root
    )

    print(f"✅ 生成完了: {output_path}")
    rel = os.path.relpath(output_path, project_root)
    print(f"🌐 URL: https://{{username}}.github.io/{{repo}}/{rel.replace(os.sep, '/')}")


if __name__ == "__main__":
    main()
