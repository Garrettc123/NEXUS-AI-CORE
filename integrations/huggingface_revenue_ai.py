"""
Garcar Enterprise — HuggingFace Revenue AI
Echo Revenue Flow: Deal scoring, content generation, AI-powered product descriptions, lead qualification
"""

import os
import httpx
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

HF_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN", "")
HF_BASE_URL = "https://api-inference.huggingface.co/models"


class HuggingFaceRevenueAI:
    """
    HuggingFace Revenue AI — Garcar Enterprise AI inference layer.
    Powers:
    - Lead quality scoring (0.0–1.0)
    - AI-generated product descriptions for Shopify
    - Email subject line optimization for outbound
    - Deal risk classification
    - Autonomous content pipeline for Notion pages
    """

    def __init__(self):
        self.token = HF_API_TOKEN
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def score_deal(
        self,
        company: str,
        title: str,
        industry: str,
        company_size: Optional[int] = None,
    ) -> float:
        """Zero-shot deal quality classification. Returns 0.0–1.0."""
        text = f"{company} {title} {industry} {company_size or ''}"
        payload = {
            "inputs": text,
            "parameters": {
                "candidate_labels": ["high value deal", "low value deal", "medium value deal"]
            },
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{HF_BASE_URL}/facebook/bart-large-mnli",
                headers=self.headers,
                json=payload,
            )
            result = resp.json()
            labels = result.get("labels", [])
            scores = result.get("scores", [])
            score_map = dict(zip(labels, scores))
            deal_score = score_map.get("high value deal", 0.5)
            logger.info(f"[HF] Deal score for {company}: {deal_score:.3f}")
            return deal_score

    async def generate_product_description(
        self, product_name: str, features: List[str]
    ) -> str:
        """Generate Shopify product description via HuggingFace text generation."""
        prompt = f"Write a compelling product description for: {product_name}. Features: {', '.join(features)}. Description:"
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 200, "temperature": 0.7},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{HF_BASE_URL}/mistralai/Mistral-7B-Instruct-v0.3",
                headers=self.headers,
                json=payload,
            )
            result = resp.json()
            if isinstance(result, list):
                return result[0].get("generated_text", "").replace(prompt, "").strip()
            return "Premium AI-powered enterprise solution by Garcar."

    async def optimize_email_subject(
        self, base_subject: str, audience: str
    ) -> str:
        """AI email subject line optimizer for outbound revenue campaigns."""
        prompt = f"Rewrite this email subject line to maximize open rates for {audience}: '{base_subject}'. Optimized:"
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 60, "temperature": 0.8},
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{HF_BASE_URL}/mistralai/Mistral-7B-Instruct-v0.3",
                headers=self.headers,
                json=payload,
            )
            result = resp.json()
            if isinstance(result, list):
                text = result[0].get("generated_text", "").replace(prompt, "").strip()
                return text.split("\n")[0] if text else base_subject
            return base_subject
