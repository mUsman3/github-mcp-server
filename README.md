# GitHub DevOps MCP Server

A lightweight [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that exposes GitHub DevOps tools to any MCP-compatible AI host — enabling natural language interaction with your repositories, CI/CD pipelines, pull requests, and security alerts.

## What is this?

Instead of switching between the GitHub UI, CLI, and dashboards, you ask your AI assistant plain questions:

```
"Show me failed CI runs in flask-k8s"
"Are there any open security vulnerabilities?"
"List my recent pull requests"
```

The AI decides which tool to call, your MCP server translates it to a GitHub API request, and the result comes back as a natural language response.

## Tools

| Tool | Description | Use case |
|------|-------------|----------|
| `list_repos` | List repositories for a user or the authenticated user | DevEx platform visibility |
| `get_pull_requests` | Get PRs by state (open, closed, all) | SDLC workflow monitoring |
| `get_workflow_runs` | Get GitHub Actions CI/CD pipeline runs | Pipeline status and debugging |
| `get_repo_security` | Get Dependabot vulnerability alerts | DevSecOps and compliance |
| `get_repo_stats` | Get repo overview — languages, commits, activity | Platform engineering metrics |

## Prerequisites

- Python 3.10+
- A GitHub Personal Access Token ([create one here](https://github.com/settings/tokens?type=beta))

### Token permissions (fine-grained, read-only)

- Actions: Read-only
- Contents: Read-only
- Dependabot alerts: Read-only
- Metadata: Read-only
- Pull requests: Read-only

## Quick start

```bash
git clone https://github.com/mUsman3/github-mcp-server.git
cd github-mcp-server

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export GITHUB_TOKEN="github_pat_YOUR_TOKEN_HERE"

# Test with MCP Inspector (opens browser UI)
mcp dev server.py
```

In the Inspector, set **Command** to your venv Python path and **Arguments** to `server.py`, then click Connect.

## Connecting to an AI host

### Option A: OpenWebUI + Ollama (fully local)

This approach keeps everything on your machine — no data leaves your device.

```bash
pip install mcpo
mcpo --port 8000 -- python3 server.py
```

Then in OpenWebUI:

1. Go to **Settings** → **Integrations**
2. Click **+** to add a tool server
3. Set URL to `http://host.docker.internal:8000` (Docker) or `http://localhost:8000` (native)
4. Save, start a new chat, type `#` to enable the tools, and ask away

Recommended models for tool calling: `qwen2.5:7b` or larger. Smaller models (3B) don't reliably understand tool schemas.

### Option B: Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "github-devops": {
      "command": "/path/to/venv/bin/python3",
      "args": ["/path/to/github-mcp-server/server.py"],
      "env": {
        "GITHUB_TOKEN": "github_pat_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

### Option C: Cursor IDE

Add to Cursor's MCP settings (`.cursor/mcp.json` in your project):

```json
{
  "mcpServers": {
    "github-devops": {
      "command": "/path/to/venv/bin/python3",
      "args": ["/path/to/github-mcp-server/server.py"],
      "env": {
        "GITHUB_TOKEN": "github_pat_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

## Architecture

```
Developer (natural language)
    │
    ▼
┌─────────────────────────────────┐
│  AI Host                        │
│  (OpenWebUI / Claude / Cursor)  │
│         │                       │
│         ▼                       │
│  LLM (decides which tool)       │
│         │                       │
│         ▼                       │
│  MCP Client                     │
└────────┬────────────────────────┘
         │ tool call (JSON)
         ▼
┌─────────────────────────────────┐
│  MCP Server (this repo)         │
│                                 │
│  ┌──────────┐ ┌──────────┐     │
│  │list_repos│ │ get_PRs  │     │
│  └──────────┘ └──────────┘     │
│  ┌──────────┐ ┌──────────┐     │
│  │ actions  │ │ security │     │
│  └──────────┘ └──────────┘     │
│  ┌──────────┐                  │
│  │  stats   │                  │
│  └──────────┘                  │
└────────┬────────────────────────┘
         │ REST API + auth token
         ▼
┌─────────────────────────────────┐
│  GitHub API                     │
│  (repos, actions, PRs, alerts)  │
└─────────────────────────────────┘
```

## Key design decisions

**Read-only by design.** All tools are read-only queries. No tool can create, modify, or delete anything. This is a deliberate governance choice — extending to write operations would require human-in-the-loop approval gates.

**Fine-grained token permissions.** The GitHub token uses the minimum permissions needed. In a production setup, you'd enforce per-team tokens scoped to specific repositories.

**Host-agnostic.** The MCP server uses stdio transport. The same `server.py` works with OpenWebUI, Claude Desktop, Cursor, or any MCP-compatible client — write once, connect anywhere.

**Extensible.** Adding a new tool takes ~20 lines of Python. Potential extensions:

- Jira/Linear for issue tracking
- PagerDuty for on-call and incident alerts
- SonarQube for code quality metrics
- AWS CloudWatch for observability data
- Slack for team notifications

## Adding a new tool

```python
@mcp.tool()
async def get_open_issues(owner: str, repo: str, limit: int = 10) -> str:
    """Get open issues for a repository."""
    data = await _github_get(
        f"/repos/{owner}/{repo}/issues",
        {"state": "open", "per_page": min(limit, 30)}
    )
    if isinstance(data, str):
        return data
    lines = [f"Open issues in {owner}/{repo}:\n"]
    for issue in data:
        lines.append(f"  - #{issue['number']}: {issue['title']}")
    return "\n".join(lines)
```

## License

MIT