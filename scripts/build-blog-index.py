#!/usr/bin/env python3
"""Generate a static /blog/ directory from published website articles.
Runs inside the miaoon-website repository; no external Python packages required.
"""
from pathlib import Path
from html.parser import HTMLParser
from html import escape, unescape
import json, re, subprocess, datetime, os

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / 'blog'
SITE_URL = 'https://www.miaoon.in'

# Exclude ordinary website pages and utilities. Add any further exceptions to
# blog/catalog-exclude.txt (one path per line).
DEFAULT_EXCLUDE = set('''index.html blog/index.html blog-studio.html 404.html
agency-website-strategy.html analytics-optimization.html brand-strategy.html
content-strategy.html digital-marketing.html ecommerce-performance-marketing.html
paid-advertising.html web-development.html kessler-group.html meridian-foods.html
nordwind-apparel.html solstice-retail.html verve-analytics.html'''.split())

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ''; self.h1 = ''; self.description = ''; self.category = ''
        self.in_title = False; self.in_h1 = False
        self.has_article = False; self.article_head = False
        self.noindex = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = a.get('class','').split()
        if tag == 'title': self.in_title = True
        if tag == 'h1': self.in_h1 = True
        if tag == 'article': self.has_article = True
        if 'article-head' in classes: self.article_head = True
        if tag == 'meta':
            name = (a.get('name') or '').lower()
            if name == 'description': self.description = a.get('content','').strip()
            if name == 'robots' and 'noindex' in a.get('content','').lower(): self.noindex = True
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag == 'h1': self.in_h1 = False
    def handle_data(self, data):
        if self.in_title: self.title += data
        if self.in_h1: self.h1 += data

def git_date(path):
    try:
        x = subprocess.run(['git','log','-1','--format=%cs','--',str(path.relative_to(ROOT))],cwd=ROOT,capture_output=True,text=True,timeout=5)
        return x.stdout.strip() or ''
    except Exception:
        return ''

def read_lines(path):
    if not path.exists(): return set()
    return {x.strip().lstrip('/') for x in path.read_text(encoding='utf-8').splitlines() if x.strip() and not x.lstrip().startswith('#')}

def published_state():
    p = ROOT / 'seo-agent/state.json'
    if not p.exists(): return {}
    try:
        return {str(t.get('slug',''))+'.html':t for t in json.loads(p.read_text(encoding='utf-8')).get('posts',[]) if t.get('slug')}
    except (ValueError, OSError): return {}

