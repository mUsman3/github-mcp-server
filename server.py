import os
import httpx
from mcp.server.fastmcp import FastMCP

# --- Configuration ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# --- Initialize MCP Server ---
mcp = FastMCP("GitHub DevOps")


def _check_token():
    """Validate that GitHub token is configured."""
    if not GITHUB_TOKEN:
        return "❌ GITHUB_TOKEN environment variable is not set. Please export it and restart the server."
    return None


async def _github_get(path: str, params: dict = None) -> dict | list | str:
    """Make an authenticated GET request to the GitHub API."""
    token_error = _check_token()
    if token_error:
        return token_error

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}{path}",
            headers=HEADERS,
            params=params or {},
            timeout=15.0,
        )
        if resp.status_code == 401:
            return "❌ Authentication failed. Check your GITHUB_TOKEN."
        if resp.status_code == 404:
            return f"❌ Not found: {path}"
        if resp.status_code != 200:
            return f"❌ GitHub API error {resp.status_code}: {resp.text[:200]}"
        return resp.json()


# ──────────────────────────────────────────────
# Tool 1: List Repositories
# ──────────────────────────────────────────────
@mcp.tool()
async def list_repos(
    owner: str = "",
    sort: str = "updated",
    limit: int = 10,
) -> str:
    """
    List GitHub repositories for a user or the authenticated user.

    Args:
        owner: GitHub username (leave empty for your own repos)
        sort: Sort by 'updated', 'created', 'pushed', or 'full_name'
        limit: Number of repos to return (max 30)
    """
    if owner:
        data = await _github_get(f"/users/{owner}/repos", {"sort": sort, "per_page": min(limit, 30)})
    else:
        data = await _github_get("/user/repos", {"sort": sort, "per_page": min(limit, 30), "affiliation": "owner"})

    if isinstance(data, str):
        return data

    lines = [f"📦 Repositories (showing {len(data)}):\n"]
    for repo in data:
        visibility = "🔒 Private" if repo.get("private") else "🌐 Public"
        language = repo.get("language") or "N/A"
        stars = repo.get("stargazers_count", 0)
        updated = repo.get("updated_at", "")[:10]
        lines.append(
            f"  • {repo['full_name']} [{visibility}]\n"
            f"    Language: {language} | ⭐ {stars} | Updated: {updated}"
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Tool 2: Get Pull Requests
# ──────────────────────────────────────────────
@mcp.tool()
async def get_pull_requests(
    owner: str,
    repo: str,
    state: str = "open",
    limit: int = 10,
) -> str:
    """
    Get pull requests for a GitHub repository.

    Args:
        owner: Repository owner (username or org)
        repo: Repository name
        state: Filter by state — 'open', 'closed', or 'all'
        limit: Number of PRs to return (max 30)
    """
    data = await _github_get(
        f"/repos/{owner}/{repo}/pulls",
        {"state": state, "per_page": min(limit, 30)},
    )
    if isinstance(data, str):
        return data

    if not data:
        return f"No {state} pull requests found in {owner}/{repo}."

    lines = [f"🔀 Pull Requests in {owner}/{repo} (state: {state}):\n"]
    for pr in data:
        draft = " [DRAFT]" if pr.get("draft") else ""
        labels = ", ".join(l["name"] for l in pr.get("labels", [])) or "none"
        created = pr.get("created_at", "")[:10]
        lines.append(
            f"  • #{pr['number']}: {pr['title']}{draft}\n"
            f"    Author: {pr['user']['login']} | Labels: {labels} | Created: {created}"
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Tool 3: Get GitHub Actions Workflow Runs
# ──────────────────────────────────────────────
@mcp.tool()
async def get_workflow_runs(
    owner: str,
    repo: str,
    status: str = "",
    limit: int = 10,
) -> str:
    """
    Get recent GitHub Actions workflow runs (CI/CD pipeline status).

    Args:
        owner: Repository owner (username or org)
        repo: Repository name
        status: Filter by status — 'completed', 'in_progress', 'queued', 'failure', 'success', or '' for all
        limit: Number of runs to return (max 30)
    """
    params = {"per_page": min(limit, 30)}
    if status:
        params["status"] = status

    data = await _github_get(f"/repos/{owner}/{repo}/actions/runs", params)
    if isinstance(data, str):
        return data

    runs = data.get("workflow_runs", [])
    if not runs:
        return f"No workflow runs found in {owner}/{repo}."

    status_icons = {
        "success": "✅",
        "failure": "❌",
        "cancelled": "⚪",
        "in_progress": "🔄",
        "queued": "⏳",
    }

    lines = [f"⚙️ GitHub Actions — {owner}/{repo} (total: {data.get('total_count', '?')}):\n"]
    for run in runs:
        icon = status_icons.get(run.get("conclusion") or run.get("status"), "❓")
        branch = run.get("head_branch", "?")
        triggered = run.get("created_at", "")[:19].replace("T", " ")
        duration = ""
        if run.get("run_started_at") and run.get("updated_at"):
            # rough duration
            duration = f" | Updated: {run['updated_at'][:19].replace('T', ' ')}"

        lines.append(
            f"  {icon} {run['name']}\n"
            f"    Branch: {branch} | Trigger: {run.get('event', '?')} | {triggered}{duration}\n"
            f"    Commit: {run.get('head_commit', {}).get('message', 'N/A')[:60]}"
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Tool 4: Get Repository Security Alerts
# ──────────────────────────────────────────────
@mcp.tool()
async def get_repo_security(
    owner: str,
    repo: str,
    limit: int = 10,
) -> str:
    """
    Get Dependabot security vulnerability alerts for a repository.
    Requires the repo to have Dependabot alerts enabled.

    Args:
        owner: Repository owner (username or org)
        repo: Repository name
        limit: Number of alerts to return (max 30)
    """
    data = await _github_get(
        f"/repos/{owner}/{repo}/dependabot/alerts",
        {"per_page": min(limit, 30), "state": "open"},
    )
    if isinstance(data, str):
        return data

    if not data:
        return f"🛡️ No open Dependabot alerts in {owner}/{repo}. Looking good!"

    severity_icons = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }

    lines = [f"🛡️ Dependabot Alerts — {owner}/{repo} ({len(data)} open):\n"]
    for alert in data:
        vuln = alert.get("security_vulnerability", {})
        advisory = alert.get("security_advisory", {})
        severity = vuln.get("severity", "unknown")
        icon = severity_icons.get(severity, "⚪")
        package = vuln.get("package", {}).get("name", "unknown")
        created = alert.get("created_at", "")[:10]

        lines.append(
            f"  {icon} [{severity.upper()}] {advisory.get('summary', 'No summary')}\n"
            f"    Package: {package} | Created: {created}\n"
            f"    Fix: {vuln.get('first_patched_version', {}).get('identifier', 'No fix available yet')}"
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Tool 5: Get Repository Stats
# ──────────────────────────────────────────────
@mcp.tool()
async def get_repo_stats(
    owner: str,
    repo: str,
) -> str:
    """
    Get overview stats for a repository — languages, topics, branch protection, and recent activity.

    Args:
        owner: Repository owner (username or org)
        repo: Repository name
    """
    # Fetch repo info
    info = await _github_get(f"/repos/{owner}/{repo}")
    if isinstance(info, str):
        return info

    # Fetch languages
    languages = await _github_get(f"/repos/{owner}/{repo}/languages")
    lang_str = ", ".join(f"{k}: {v}" for k, v in languages.items()) if isinstance(languages, dict) else "N/A"

    # Fetch recent commits count
    commits = await _github_get(f"/repos/{owner}/{repo}/commits", {"per_page": 5})
    recent_commits = ""
    if isinstance(commits, list):
        recent_commits = "\n\n  📝 Recent commits:"
        for c in commits[:5]:
            msg = c.get("commit", {}).get("message", "").split("\n")[0][:60]
            author = c.get("commit", {}).get("author", {}).get("name", "?")
            date = c.get("commit", {}).get("author", {}).get("date", "")[:10]
            recent_commits += f"\n    • {date} | {author}: {msg}"

    topics = ", ".join(info.get("topics", [])) or "none"

    return (
        f"📊 Repository Stats — {info['full_name']}\n\n"
        f"  Description: {info.get('description') or 'N/A'}\n"
        f"  Default branch: {info.get('default_branch', 'N/A')}\n"
        f"  Visibility: {'Private' if info.get('private') else 'Public'}\n"
        f"  Stars: {info.get('stargazers_count', 0)} | Forks: {info.get('forks_count', 0)} | Open Issues: {info.get('open_issues_count', 0)}\n"
        f"  Topics: {topics}\n"
        f"  Languages: {lang_str}\n"
        f"  Created: {info.get('created_at', '')[:10]} | Last push: {info.get('pushed_at', '')[:10]}"
        f"{recent_commits}"
    )


# ──────────────────────────────────────────────
# Run the server
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Starting GitHub DevOps MCP Server...")
    print("   Tools: list_repos, get_pull_requests, get_workflow_runs, get_repo_security, get_repo_stats")
    mcp.run(transport="stdio")
