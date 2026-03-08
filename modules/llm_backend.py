"""
LLM Backend Module — four backends with unified .query() interface.

Single source of truth for all backend names, model lists, and default models.
admin.py and sidebar.py both import from here — no model list lives anywhere else.

System prompts are now sourced from modules/prompts.py for easy editing.
"""
import requests
from typing import Dict, Any

# System prompts live in prompts.py — edit there
from modules.prompts import get_system_prompt

# ── Backend name constants ────────────────────────────────────────────────────
BACKEND_OLLAMA    = "Ollama (Local)"
BACKEND_MISTRAL   = "Mistral AI"
BACKEND_ANTHROPIC = "Anthropic (Claude)"
BACKEND_CUSTOM    = "Custom Endpoint"

BACKEND_LIST = [BACKEND_OLLAMA, BACKEND_MISTRAL, BACKEND_ANTHROPIC, BACKEND_CUSTOM]

# ── Model lists per backend ───────────────────────────────────────────────────
# Edit here to add/remove models globally.

BACKEND_MODELS: Dict[str, list] = {
    BACKEND_OLLAMA: [
        # Small / local models first — most common for local use
        "gemma3:1b",
        # "gemma3:4b",      # uncomment for a slightly larger gemma
        "llama3.2",
        "llama3.1",
        "llama3",
        "mistral",
        "mixtral",
        "phi3",
        # "phi3:mini",      # uncomment for the smaller phi3 variant
        "llama2",
    ],
    BACKEND_MISTRAL: [
        # "mistral-small-latest",
        # "mistral-medium-latest",  # uncomment if you have access
        # "mistral-large-latest",
        "codestral-latest",
        # "open-mixtral-8x22b",
    ],
    BACKEND_ANTHROPIC: [
        "claude-sonnet-4-20250514",
        # "claude-3-5-sonnet-20241022",   # previous Sonnet version
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ],
    BACKEND_CUSTOM: [],   # free-text model ID
}


def default_model(backend: str) -> str:
    models = BACKEND_MODELS.get(backend, [])
    return models[0] if models else ""


# ── LLMBackend class ──────────────────────────────────────────────────────────

class LLMBackend:
    def __init__(
        self,
        backend_type: str = BACKEND_OLLAMA,
        ollama_model: str = "",
        # ollama_url: str = "http://localhost:11434",   # default Ollama URL
        ollama_url: str = "http://localhost:11434",
        mistral_api_key: str = "",
        mistral_model: str = "",
        custom_url: str = "",
        custom_api_key: str = "",
        custom_model: str = "",
        anthropic_api_key: str = "",
        anthropic_model: str = "",
        # temperature: float = 0.1,   # lower = more deterministic for small models
        temperature: float = 0.2,
        # max_tokens: int = 1024,     # conservative default for local models
        max_tokens: int = 2048,
    ):
        self.backend_type      = backend_type
        self.ollama_url        = ollama_url.rstrip("/")
        self.mistral_api_key   = mistral_api_key
        self.custom_url        = custom_url
        self.custom_api_key    = custom_api_key
        self.anthropic_api_key = anthropic_api_key
        self.temperature       = temperature
        self.max_tokens        = max_tokens

        self.ollama_model    = ollama_model    or default_model(BACKEND_OLLAMA)
        self.mistral_model   = mistral_model   or default_model(BACKEND_MISTRAL)
        self.custom_model    = custom_model    or ""
        self.anthropic_model = anthropic_model or default_model(BACKEND_ANTHROPIC)

    @property
    def active_model_name(self) -> str:
        """Return the model name for the current backend (used for prompt tier detection)."""
        mapping = {
            BACKEND_OLLAMA:    self.ollama_model,
            BACKEND_MISTRAL:   self.mistral_model,
            BACKEND_ANTHROPIC: self.anthropic_model,
            BACKEND_CUSTOM:    self.custom_model,
        }
        return mapping.get(self.backend_type, "")

    def query(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Run a query with the configured backend. Uses analysis system prompt by default."""
        if not system_prompt:
            system_prompt = get_system_prompt("analysis", self.active_model_name)
        try:
            fn = {
                BACKEND_OLLAMA:    self._query_ollama,
                BACKEND_MISTRAL:   self._query_mistral,
                BACKEND_ANTHROPIC: self._query_anthropic,
                BACKEND_CUSTOM:    self._query_custom,
            }.get(self.backend_type)
            if fn is None:
                return {"response": "", "error": f"Unknown backend: {self.backend_type}"}
            return fn(prompt, system_prompt)
        except Exception as e:
            return {"response": "", "error": str(e)}

    def query_for_LLM_query(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Run a RAG / Q&A query. Uses query system prompt by default."""
        if not system_prompt:
            system_prompt = get_system_prompt("query", self.active_model_name)
        return self.query(prompt, system_prompt)

    def test_connection(self) -> bool:
        result = self.query("Reply with OK", "You are a test assistant. Reply only with 'OK'.")
        return result["error"] is None and bool(result["response"])

    # ── Backend implementations ───────────────────────────────────────────────

    def _query_ollama(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        # timeout: int = 60   # tighter timeout for fast local models
        timeout = 120
        resp = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model":  self.ollama_model,
                "prompt": f"System: {system_prompt}\n\nUser: {prompt}",
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    # "num_ctx": 4096,   # uncomment to set context window for Ollama
                },
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return {"response": resp.json().get("response", ""), "error": None}

    def _query_mistral(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        if not self.mistral_api_key:
            return {"response": "", "error": "Mistral API key not provided."}
        # endpoint = "https://api.mistral.ai/v1/chat/completions"   # standard endpoint
        endpoint = "https://codestral.mistral.ai/v1/chat/completions"
        resp = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {self.mistral_api_key}",
                     "Content-Type": "application/json"},
            json={"model": self.mistral_model,
                  "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user",   "content": prompt}],
                  "temperature": self.temperature,
                  "max_tokens":  self.max_tokens},
            timeout=60,
        )
        resp.raise_for_status()
        return {"response": resp.json()["choices"][0]["message"]["content"], "error": None}

    def _query_anthropic(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        if not self.anthropic_api_key:
            return {"response": "", "error": "Anthropic API key not provided."}
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.anthropic_api_key,
                     "anthropic-version": "2023-06-01",
                     "Content-Type": "application/json"},
            json={"model":      self.anthropic_model,
                  "max_tokens": self.max_tokens,
                  "system":     system_prompt,
                  "messages":   [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        resp.raise_for_status()
        return {"response": resp.json()["content"][0]["text"], "error": None}

    def _query_custom(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        if not self.custom_url:
            return {"response": "", "error": "Custom endpoint URL not provided."}
        headers = {"Content-Type": "application/json"}
        if self.custom_api_key:
            headers["Authorization"] = f"Bearer {self.custom_api_key}"
        resp = requests.post(
            self.custom_url, headers=headers,
            json={"model":       self.custom_model or "default",
                  "messages":    [{"role": "system", "content": system_prompt},
                                  {"role": "user",   "content": prompt}],
                  "temperature": self.temperature,
                  "max_tokens":  self.max_tokens},
            timeout=60,
        )
        resp.raise_for_status()
        data    = resp.json()
        content = (data["choices"][0]["message"]["content"] if "choices" in data
                   else data.get("response", str(data)))
        return {"response": content, "error": None}
