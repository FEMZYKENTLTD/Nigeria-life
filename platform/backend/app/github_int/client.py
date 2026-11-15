"""GitHub integration.

Two adapters:
* LocalRepoAdapter — operates on the local checkout with `git` (used when
  the workspace IS the repository, which is the normal research workflow here).
* RemoteRepoAdapter — reads remote repo state through `gh api` (read-only).

Security (directive §12):
* tokens are handled only by git/gh credential helpers; this module never
  logs or stores tokens;
* research files never contain credentials (sanitised on write);
* consequential writes (branches, commits to product areas, PRs) are gated
  behind an approved Decision by the agent loop / API layer.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone

log = logging.getLogger("rice.github")

_TOKEN_SCAN = re.compile(
    r"(?i)\b(ghp_|gho_|github_pat_|xox[baprs]-|sk-|Bearer\s+)[A-Za-z0-9_\-]{16,}"
)


def sanitize(text: str) -> str:
    """Never let credential-shaped strings land in research content."""
    return _TOKEN_SCAN.sub("[REDACTED-CREDENTIAL]", text or "")


class GitError(RuntimeError):
    pass


def _run(cmd: list[str], cwd: str | None = None, timeout: int = 60) -> str:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            raise GitError(f"{' '.join(cmd[:4])}… failed: {p.stderr.strip()[:300]}")
        return p.stdout
    except FileNotFoundError:
        raise GitError(f"command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise GitError(f"timeout: {' '.join(cmd[:4])}…")


class LocalRepoAdapter:
    """The repository is the local checkout (the central project knowledge
    base). All reads go through git; writes go through branches + commits and
    are only performed after an approved Decision."""

    def __init__(self, path: str) -> None:
        self.path = path

    def available(self) -> bool:
        return os.path.isdir(os.path.join(self.path, ".git"))

    def repo_info(self) -> dict:
        _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=self.path)
        branches = _run(["git", "branch", "--show-current"], cwd=self.path).strip() or "(detached)"
        try:
            remotes = _run(["git", "remote", "-v"], cwd=self.path).strip().splitlines()
            remote = remotes[0].split()[1] if remotes else ""
        except GitError:
            remote = ""
        try:
            head = _run(["git", "log", "-1", "--format=%H %ai %s"], cwd=self.path).strip().split(" ", 2)
            last_sha, last_date, last_msg = head[0], head[1], (head[2] if len(head) > 2 else "")
        except GitError:
            last_sha = last_date = last_msg = ""
        return {
            "mode": "local",
            "path": self.path,
            "remote": remote,
            "branch": branches,
            "last_commit_sha": last_sha,
            "last_commit_date": last_date,
            "last_commit_message": sanitize(last_msg),
        }

    def recent_commits(self, n: int = 15) -> list[dict]:
        out = _run(["git", "log", f"-{n}", "--format=%H|%ai|%an|%s"], cwd=self.path).strip().splitlines()
        rows = []
        for line in out:
            parts = line.split("|", 3)
            if len(parts) == 4:
                rows.append({"sha": parts[0], "date": parts[1], "author": parts[2],
                             "message": sanitize(parts[3])})
        return rows

    def branches(self) -> list[str]:
        out = _run(["git", "branch", "-a"], cwd=self.path).strip().splitlines()
        return [b.strip().lstrip("* ").strip() for b in out if b.strip()]

    def docs_tree(self, root: str = "docs") -> list[dict]:
        """Markdown documentation tree with sizes and mtimes."""
        rows = []
        base = os.path.join(self.path, root)
        if not os.path.isdir(base):
            return rows
        for dirpath, _dirnames, filenames in os.walk(base):
            for fn in sorted(filenames):
                if not fn.endswith(".md"):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, self.path)
                st = os.stat(full)
                rows.append({"path": rel, "size": st.st_size,
                             "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()})
        return rows

    def read_doc(self, path: str) -> str:
        full = os.path.join(self.path, path)
        if not os.path.isfile(full):
            raise GitError(f"not a file: {path}")
        with open(full, "r", encoding="utf-8") as f:
            return f.read()

    def write_back(self, path: str, content: str, commit_msg: str,
                   branch: str | None = None) -> dict:
        """Create (or use) a research branch, write the doc, commit.
        Must only be called after an approved Decision."""
        sanitize(content)
        target = os.path.join(self.path, path)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        _run(["git", "add", path], cwd=self.path)
        if branch:
            current = self.repo_info()["branch"]
            if current != branch:
                _run(["git", "checkout", "-b", branch], cwd=self.path)
        sha = _run(["git", "commit", "-m", commit_msg], cwd=self.path).strip()
        out = _run(["git", "rev-parse", "HEAD"], cwd=self.path).strip()
        return {"commit": out, "message": commit_msg, "path": path, "branch": self.repo_info()["branch"]}

    def create_pr(self, title: str, body: str, base: str = "main") -> dict:
        """Open a PR from the current branch (requires pushed branch)."""
        branch = self.repo_info()["branch"]
        _run(["git", "push", "origin", branch], cwd=self.path, timeout=120)
        body = sanitize(body)
        p = subprocess.run(
            ["gh", "pr", "create", "--title", title, "--body", body, "--base", base],
            cwd=self.path, capture_output=True, text=True, timeout=120,
        )
        if p.returncode != 0:
            # PR may already exist for this branch — that is a known state, not a crash
            if "already exists" in p.stderr or "already exists" in p.stdout:
                out = _run(["gh", "pr", "view", "--json", "url,number"], cwd=self.path)
                data = json.loads(out)
                return {"number": data.get("number"), "url": data.get("url"), "note": "PR already existed for branch"}
            raise GitError(f"gh pr create failed: {p.stderr.strip()[:300]}")
        out = _run(["gh", "pr", "view", "--json", "url,number"], cwd=self.path)
        data = json.loads(out)
        return {"number": data.get("number"), "url": data.get("url")}


class RemoteRepoAdapter:
    """Read-only remote inspection via gh api (used for repos that are not
    the local checkout)."""

    def __init__(self, full_name: str) -> None:
        self.full_name = full_name

    def available(self) -> bool:
        try:
            _run(["gh", "repo", "view", self.full_name, "--json", "nameWithOwner"], timeout=30)
            return True
        except GitError:
            return False

    def _api(self, path: str) -> list | dict:
        out = _run(["gh", "api", f"repos/{self.full_name}/{path}"], timeout=60)
        return json.loads(out)

    def repo_info(self) -> dict:
        data = self._api("")
        return {
            "mode": "remote",
            "remote": data.get("html_url", ""),
            "branch": data.get("default_branch", ""),
            "description": data.get("description") or "",
        }

    def recent_commits(self, n: int = 15) -> list[dict]:
        data = self._api(f"commits?per_page={n}")
        return [{"sha": c.get("sha", "")[:12],
                 "date": (c.get("commit", {}).get("committer") or {}).get("date", ""),
                 "author": ((c.get("commit", {}).get("author") or {}).get("name", "")),
                 "message": sanitize((c.get("commit", {}).get("message") or "").splitlines()[0])}
                for c in data]

    def docs_tree(self, root: str = "docs") -> list[dict]:
        try:
            data = self._api(f"git/trees/HEAD?recursive=1")
        except GitError:
            return []
        return [{"path": t.get("path", ""), "size": t.get("size") or 0}
                for t in data.get("tree", [])
                if str(t.get("path", "")).startswith(root) and str(t.get("path", "")).endswith(".md")]


def get_adapter(local_path: str | None = None, remote: str | None = None) -> LocalRepoAdapter | RemoteRepoAdapter | None:
    if local_path and os.path.isdir(os.path.join(local_path, ".git")):
        return LocalRepoAdapter(local_path)
    if remote:
        return RemoteRepoAdapter(remote)
    return None
