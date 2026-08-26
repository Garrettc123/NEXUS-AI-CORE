"""Linear integration — execution ledger, task creation and updates."""
import os
import httpx

LINEAR_API = "https://api.linear.app/graphql"
TEAM_ID = os.getenv("LINEAR_TEAM_ID", "")


def _headers() -> dict:
    return {"Authorization": os.getenv("LINEAR_API_KEY", ""),
            "Content-Type": "application/json"}


async def create_issue(title: str, description: str = "",
                       priority: int = 2, label: str | None = None) -> dict:
    """Create a Linear issue and return its id and url."""
    query = """
    mutation CreateIssue($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier title url }
      }
    }
    """
    variables = {
        "input": {
            "teamId": TEAM_ID,
            "title": title,
            "description": description,
            "priority": priority,
        }
    }
    async with httpx.AsyncClient() as c:
        r = await c.post(LINEAR_API, json={"query": query, "variables": variables},
                         headers=_headers())
        r.raise_for_status()
        data = r.json()
        issue = data["data"]["issueCreate"]["issue"]
        return {"id": issue["id"], "identifier": issue["identifier"],
                "title": issue["title"], "url": issue["url"]}


async def update_issue_status(issue_id: str, state_name: str) -> dict:
    # First resolve the state id
    state_query = """
    query States($teamId: String!) {
      team(id: $teamId) { states { nodes { id name } } }
    }
    """
    async with httpx.AsyncClient() as c:
        r = await c.post(LINEAR_API,
                         json={"query": state_query, "variables": {"teamId": TEAM_ID}},
                         headers=_headers())
        r.raise_for_status()
        states = r.json()["data"]["team"]["states"]["nodes"]
        state_id = next((s["id"] for s in states if s["name"].lower() == state_name.lower()), None)
        if not state_id:
            return {"error": f"State '{state_name}' not found"}

    mutation = """
    mutation UpdateIssue($id: String!, $stateId: String!) {
      issueUpdate(id: $id, input: { stateId: $stateId }) {
        success
        issue { id title url }
      }
    }
    """
    async with httpx.AsyncClient() as c:
        r = await c.post(LINEAR_API,
                         json={"query": mutation,
                               "variables": {"id": issue_id, "stateId": state_id}},
                         headers=_headers())
        r.raise_for_status()
        return r.json()["data"]["issueUpdate"]
