"""Page understanding engine tests (fixture HTML, no network)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import REPO_ROOT  # noqa: F401

from app.engine.page_understanding import analyze_html

FIXTURE = """
<html>
<head>
  <title>Acme Market — Buy and sell</title>
  <meta name="description" content="The Acme marketplace for local goods">
</head>
<body>
  <header><h1>Acme Market</h1><p>Buy and sell local goods</p></header>
  <nav class="main-nav">
    <a href="/">Home</a>
    <a href="/listings">Listings</a>
    <a href="/sellers">Sellers</a>
    <a href="https://external.example.com/docs">External Docs</a>
  </nav>
  <main>
    <section id="search">
      <h2>Find a listing</h2>
      <form action="/api/search" method="get">
        <input type="text" name="q" placeholder="Search listings" required>
        <select name="category"><option>Food</option><option>Services</option></select>
        <button type="submit">Search</button>
      </form>
    </section>
    <section id="results">
      <h2>Latest listings</h2>
      <div class="card">Item one</div>
      <div class="card">Item two</div>
      <div class="card">Item three</div>
      <div class="card">Item four</div>
    </section>
  </main>
  <footer><p>© Acme</p><a href="/privacy">Privacy</a></footer>
</body>
</html>
"""


def test_title_and_category():
    r = analyze_html(FIXTURE, url="https://acme.example.com/")
    assert r["title"] == "Acme Market — Buy and sell"
    assert r["content_category"] in ("content", "form", "landing")


def test_regions_and_nav():
    r = analyze_html(FIXTURE, url="https://acme.example.com/")
    assert "header" in r["regions"]
    assert "main" in r["regions"]
    nav_texts = [n.get("href") for n in r["navigation"]]
    assert "/listings" in nav_texts


def test_forms_and_controls():
    r = analyze_html(FIXTURE, url="https://acme.example.com/")
    assert len(r["forms"]) == 1
    f = r["forms"][0]
    assert f["action"] == "/api/search"
    names = [x["name"] for x in f["fields"]]
    assert "q" in names and "category" in names


def test_links_split():
    r = analyze_html(FIXTURE, url="https://acme.example.com/")
    ext = [l["href"] for l in r["links"]["external"]]
    assert any("external.example.com" in e for e in ext)
    assert len(r["links"]["internal"]) >= 3


def test_repeated_components():
    r = analyze_html(FIXTURE, url="https://acme.example.com/")
    reps = r["repeated_components"]
    assert any(rc["class"] == "card" and rc["count"] >= 4 for rc in reps)


def test_sections_outline():
    r = analyze_html(FIXTURE, url="https://acme.example.com/")
    texts = [s["text"] for s in r["sections"]]
    assert "Find a listing" in texts and "Latest listings" in texts


def test_error_state_detection():
    html = "<html><body><h1>404 — Page not found</h1><p>The road no dey.</p></body></html>"
    r = analyze_html(html, url="https://x.test/nope")
    assert r["states"]["error"] is True


def test_empty_state_detection():
    r = analyze_html("<html><body></body></html>", url="https://x.test/empty")
    assert r["states"]["empty"] is True


def test_malformed_html_does_not_crash():
    r = analyze_html("<html><body><div><p>unclosed", url="https://x.test/")
    assert isinstance(r["regions"], dict)
