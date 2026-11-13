from submarine_backend.config import Settings

# Tests must not depend on a developer's local .env (for example an enabled
# Ollama cleanup or a forced source language).
Settings.model_config["env_file"] = None
