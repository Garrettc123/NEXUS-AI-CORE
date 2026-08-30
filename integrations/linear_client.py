"""
integrations/linear_client.py

Linear GraphQL API client for NEXUS-AI-CORE.
Credentials resolved via core.secrets (Vault-first).

Capabilities:
  - Issue creation, update, close
  - Project & team queries
  - Cycle management
  - Webhook signature validation
  - Automated sprint task creation from revenue events
"""

import hashlib
import hmac
import logging
from typing import Any, Optional

import httpx

from core.secrets import SecretKey, require_secret, get_secret

logger = logging.getLogger(__name__)

LINEAR_API = "https://api.linear.app/graphql"


class LinearClient:
    """Linear GraphQL API client."""

    def __init__(self):
        self._api_key = require_secret(SecretKey.LINEAR_API_KEY)
        self._team_id = get_secret(SecretKey.LINEAR_TEAM_ID)
        self._project_id = get_secret(SecretKey.LINEAR_PROJECT_ID)
        self._webhook_secret = get_secret(SecretKey.LINEAR_WEBHOOK_SECRET)
        self._headers = {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
        }
        logger.info("[Linear] Client initialised (team=%s)", self._team_id)

    def _gql(self, query: str, variables: dict | None = None) -> dict:
        r = httpx.post(
            LINEAR_API,
            headers=self._headers,
            json={"query": query, "variables": variables or {}},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    # ── Issues ─────────────────────────────────────────────────────────────

    def create_issue(
        self,
        title: str,
        description: str = "",
        priority: int = 2,
        team_id: str | None = None,
        project_id: str | None = None,
        label_ids: list[str] | None = None,
    ) -> dict:
        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success issue { id identifier title url }
          }
        }"""
        variables = {"input": {
            "title": title,
            "description": description,
            "priority": priority,
            "teamId": team_id or self._team_id,
        }}
        if project_id or self._project_id:
            variables["input"]["projectId"] = project_id or self._project_id
        if label_ids:
            variables["input"]["labelIds"] = label_ids
        result = self._gql(mutation, variables)
        issue = result.get("data", {}).get("issueCreate", {}).get("issue", {})
        logger.info("[Linear] Created issue %s: %s", issue.get("identifier"), title)
        return issue

    def update_issue(self, issue_id: str, state_id: str | None = None, priority: int | None = None) -> dict:
        mutation = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success issue { id identifier state { name } }
          }
        }"""
        inp: dict = {}
        if state_id:
            inp["stateId"] = state_id
        if priority is not None:
            inp["priority"] = priority
        return self._gql(mutation, {"id": issue_id, "input": inp})

    def get_team_issues(self, team_id: str | None = None) -> list:
        query = """
        query TeamIssues($teamId: String!) {
          team(id: $teamId) { issues { nodes { id identifier title priority state { name } } } }
        }"""
        result = self._gql(query, {"teamId": team_id or self._team_id})
        return result.get("data", {}).get("team", {}).get("issues", {}).get("nodes", [])

    # ── Webhooks ───────────────────────────────────────────────────────────

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        if not self._webhook_secret:
            return False
        expected = hmac.new(self._webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
