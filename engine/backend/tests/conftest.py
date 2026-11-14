import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
REPO_ROOT = Path(__file__).resolve().parents[3]

SITE = {
    "/robots.txt": ("text/plain", "User-agent: *\nDisallow: /private/\n"),
    "/": ("text/html", """<html><head><title>Demo City</title></head><body>
        <header><nav><a href="/login">Log in</a><a href="/market">Market</a><a href="/private/admin">Admin</a><a href="https://other.example/x">Other</a></nav></header>
        <main><h1>Welcome to Demo City</h1><p>""" + "A small city simulation used for tests. " * 12 + """</p>
        <button>Start playing</button></main><footer>Demo</footer></body></html>"""),
    "/login": ("text/html", """<html><head><title>Log in</title></head><body><main><h1>Log in</h1>
        <form method="post" action="/session"><input name="username" required><input type="password" name="password" required>
        <button type="submit">Log in</button></form><p>""" + "Enter your details. " * 15 + "</p><a href='/'>Home</a></main></body></html>"),
    "/market": ("text/html", """<html><head><title>Market</title></head><body><main><h1>Market</h1>
        <form action="/market"><input type="search" name="q"><button type="submit">Search</button></form>
        <ul><li class="item">Rice</li><li class="item">Beans</li><li class="item">Yam</li></ul><p>""" + "Goods for sale. " * 15 + "</p><a href='/flaky'>Deals</a></main></body></html>"),
}


class FakeSite(httpx.BaseTransport):
    def __init__(self):
        self.hits = []
        self.flaky_failures = 0  # number of 503s to serve on /flaky before succeeding
        self.down = False

    def handle_request(self, request):
        path = request.url.path
        self.hits.append(path)
        if self.down and path != "/robots.txt":
            raise httpx.ConnectError("connection refused", request=request)
        if path == "/flaky":
            if self.flaky_failures > 0:
                self.flaky_failures -= 1
                return httpx.Response(503, text="busy")
            return httpx.Response(200, headers={"content-type": "text/html"}, text="<html><title>Deals</title><body><h1>Deals</h1><p>" + "Deal. " * 60 + "</p></body></html>")
        if path in SITE:
            ctype, body = SITE[path]
            return httpx.Response(200, headers={"content-type": ctype}, text=body)
        return httpx.Response(404, headers={"content-type": "text/html"}, text="<html><title>Not found</title><body>404 not found</body></html>")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NLIE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("NLIE_WORKER", "0")
    monkeypatch.setenv("NLIE_DEFAULT_ENGINE", "http")  # pipeline tests use the in-memory site even where real browsers are installed
    for k in ("NLIE_DATABASE_URL", "NLIE_AI_BASE_URL", "NLIE_AI_MODEL_SIMPLE"):
        monkeypatch.delenv(k, raising=False)
    from nlie import config, db, jobs, permissions
    from nlie.browser import registry
    from nlie.browser.http_adapter import HttpAdapter
    config.reset_settings()
    db._engine = db._Session = None
    db.init_db()
    site = FakeSite()
    permissions.transport = site
    permissions.clear_cache()
    registry.register("http", lambda: HttpAdapter(transport=site))
    jobs._backoff_scale = 0
    jobs._last_fetch.clear()
    yield site
    permissions.transport = None
    registry.register("http", HttpAdapter)
    if db._engine is not None:
        db._engine.dispose()
    db._engine = db._Session = None
    config.reset_settings()


@pytest.fixture()
def project(env):
    from nlie.db import Project, Source, session
    with session() as s:
        p = Project(name="Demo", objective="Document Demo City")
        s.add(p)
        s.flush()
        s.add(Source(project_id=p.id, name="Demo City", base_url="https://demo.test/", automation="automated", approved=True, rate_limit_seconds=0, max_pages=10))
        return p.id


@pytest.fixture()
def git_repo(tmp_path):
    """A throwaway repository with a local bare 'origin', so branch/commit/push are exercised without touching GitHub."""
    origin, repo = tmp_path / "origin.git", tmp_path / "repo"
    run = lambda *a, cwd=None: subprocess.run(a, cwd=cwd, check=True, capture_output=True)  # noqa: E731
    run("git", "init", "--bare", "-b", "main", str(origin))
    run("git", "init", "-b", "main", str(repo))
    (repo / "README.md").write_text("# Demo\n")
    run("git", "add", "-A", cwd=repo)
    run("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init", cwd=repo)
    run("git", "remote", "add", "origin", str(origin), cwd=repo)
    run("git", "push", "-u", "origin", "main", cwd=repo)
    return repo, origin
