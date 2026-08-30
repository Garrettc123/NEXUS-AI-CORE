"""
integrations/github_client.py

GitHub REST + GraphQL client for NEXUS-AI-CORE.
Credentials resolved via core.secrets (Vault-first).

Capabilities:
  - Repo CRUD (create, list, update)
  - Issues & PRs (create, label, assign, close)
  - GitHub Actions workflow dispatch
  - Webhook signature validation
  - Org secret management (list)
"""

import hashlib
import hmac
import logging
from typing import Any, Optional

import httpx

from core.secrets import SecretKey, require_secret, get_secret

logger = logging.getLogger(__name__)

GH_API = "https://api.github.com"
GH_ORG = "Garrettc123"


class GitHubClient:
    """Authenticated GitHub API client."""

    def __init__(self):
        token = require_secret(SecretKey.GITHUB_TOKEN)
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._webhook_secret = get_secret(SecretKey.GITHUB_WEBHOOK_SECRET)
        logger.info("[GitHub] Client initialised (org=%s)", GH_ORG)

    # ── Repos ──────────────────────────────────────────────────────────────

    def list_repos(self, per_page: int = 100) -> list[dict]:
        repos, page = [], 1
        while True:
            r = httpx.get(
                f"{GH_API}/user/repos",
                headers=self._headers,
                params={"per_page": per_page, "page": page, "sort": "updated"},
                timeout=15,
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            repos.extend(batch)
            page += 1
        logger.info("[GitHub] Listed %d repos", len(repos))
        return repos

    def create_repo(self, name: str, private: bool = True, description: str = "") -> dict:
        r = httpx.post(
            f"{GH_API}/user/repos",
            headers=self._headers,
            json={"name": name, "private": private, "description": description, "auto_init": True},
            timeout=15,
        )
        r.raise_for_status()
        logger.info("[GitHub] Created repo %s", name)
        return r.json()

    # ── Issues ─────────────────────────────────────────────────────────────

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> dict:
        r = httpx.post(
            f"{GH_API}/repos/{GH_ORG}/{repo}/issues",
            headers=self._headers,
            json={"title": title, "body": body, "labels": labels or [], "assignees": assignees or []},
            timeout=15,
        )
        r.raise_for_status()
        logger.info("[GitHub] Created issue '%s' in %s", title, repo)
        return r.json()

    def close_issue(self, repo: str, issue_number: int) -> dict:
        r = httpx.patch(
            f"{GH_API}/repos/{GH_ORG}/{repo}/issues/{issue_number}",
            headers=self._headers,
            json={"state": "closed"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    # ── Actions ────────────────────────────────────────────────────────────

    def dispatch_workflow(self, repo: str, workflow_id: str, ref: str = "main", inputs: dict | None = None) -> bool:
        r = httpx.post(
            f"{GH_API}/repos/{GH_ORG}/{repo}/actions/workflows/{workflow_id}/dispatches",
            headers=self._headers,
            json={"ref": ref, "inputs": inputs or {}},
            timeout=15,
        )
        ok = r.status_code == 204
        logger.info("[GitHub] Dispatched %s/%s: %s", repo, workflow_id, "OK" if ok else r.text)
        return ok

    # ── Webhooks ───────────────────────────────────────────────────────────

    def verify_webhook(self, payload: bytes, signature_header: str) -> bool:
        if not self._webhook_secret:
            logger.warning("[GitHub] Webhook secret not configured")
            return False
        expected = "sha256=" + hmac.new(
            self._webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)
