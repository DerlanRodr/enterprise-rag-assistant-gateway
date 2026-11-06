"""
Gerenciamento de configurações da aplicação via Pydantic Settings com fallback gracioso.
"""
import os
from typing import Set
from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        app_name: str = "Enterprise RAG Assistant Gateway"
        app_env: str = "development"
        app_host: str = "0.0.0.0"
        app_port: int = 8000
        debug: bool = False

        # SurrealDB v2
        surreal_url: str = "ws://localhost:8000/rpc"
        surreal_user: str = "root"
        surreal_pass: str = "root"
        surreal_ns: str = "enterprise"
        surreal_db: str = "knowledge_base"

        # Open Notebook
        open_notebook_api_url: str = "http://localhost:5055/api"
        open_notebook_notebook_id: str = "notebook:enterprise_knowledge_demo"

        # Whitelist de contatos autorizados (separados por vírgula no .env)
        authorized_contacts_raw: str = Field(
            default="+5511999990001,+5511999990002,+5585999990003",
            alias="AUTHORIZED_CONTACTS"
        )
        security_token: str = "demo-secret-token-change-in-production"

        # RAG e Guardrails Anti-Alucinação
        similarity_threshold: float = 0.20
        max_chunks_per_query: int = 3
        strict_ground_truth: bool = True

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"
        )

        @property
        def authorized_contacts(self) -> Set[str]:
            """Retorna os identificadores de contatos em formato de conjunto para busca O(1)."""
            contacts = [c.strip() for c in self.authorized_contacts_raw.split(",") if c.strip()]
            return set(contacts)

    settings = Settings()

except ImportError:
    from pydantic import BaseModel

    class SettingsFallback(BaseModel):
        app_name: str = os.getenv("APP_NAME", "Enterprise RAG Assistant Gateway")
        app_env: str = os.getenv("APP_ENV", "development")
        app_host: str = os.getenv("APP_HOST", "0.0.0.0")
        app_port: int = int(os.getenv("APP_PORT", "8000"))
        debug: bool = os.getenv("DEBUG", "false").lower() == "true"

        # SurrealDB v2
        surreal_url: str = os.getenv("SURREAL_URL", "ws://localhost:8000/rpc")
        surreal_user: str = os.getenv("SURREAL_USER", "root")
        surreal_pass: str = os.getenv("SURREAL_PASS", "root")
        surreal_ns: str = os.getenv("SURREAL_NS", "enterprise")
        surreal_db: str = os.getenv("SURREAL_DB", "knowledge_base")

        # Open Notebook
        open_notebook_api_url: str = os.getenv("OPEN_NOTEBOOK_API_URL", "http://localhost:5055/api")
        open_notebook_notebook_id: str = os.getenv("OPEN_NOTEBOOK_NOTEBOOK_ID", "notebook:enterprise_knowledge_demo")

        authorized_contacts_raw: str = os.getenv(
            "AUTHORIZED_CONTACTS",
            "+5511999990001,+5511999990002,+5585999990003"
        )
        security_token: str = os.getenv("SECURITY_TOKEN", "demo-secret-token-change-in-production")

        similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.20"))
        max_chunks_per_query: int = int(os.getenv("MAX_CHUNKS_PER_QUERY", "3"))
        strict_ground_truth: bool = os.getenv("STRICT_GROUND_TRUTH", "true").lower() == "true"

        @property
        def authorized_contacts(self) -> Set[str]:
            contacts = [c.strip() for c in self.authorized_contacts_raw.split(",") if c.strip()]
            return set(contacts)

    settings = SettingsFallback()

