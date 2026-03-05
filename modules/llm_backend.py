"""
LLM Backend Module — four backends with unified .query() interface.

Single source of truth for all backend names, model lists, and default models.
admin.py and sidebar.py both import from here — no model list lives anywhere else.
"""
import requests
from typing import Dict, Any

# ── Backend name constants ────────────────────────────────────────────────────
BACKEND_OLLAMA    = "Ollama (Local)"
BACKEND_MISTRAL   = "Mistral AI"
BACKEND_ANTHROPIC = "Anthropic (Claude)"
BACKEND_CUSTOM    = "Custom Endpoint"

# Ordered list used to populate selectboxes
BACKEND_LIST = [BACKEND_OLLAMA, BACKEND_MISTRAL, BACKEND_ANTHROPIC, BACKEND_CUSTOM]

# ── Model lists per backend ───────────────────────────────────────────────────
# Edit here to add/remove models globally — sidebar and admin panel both reflect
# the change automatically with no other files to touch.
BACKEND_MODELS: Dict[str, list] = {
    BACKEND_OLLAMA: [
        "llama3",
        "llama3.1",
        "llama3.2",
        "mistral",
        "mixtral",
        "phi3",
        "llama2",
    ],
    BACKEND_MISTRAL: [
        "codestral-latest",
        "mistral-large-latest",
        "mistral-medium-latest",
        "mistral-small-latest",
        "codestral-latest",
        "open-mixtral-8x22b",
    ],
    BACKEND_ANTHROPIC: [
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ],
    BACKEND_CUSTOM: [],   # free-text model ID — no fixed list
}

# ── Default model per backend (first entry is the default) ───────────────────
# Changing the first item in BACKEND_MODELS above also changes the default.
def default_model(backend: str) -> str:
    models = BACKEND_MODELS.get(backend, [])
    return models[0] if models else ""

# ── System prompt ─────────────────────────────────────────────────────────────
DEFAULT_SYSTEM_PROMPT = (
    "You are an expert legal analyst specializing in multinational deal documentation. "
    "Analyze contract clauses with precision, identify risks, and provide actionable insights. "
    "Be concise, specific, and cite relevant clause language when possible."
)


# ── LLMBackend class ──────────────────────────────────────────────────────────
class LLMBackend:
    def __init__(
        self,
        backend_type: str = BACKEND_OLLAMA,
        ollama_model: str = "",
        ollama_url: str = "http://localhost:11434",
        mistral_api_key: str = "",
        mistral_model: str = "",
        custom_url: str = "",
        custom_api_key: str = "",
        custom_model: str = "",
        anthropic_api_key: str = "",
        anthropic_model: str = "",
        temperature: float = 0.2,
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

        # Fall back to default model if caller passes empty string
        self.ollama_model    = ollama_model    or default_model(BACKEND_OLLAMA)
        self.mistral_model   = mistral_model   or default_model(BACKEND_MISTRAL)
        self.custom_model    = custom_model    or ""
        self.anthropic_model = anthropic_model or default_model(BACKEND_ANTHROPIC)

    def query(self, prompt: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> Dict[str, Any]:
        try:
            dispatch = {
                BACKEND_OLLAMA:    self._query_ollama,
                BACKEND_MISTRAL:   self._query_mistral,
                BACKEND_ANTHROPIC: self._query_anthropic,
                BACKEND_CUSTOM:    self._query_custom,
            }
            fn = dispatch.get(self.backend_type)
            if fn is None:
                return {"response": "", "error": f"Unknown backend: {self.backend_type}"}
            return fn(prompt, system_prompt)
        except Exception as e:
            return {"response": "", "error": str(e)}

    def test_connection(self) -> bool:
        result = self.query("Reply with OK", "You are a test assistant. Reply only with 'OK'.")
        return result["error"] is None and bool(result["response"])

    def _query_ollama(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        resp = requests.post(
            f"{self.ollama_url}/api/generate",
            json={"model": self.ollama_model,
                  "prompt": f"System: {system_prompt}\n\nUser: {prompt}",
                  "stream": False,
                  "options": {"temperature": self.temperature, "num_predict": self.max_tokens}},
            timeout=120,
        )
        resp.raise_for_status()
        return {"response": resp.json().get("response", ""), "error": None}

    def _query_mistral(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        if not self.mistral_api_key:
            return {"response": "", "error": "Mistral API key not provided."}
        resp = requests.post(
            "https://codestral.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.mistral_api_key}",
                     "Content-Type": "application/json"},
            json={"model": self.mistral_model,
                  "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user",   "content": prompt}],
                  "temperature": self.temperature, "max_tokens": self.max_tokens},
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
            json={"model": self.anthropic_model, "max_tokens": self.max_tokens,
                  "system": system_prompt,
                  "messages": [{"role": "user", "content": prompt}]},
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
            json={"model": self.custom_model or "default",
                  "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user",   "content": prompt}],
                  "temperature": self.temperature, "max_tokens": self.max_tokens},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = (data["choices"][0]["message"]["content"] if "choices" in data
                   else data.get("response", str(data)))
        return {"response": content, "error": None}