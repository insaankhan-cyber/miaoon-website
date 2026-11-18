#!/usr/bin/env python3
"""Synchronize sitemap.xml from existing sitemap and published /blog/ article cards.
Run from the root of miaoon-website. Uses no external dependencies.
"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
from xml.etree import ElementTree as ET
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SITEMAP = ROOT / 'sitemap.xml'
INDEX = ROOT / 'blog' / 'index.html'
CANONICAL_HOST = 'www.miaoon.in'  # Align with /blog/ canonical URL
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
ET.register_namespace('', NS)

class ArticleLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_article = 0
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'article':
            self.in_article += 1
        if tag == 'a' and self.in_article and attrs.get('href'):
            self.hrefs.append(attrs['href'])
    def handle_endtag(self, tag):
        if tag == 'article' and self.in_article:
            self.in_article -= 1

def normalized_path(url):
    url = url.strip()
    if not url or url.startswith(('#', 'mailto:', 'javascript:')):
        return None
    p = urlsplit(url)
    if p.scheme and p.scheme not in ('http', 'https'):
        return None
    if p.netloc and p.hostname not in ('miaoon.in', 'www.miaoon.in'):
        return None
    path = unquote(p.path or '/')
    if not path.startswith('/'):
        path = '/' + path
    if '..' in Path(path).parts:
        return None
    if path.endswith('/index.html'):
        path = path[:-len("index.html")]
    if path != '/' and not (path.endswith('.html') or path.endswith('/')):
        return None
    return path

def main():
    if not INDEX.is_file() or not SITEMAP.is_file():
        sys.exit('Missing blog/index.html or sitemap.xml in repository root')

    parser = ArticleLinks()
    parser.feed(INDEX.read_text(encoding='utf-8'))
    article_paths = set()
    missing_files = []
    for href in parser.hrefs:
        path = normalized_path(href)
        if not path or not path.endswith('.html'):
            continue
        local_file = ROOT / path.lstrip('/')
        if not local_file.is_file():
            missing_files.append(path)
            continue
        html = local_file.read_text(encoding='utf-8', errors='replace')
        if re.search(r'<meta\b[^>]*name=["\']robots["\'][^>]*content=["\'][^"\']*noindex', html, re.I):
            continue
        article_paths.add(path)
    if missing_files:
        print('WARNING: directory links without matching files:', ', '.join(sorted(set(missing_files))))
    if len(article_paths) < 20:
        sys.exit(f'Only {len(article_paths)} local article URLs found; refusing to overwrite sitemap')

    root = ET.parse(SITEMAP).getroot()
    existing_paths = set()
    for elem in root.findall(f'.//{{{NS}}}loc'):
        if elem.text:
            path = normalized_path(elem.text)
            if path:
                existing_paths.add(path)
    all_paths = existing_paths | article_paths | {'/blog/', '/'}
    output = ET.Element(f'{{{NS}}}urlset')
    for path in sorted(all_paths, key=lambda p: (p != '/', p)):
        url = ET.SubElement(output, f'{{{NS}}}url')
        loc = ET.SubElement(url, f'{{{NS}}}loc')
        loc.text = f'https://{CANONICAL_HOST}{path}'
    ET.indent(output, space='  ')
    xml = ET.tostring(output, encoding='utf-8', xml_declaration=True)
    previous = SITEMAP.read_bytes()
    if xml != previous:
        SITEMAP.write_bytes(xml)
    print(f'Articles in directory: {len(article_paths)}; old sitemap URLs: {len(existing_paths)}; final sitemap URLs: {len(all_paths)}; changed: {xml != previous}')

if __name__ == '__main__':
    main()
