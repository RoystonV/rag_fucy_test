# =============================================================================
# generator.py — LLM prompt construction + Gemini call
# =============================================================================

import json
import os
from typing import Any, Optional

from haystack import Document

import config


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

TARA_PROMPT = """You are a cybersecurity expert specializing in automotive TARA (Threat Analysis and Risk Assessment) per ISO/SAE 21434.

You must answer the user's query using ONLY the provided context documents. If the context does not contain enough information, say so explicitly — do NOT make up information.

## Rules:
1. Output ONLY valid JSON — no markdown fences, no commentary
2. Use exact data from the context — do not invent IDs, names, or values
3. Include source references where possible
4. Structure the output as the query requires

## Context:
{context}

## User Query:
{query}

## JSON Response:"""


class FucyGenerator:
    """
    Assembles the final prompt, calls Gemini (optionally with CAG cache),
    and validates JSON output.
    """

    def __init__(self):
        os.environ["GOOGLE_API_KEY"] = config.GOOGLE_API_KEY

    def generate(
        self,
        query: str,
        context_docs: list[Document],
        context_text: str = "",
        cache_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Generate a response using Gemini.

        Args:
            query: User question.
            context_docs: Assembled context documents (from RAG path).
            context_text: Pre-formatted context string. If empty, formats from docs.
            cache_name: Optional Gemini cache_name for CAG. If provided,
                        the cached domain knowledge is automatically included.

        Returns:
            Parsed JSON dict, or {"error": ..., "raw": ...} on failure.
        """
        # Format context from documents if not pre-formatted
        if not context_text and context_docs:
            from context.assembler import ContextAssembler
            context_text = ContextAssembler().format_context(context_docs)

        prompt = TARA_PROMPT.format(context=context_text or "(no context)", query=query)

        # Call Gemini — with or without CAG
        raw_response = self._call_gemini(prompt, cache_name)

        # Parse JSON
        result = self._parse_json(raw_response)

        if result is None:
            # Retry once with repair instruction
            print("  [Generator] JSON parse failed — retrying with repair prompt...")
            repair_prompt = (
                f"The following text should be valid JSON but has errors. "
                f"Fix the JSON and return ONLY the corrected JSON, nothing else:\n\n{raw_response}"
            )
            raw_repair = self._call_gemini(repair_prompt, cache_name)
            result = self._parse_json(raw_repair)

        if result is None:
            return {"error": "Failed to generate valid JSON", "raw": raw_response}

        return result

    def _call_gemini(self, prompt: str, cache_name: Optional[str] = None) -> str:
        """Call Gemini API, optionally attaching a cached context."""
        try:
            if cache_name:
                # Use google-genai SDK with cache reference
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=config.GOOGLE_API_KEY)
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        cached_content=cache_name,
                        temperature=config.GENERATION_KWARGS.get("temperature", 0.0),
                    ),
                )
                return response.text or ""
            else:
                # Use Haystack generator (no cache)
                from haystack_integrations.components.generators.google_ai import GoogleAIGeminiGenerator
                generator = GoogleAIGeminiGenerator(
                    model=config.GEMINI_MODEL,
                    generation_kwargs=config.GENERATION_KWARGS,
                )
                result = generator.run(prompt=prompt)
                return result["replies"][0] if result["replies"] else ""

        except Exception as e:
            print(f"  [Generator] Gemini call failed: {e}")
            return ""

    @staticmethod
    def _parse_json(text: str) -> Optional[dict]:
        """Try to parse JSON from LLM output, stripping markdown fences."""
        if not text:
            return None

        # Strip markdown code fences
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]  # drop opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None
