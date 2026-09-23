# core/opencode_service.py
import json
from pathlib import Path
from anthropic import Anthropic

class OpenCodeService:
    _client = None

    @classmethod
    def _resolve_auth(cls) -> str:
        """Reads API key exclusively from OpenCode's auth store."""
        auth_file = Path.home() / ".local" / "share" / "opencode" / "auth.json"
        if not auth_file.exists():
            raise RuntimeError(
                f"OpenCode auth file not found at {auth_file}. "
                "Ensure you ran 'opencode auth login' during Lab 0."
            )

        try:
            with open(auth_file, "r") as f:
                data = json.load(f)
                anthropic_entry = data.get("anthropic", {})
                if isinstance(anthropic_entry, dict):
                    api_key = anthropic_entry.get("key") or anthropic_entry.get("apiKey")
                elif isinstance(anthropic_entry, str):
                    api_key = anthropic_entry
                else:
                    api_key = None

                if api_key:
                    return api_key
        except Exception as e:
            raise RuntimeError(f"Failed to read OpenCode authentication store: {e}")

        raise RuntimeError(
            "Anthropic credentials not found in ~/.local/share/opencode/auth.json. "
            "Please run 'opencode auth login'."
        )

    @classmethod
    def get_client(cls) -> Anthropic:
        if cls._client is None:
            api_key = cls._resolve_auth()
            cls._client = Anthropic(api_key=api_key)
        return cls._client

    @classmethod
    def get_configured_model(cls, tier: str = "model") -> str:
        """Reads configured model tiers directly from opencode.json."""
        config_path = Path("opencode.json")
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                    m = data.get(tier, data.get("model", "claude-3-haiku-20240307"))
                    return m.replace("anthropic/", "")
            except Exception:
                pass
        return "claude-3-haiku-20240307"

    @classmethod
    def send(cls, system_prompt: str, user_prompt: str, model_id: str = None, **kwargs) -> str:
        client = cls.get_client()

        target_model = model_id or cls.get_configured_model("model")
        target_model = target_model.replace("anthropic/", "")

        if "sonnet" in target_model and not any(c.isdigit() for c in target_model.split("sonnet")[-1]):
            target_model = "claude-3-5-sonnet-20241022"
        elif "haiku" in target_model and not any(c.isdigit() for c in target_model.split("haiku")[-1]):
            target_model = "claude-3-haiku-20240307"

        response = client.messages.create(
            model=target_model,
            max_tokens=kwargs.get("max_tokens", 1000),
            system=system_prompt.strip(),
            messages=[{"role": "user", "content": user_prompt.strip()}]
        )

        # Safely extract from text blocks, bypassing thinking/reasoning blocks
        output_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                output_text += block.text
            elif getattr(block, "type", None) == "text":
                output_text += getattr(block, "text", "")

        return output_text.strip()