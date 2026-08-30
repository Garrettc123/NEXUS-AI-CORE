"""
integrations/huggingface_client.py

Hugging Face Inference + Hub client for NEXUS-AI-CORE.
Credentials resolved via core.secrets (Vault-first).

Capabilities:
  - Inference API (text generation, embeddings, classification)
  - Custom model scoring (Garrettc123/nexus-deal-scorer)
  - Sentence embeddings for semantic search
  - Dataset push/pull
  - Spaces management
"""

import logging
from typing import Any, Optional

import httpx

from core.secrets import SecretKey, require_secret, get_secret

logger = logging.getLogger(__name__)

HF_API = "https://api-inference.huggingface.co/models"
HF_HUB_API = "https://huggingface.co/api"


class HuggingFaceClient:
    """Hugging Face Inference API + Hub client."""

    def __init__(self):
        self._token = require_secret(SecretKey.HUGGINGFACE_API_TOKEN)
        self._embed_model = get_secret(SecretKey.HF_EMBED_MODEL, "sentence-transformers/all-MiniLM-L6-v2")
        self._score_model = get_secret(SecretKey.HF_SCORE_MODEL, "Garrettc123/nexus-deal-scorer")
        self._space_id = get_secret(SecretKey.HF_SPACE_ID)
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        logger.info("[HuggingFace] Client initialised (embed=%s, score=%s)", self._embed_model, self._score_model)

    def _infer(self, model: str, payload: dict) -> Any:
        r = httpx.post(f"{HF_API}/{model}", headers=self._headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()

    # ── Embeddings ─────────────────────────────────────────────────────────

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Compute sentence embeddings."""
        result = self._infer(self._embed_model, {"inputs": texts})
        logger.info("[HuggingFace] Embedded %d texts", len(texts))
        return result

    # ── Deal Scoring ───────────────────────────────────────────────────────

    def score_deal(self, deal_text: str) -> float:
        """Score a deal/lead using Garrettc123/nexus-deal-scorer."""
        result = self._infer(self._score_model, {"inputs": deal_text})
        # Expect [{"label": "POSITIVE", "score": 0.92}]
        if isinstance(result, list) and result:
            top = max(result, key=lambda x: x.get("score", 0))
            score = top.get("score", 0.0)
            logger.info("[HuggingFace] Deal score: %.3f", score)
            return float(score)
        return 0.0

    # ── Text Generation ────────────────────────────────────────────────────

    def generate(self, model: str, prompt: str, max_new_tokens: int = 256) -> str:
        result = self._infer(model, {"inputs": prompt, "parameters": {"max_new_tokens": max_new_tokens}})
        if isinstance(result, list) and result:
            return result[0].get("generated_text", "")
        return str(result)

    # ── Classification ─────────────────────────────────────────────────────

    def classify(self, model: str, text: str, labels: list[str]) -> dict:
        """Zero-shot classification."""
        result = self._infer(model, {"inputs": text, "parameters": {"candidate_labels": labels}})
        return result

    # ── Hub ────────────────────────────────────────────────────────────────

    def push_dataset(self, repo_id: str, data: list[dict]) -> dict:
        try:
            from datasets import Dataset  # type: ignore
            from huggingface_hub import HfApi  # type: ignore
            api = HfApi(token=self._token)
            ds = Dataset.from_list(data)
            ds.push_to_hub(repo_id, token=self._token)
            logger.info("[HuggingFace] Dataset pushed to %s", repo_id)
            return {"status": "ok", "repo": repo_id}
        except ImportError:
            raise RuntimeError("[HuggingFace] datasets + huggingface_hub required. pip install datasets huggingface_hub")
