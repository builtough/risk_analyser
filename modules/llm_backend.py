"""
LLM Backend Module
Supports three backends:
  1. Ollama (local models via HTTP)
  2. Mistral AI (cloud API)
  3. Custom endpoint (user-defined URL + API key)

All backends expose a unified `query(prompt, system_prompt)` interface.
"""

import requests
import json
from typing import Optional, Dict, Any


# ─────────────────────────────────────────────
# Backend Configuration
# ─────────────────────────────────────────────

BACKEND_OLLAMA = "Ollama (Local)"
BACKEND_MISTRAL = "Mistral AI"
BACKEND_CUSTOM = "Custom Endpoint"
BACKEND_ANTHROPIC = "Anthropic (Claude)"

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert legal analyst specializing in multinational deal documentation. "
    "Analyze contract clauses with precision, identify risks, and provide actionable insights. "
    "Be concise, specific, and cite relevant clause language when possible."
)


class LLMBackend:
    """
    Unified LLM backend abstraction.
    Initialize with backend type and credentials, then call .query().
    """

    def __init__(
        self,
        backend_type: str = BACKEND_OLLAMA,
        ollama_model: str = "llama3",
        ollama_url: str = "http://localhost:11434",
        mistral_api_key: str = "",
        mistral_model: str = "mistral-large-latest",
        custom_url: str = "",
        custom_api_key: str = "",
        custom_model: str = "",
        anthropic_api_key: str = "",
        anthropic_model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.2,
        max_tokens: int = 2048
    ):
        self.backend_type = backend_type
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url.rstrip("/")
        self.mistral_api_key = mistral_api_key
        self.mistral_model = mistral_model
        self.custom_url = custom_url
        self.custom_api_key = custom_api_key
        self.custom_model = custom_model
        self.anthropic_api_key = anthropic_api_key
        self.anthropic_model = anthropic_model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def query(self, prompt: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> Dict[str, Any]:
        """
        Send a prompt to the configured LLM backend.
        Returns dict with 'response' (str) and 'error' (str|None).
        """
        try:
            if self.backend_type == BACKEND_OLLAMA:
                return self._query_ollama(prompt, system_prompt)
            elif self.backend_type == BACKEND_MISTRAL:
                return self._query_mistral(prompt, system_prompt)
            elif self.backend_type == BACKEND_ANTHROPIC:
                return self._query_anthropic(prompt, system_prompt)
            elif self.backend_type == BACKEND_CUSTOM:
                return self._query_custom(prompt, system_prompt)
            else:
                return {"response": "", "error": f"Unknown backend: {self.backend_type}"}
        except Exception as e:
            return {"response": "", "error": str(e)}

    def _query_ollama(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Query local Ollama instance."""
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": f"System: {system_prompt}\n\nUser: {prompt}",
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens
            }
        }
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return {"response": data.get("response", ""), "error": None}

    def _query_mistral(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Query Mistral AI cloud API."""
        if not self.mistral_api_key:
            return {"response": "", "error": "Mistral API key not provided."}
        
        url = "https://codestral.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.mistral_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.mistral_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return {"response": content, "error": None}

    def _query_anthropic(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Query Anthropic Claude API."""
        if not self.anthropic_api_key:
            return {"response": "", "error": "Anthropic API key not provided."}
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.anthropic_model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}]
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["content"][0]["text"]
        return {"response": content, "error": None}

    def _query_custom(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Query a custom OpenAI-compatible endpoint."""
        if not self.custom_url:
            return {"response": "", "error": "Custom endpoint URL not provided."}
        
        headers = {"Content-Type": "application/json"}
        if self.custom_api_key:
            headers["Authorization"] = f"Bearer {self.custom_api_key}"
        
        payload = {
            "model": self.custom_model or "default",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        resp = requests.post(self.custom_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        
        # Handle both OpenAI-style and raw response formats
        if "choices" in data:
            content = data["choices"][0]["message"]["content"]
        elif "response" in data:
            content = data["response"]
        else:
            content = str(data)
        
        return {"response": content, "error": None}

    def test_connection(self) -> bool:
        """Test if the backend is reachable."""
        result = self.query("Reply with OK", "You are a test assistant. Reply only with 'OK'.")
        print (result)
        import streamlit as st
        st.write(result)
        return result["error"] is None and bool(result["response"])