def main():
    BLOG.mkdir(exist_ok=True)
    includes = read_lines(BLOG/'catalog-include.txt')
    excludes = DEFAULT_EXCLUDE | read_lines(BLOG/'catalog-exclude.txt')
    published = published_state()
    files = list(ROOT.glob('*.html')) + list((BLOG/'posts').glob('*.html')) if (BLOG/'posts').exists() else list(ROOT.glob('*.html'))
    pages=[]
    for file in sorted(files):
        rel=file.relative_to(ROOT).as_posix()
        if rel in excludes or file.name.startswith('.'): continue
        try: source=file.read_text(encoding='utf-8',errors='replace')
        except OSError: continue
        p=PageParser()
        try: p.feed(source)
        except Exception: continue
        if p.noindex: continue
        # Exclude demo/template pages and empty placeholders.
        if re.search(r'(?i)(template|sample|placeholder|post-1)\.html$',rel): continue
        likely_article = (rel.startswith('blog/posts/') or file.name.startswith('blog-')
                          or rel in published or p.article_head or (p.has_article and bool(p.h1)))
        if not (likely_article or rel in includes): continue
        title=re.sub(r'\s*[|–-]\s*Miaoon\s*$','',unescape((p.h1 or p.title).strip()),flags=re.I)
        title=' '.join(title.split())
        if not title or title.lower() in ('miaoon', 'untitled'): continue
        desc=' '.join(unescape(p.description).split())
        state=published.get(rel,{})
        date=(state.get('date') or '')[:10] or git_date(file)
        # Older undated posts sort after known dated posts, not with misleading dates.
        category=('AI & Automation' if re.search(r'(?i)(agentic|\bAI\b|automation|GaaS)',title)
                  else 'SEO & Search' if re.search(r'(?i)(SEO|search|generative engine|content)',title)
                  else 'Brand & Marketing' if re.search(r'(?i)(brand|marketing|campaign|ads|creative)',title)
                  else 'Insights')
        pages.append(dict(path=rel, title=title, description=desc, date=date, category=category))
    pages.sort(key=lambda p:(p['date'],p['path']),reverse=True)
    cards=[]
    for p in pages:
        url='/' + p['path']
        desc=escape(p['description'][:180]) if p['description'] else 'Explore the latest thinking from Miaoon.'
        date=escape(p['date']) if p['date'] else 'Insights'
        cards.append(f'''<article class="card" data-search="{escape((p['title']+' '+p['category']).lower(),quote=True)}" data-category="{escape(p['category'],quote=True)}">
          <div class="meta"><span>{escape(p['category'])}</span><time>{date}</time></div>
          <h2><a href="{escape(url,quote=True)}">{escape(p['title'])}</a></h2>
          <p>{desc}</p><a class="more" href="{escape(url,quote=True)}">Read article <span aria-hidden="true">↗</span></a>
        </article>''')
    html='''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Insights & Articles | Miaoon</title><meta name="description" content="Explore Miaoon insights on agentic AI, branding, SEO, digital marketing and creative strategy.">
<link rel="canonical" href="https://www.miaoon.in/blog/">
<style>
:root{--bg:#090909;--card:#171717;--ink:#f7f7f7;--muted:#b1b1b1;--accent:#ff5a43}*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Arial,Helvetica,sans-serif;line-height:1.6}
a{color:inherit}header{border-bottom:1px solid #333;padding:20px clamp(20px,5vw,75px);display:flex;justify-content:space-between;align-items:center}
.logo{font-size:24px;font-weight:900;letter-spacing:.12em;text-decoration:none}.logo span{color:var(--accent)}header nav a{text-decoration:none;color:#ddd;margin-left:20px}
.hero{padding:75px clamp(20px,5vw,75px) 38px;max-width:1100px}.eyebrow{font-weight:800;color:var(--accent);text-transform:uppercase;letter-spacing:.18em;font-size:12px}
h1{font-size:clamp(38px,6vw,76px);letter-spacing:-.045em;line-height:1.05;margin:16px 0}h1 em{font-style:normal;color:var(--accent)}.hero p{color:var(--muted);max-width:640px;font-size:18px}
main{padding:20px clamp(20px,5vw,75px) 90px}.toolbar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:10px 0 25px}
input{background:#171717;border:1px solid #444;color:white;border-radius:8px;padding:14px 16px;min-width:min(100%,340px);font-size:16px}
.count{color:var(--muted);font-size:14px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,310px),1fr));gap:20px}
.card{background:var(--card);border:1px solid #303030;border-radius:14px;padding:26px;display:flex;flex-direction:column;min-height:280px}
.card:hover{border-color:var(--accent)}.meta{display:flex;justify-content:space-between;gap:12px;color:var(--accent);font-size:11px;letter-spacing:.06em;text-transform:uppercase;font-weight:800}
.meta time{color:#a9a9a9}.card h2{font-size:22px;line-height:1.3;letter-spacing:-.02em;margin:22px 0 12px}.card h2 a{text-decoration:none}
.card p{color:var(--muted);font-size:14px;flex:1}.more{margin-top:20px;color:var(--accent);font-size:14px;font-weight:800;text-decoration:none}
footer{padding:30px clamp(20px,5vw,75px);border-top:1px solid #333;color:var(--muted)}#empty{display:none;color:var(--muted)}
</style></head><body>
<header><a class="logo" href="/">MIAOON<span>.</span></a><nav><a href="/">Home</a><a href="/blog/" aria-current="page">Insights</a></nav></header>
<section class="hero"><div class="eyebrow">Ideas that move business</div><h1>Insights<span style="color:var(--accent)">.</span><br><em>Built for what's next.</em></h1><p>Ideas, practical perspectives and future-facing thinking on AI, branding, marketing and growth.</p></section>
<main><div class="toolbar"><input id="search" type="search" aria-label="Search articles" placeholder="Search articles…"><span class="count" id="count">__COUNT__ published articles</span></div>
<div class="grid" id="articles">__CARDS__</div><p id="empty">No matching articles found.</p></main>
<footer>© Miaoon · <a href="/">Back to homepage</a></footer>
<script>const q=document.getElementById('search'),cards=[...document.querySelectorAll('.card')],count=document.getElementById('count');q.addEventListener('input',()=>{let n=0;for(const c of cards){const show=c.dataset.search.includes(q.value.toLowerCase().trim());c.hidden=!show;if(show)n++}count.textContent=n+' of '+cards.length+' articles';document.getElementById('empty').style.display=n?'none':'block'});</script>
</body></html>'''.replace('__COUNT__',str(len(pages))).replace('__CARDS__','\n'.join(cards))
    target=BLOG/'index.html'
    if not target.exists() or target.read_text(encoding='utf-8')!=html:
        target.write_text(html,encoding='utf-8')
    print(f'Generated blog/index.html with {len(pages)} articles from {len(files)} HTML files')
    print('Articles:', ', '.join(p['path'] for p in pages[:10]))

if __name__=='__main__': main()
