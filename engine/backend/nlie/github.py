"""Repository integration. Reading is free; anything that writes goes through an approval first.

Writes use a separate git worktree, so the user's checked-out files and current branch are never touched.
The token is read from the environment by git/gh themselves and is never logged or stored."""
from __future__ import annotations
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .security import redact_text

EXPECTED_DOCS = {
    "README.md": "Repository overview",
    "docs/research/README.md": "Research index",
    "docs/research/00-investigation-log.md": "Investigation log",
    "docs/research/12-evidence-register.md": "Evidence register",
    "docs/engine/README.md": "Engine overview and installation",
    "docs/engine/02-architecture.md": "Engine architecture",
    "LICENSE": "Licence",
    "CONTRIBUTING.md": "Contribution guide",
    ".gitignore": "Ignore rules",
}


class GitError(Exception):
    pass


def git(repo: str | Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=120)
    if check and r.returncode != 0:
        raise GitError(redact_text(f"git {' '.join(args[:2])} failed: {r.stderr.strip() or r.stdout.strip()}"))
    return r.stdout.strip()


def remote_slug(repo) -> str:
    url = re.sub(r"//[^@/]+@", "//", git(repo, "remote", "get-url", "origin", check=False))  # drop any embedded credentials
    m = re.search(r"github\.com[:/]+([^/]+/[^/.]+)", url)
    return m.group(1) if m else ""


def status(repo: str) -> dict:
    if not repo or not (Path(repo) / ".git").exists():
        return {"connected": False, "reason": "No local git repository at the configured path."}
    files = git(repo, "ls-files").splitlines()
    docs = [f for f in files if f.endswith(".md")]
    top = sorted({f.split("/")[0] + ("/" if "/" in f else "") for f in files})
    log_lines = git(repo, "log", "-8", "--pretty=%h|%ad|%s", "--date=short", check=False).splitlines()
    return {"connected": True, "slug": remote_slug(repo), "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD"), "head": git(repo, "rev-parse", "--short", "HEAD"),
            "dirty_files": len([l for l in git(repo, "status", "--porcelain").splitlines() if l]), "tracked_files": len(files), "top_level": top, "docs": docs,
            "has_product_code": any(f.split("/")[0] in ("src", "app", "apps", "packages", "game") for f in files),
            "recent_commits": [dict(zip(("sha", "date", "subject"), l.split("|", 2))) for l in log_lines],
            "gh_cli": bool(shutil.which("gh"))}


def doc_gaps(repo: str) -> list[dict]:
    out = []
    for path, what in EXPECTED_DOCS.items():
        p = Path(repo) / path
        if not p.exists():
            out.append({"path": path, "issue": "missing", "detail": f"{what} not found."})
        elif p.suffix == ".md" and len(p.read_text(encoding="utf-8", errors="replace").split()) < 40:
            out.append({"path": path, "issue": "thin", "detail": f"{what} has fewer than 40 words."})
    for md in (Path(repo) / "docs").rglob("*.md") if (Path(repo) / "docs").exists() else []:
        text = md.read_text(encoding="utf-8", errors="replace")
        for target in re.findall(r"\]\((?!https?:|#|mailto:)([^)#\s]+)", text):
            if not (md.parent / target).exists():
                out.append({"path": str(md.relative_to(repo)), "issue": "broken_link", "detail": f"Links to '{target}', which does not exist."})
    return out


def publish(repo: str, branch: str, files: dict[str, str], message: str, *, base: str = "", push: bool = False, open_pr: bool = False, pr_title: str = "", pr_body: str = "") -> dict:
    """Create `branch` from `base` (default: current HEAD) in a temporary worktree, write files, commit, optionally push and open a PR.
    Refuses to reuse an existing branch, and refuses paths that escape the repository."""
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,120}", branch) or ".." in branch:
        raise GitError("Invalid branch name.")
    if git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False):
        raise GitError(f"Branch '{branch}' already exists; not overwriting it.")
    base = base or git(repo, "rev-parse", "HEAD")
    tmp = Path(tempfile.mkdtemp(prefix="nlie-wt-"))
    result = {"branch": branch, "base": base[:12], "files": sorted(files), "pushed": False, "pr_url": ""}
    try:
        git(repo, "worktree", "add", "-b", branch, str(tmp), base)
        for rel, content in files.items():
            dest = (tmp / rel).resolve()
            if tmp.resolve() not in dest.parents:
                raise GitError(f"Path '{rel}' is outside the repository.")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        git(tmp, "add", "-A")
        if not git(tmp, "status", "--porcelain"):
            raise GitError("Nothing to commit: generated files are identical to the base.")
        git(tmp, "-c", "user.name=NLIE", "-c", "user.email=nlie@localhost", "commit", "-m", message)
        result["commit"] = git(tmp, "rev-parse", "--short", "HEAD")
        if push:
            git(tmp, "push", "-u", "origin", branch)
            result["pushed"] = True
        if open_pr:
            if not shutil.which("gh"):
                result["pr_error"] = "GitHub CLI (gh) is not installed; branch pushed but no pull request opened."
            else:
                r = subprocess.run(["gh", "pr", "create", "--head", branch, "--title", pr_title or message, "--body", pr_body or message], cwd=tmp, capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    result["pr_url"] = r.stdout.strip().splitlines()[-1]
                else:
                    result["pr_error"] = redact_text(r.stderr.strip())[:500]
    except Exception:
        git(repo, "worktree", "remove", "--force", str(tmp), check=False)
        if "commit" not in result:
            git(repo, "branch", "-D", branch, check=False)
        raise
    git(repo, "worktree", "remove", "--force", str(tmp), check=False)
    shutil.rmtree(tmp, ignore_errors=True)
    return result
