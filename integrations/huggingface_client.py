"""HuggingFace integration — inference API, embeddings, deal scoring."""
import os
import httpx

HF_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN", "")
EMBED_MODEL = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
SCORE_MODEL = os.getenv("HF_SCORE_MODEL", "")
BASE_URL = "https://api-inference.huggingface.co/models"


def _hf_headers() -> dict:
    return {"Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json"}


async def embed_text(text: str) -> list[float]:
    """Return a float embedding vector for the given text."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{BASE_URL}/{EMBED_MODEL}",
            headers=_hf_headers(),
            json={"inputs": text},
        )
        r.raise_for_status()
        result = r.json()
        # API returns list[list[float]] for batched or list[float] for single
        return result[0] if isinstance(result[0], list) else result


async def score_deal(features: dict) -> float:
    """Run deal scoring model inference and return a 0-1 probability."""
    if not SCORE_MODEL:
        # Fallback heuristic scoring when no fine-tuned model is deployed
        score = 0.0
        score += min(features.get("company_size", 0) / 1000, 0.3)
        score += min(features.get("revenue", 0) / 1_000_000, 0.3)
        score += 0.2 if features.get("has_budget") else 0.0
        score += 0.2 if features.get("decision_maker") else 0.0
        return round(min(score, 1.0), 4)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{BASE_URL}/{SCORE_MODEL}",
            headers=_hf_headers(),
            json={"inputs": features},
        )
        r.raise_for_status()
        result = r.json()
        return float(result[0]["score"]) if isinstance(result, list) else float(result)


async def classify_intent(text: str) -> str:
    """Zero-shot classify a text string into a NEXUS intent label."""
    candidate_labels = ["revenue", "crm_update", "task_update",
                         "contract_update", "deal", "inventory", "default"]
    model = "facebook/bart-large-mnli"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{BASE_URL}/{model}",
            headers=_hf_headers(),
            json={"inputs": text, "parameters": {"candidate_labels": candidate_labels}},
        )
        r.raise_for_status()
        data = r.json()
        return data["labels"][0]
