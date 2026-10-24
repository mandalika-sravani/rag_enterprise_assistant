"""All settings in one place, read from environment variables or the .env file."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Claude (through langchain-anthropic)
    anthropic_api_key: SecretStr | None = None  # ANTHROPIC_API_KEY
    claude_model: str = "claude-haiku-5-5"  # CLAUDE_MODEL
    llm_timeout: float = 30  # seconds
    price_in: float = 1.0  # USD per million input tokens (check current pricing)
    price_out: float = 5.0  # USD per million output tokens

    # Documents and search
    docs_dir: Path = Path("sample_docs")
    index_dir: Path = Path("data")
    users_file: Path = Path("users.yaml")
    log_file: Path = Path("logs/requests.jsonl")
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    chunk_size: int = 900  # characters
    chunk_overlap: int = 150  # characters
    top_k: int = 5  # chunks given to the model
    min_score: float = 0.45  # below this cosine similarity, abstain without calling Claude

    # Conversation
    max_history_turns: int = 6
