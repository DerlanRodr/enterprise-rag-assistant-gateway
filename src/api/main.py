"""
Ponto de Entrada Principal da API FastAPI: Enterprise RAG Assistant Gateway.
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Header, status
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.security import WhitelistValidator
from src.rag.retriever import KnowledgeRetriever
from src.rag.anti_hallucination import AntiHallucinationGuard
from src.gateway.webhook_handler import (
    MessageGatewayHandler,
    InboundMessage,
    OutboundMessage
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Instâncias globais da aplicação
knowledge_retriever: Optional[KnowledgeRetriever] = None
message_gateway: Optional[MessageGatewayHandler] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida da aplicação: inicialização de recursos e pré-carregamento."""
    global knowledge_retriever, message_gateway
    logger.info("Iniciando Enterprise RAG Assistant Gateway...")

    # Inicializa motor de recuperação e armazenamento vetorial
    knowledge_retriever = KnowledgeRetriever()
    message_gateway = MessageGatewayHandler(retriever=knowledge_retriever)

    # Ingestão automática do documento de diretrizes corporativas de exemplo
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "samples", "sample_enterprise_knowledge.md"
    )
    if os.path.exists(sample_path):
        count = knowledge_retriever.ingest_file(sample_path)
        logger.info(f"Base de conhecimento corporativa inicializada com {count} seções.")
    else:
        logger.warning(f"Arquivo de exemplo não localizado em: {sample_path}")

    yield

    logger.info("Encerrando Enterprise RAG Assistant Gateway...")


app = FastAPI(
    title="Enterprise RAG Assistant Gateway",
    description=(
        "Gateway corporativo de inteligência artificial com controle de acesso Zero Trust (Whitelist), "
        "banco vetorial semântico (SurrealDB v2 / In-Memory) e pipeline RAG estritamente auditado "
        "com guardrails anti-alucinação (Ground Truth Verification)."
    ),
    version="1.0.0",
    lifespan=lifespan
)


class QueryRequest(BaseModel):
    query: str = Field(description="Pergunta em linguagem natural a ser consultada na base")
    top_k: Optional[int] = Field(default=None, description="Número máximo de fragmentos recuperados")
    threshold: Optional[float] = Field(default=None, description="Limiar mínimo de similaridade de cosseno")


class IngestTextRequest(BaseModel):
    title: str = Field(description="Título do documento corporativo")
    content: str = Field(description="Conteúdo em Markdown ou texto puro")
    source_name: str = Field(default="admin_upload", description="Identificador da fonte/documento")


@app.get("/", tags=["Diagnóstico"])
def root() -> Dict[str, Any]:
    """Visão geral da API e metadados de arquitetura."""
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "status": "operational",
        "architecture": {
            "security": "Zero-Trust Whitelist Gatekeeper",
            "rag_engine": "Dense Semantic Cosine Similarity (128-dim)",
            "vector_store": "SurrealDB v2 Ready + Autonomous In-Memory Fallback",
            "anti_hallucination": "Strict Ground Truth Verification",
            "lgpd_compliance": "Automated Sensitive Data Sanitizer"
        },
        "endpoints": {
            "health": "/health",
            "webhook_message": "/webhook/message",
            "direct_query": "/api/v1/query",
            "admin_ingest": "/api/v1/admin/ingest",
            "admin_whitelist": "/api/v1/admin/whitelist"
        }
    }


@app.get("/health", tags=["Diagnóstico"])
def health_check() -> Dict[str, Any]:
    """Endpoint de auditoria de integridade e saúde operacional."""
    total_chunks = 0
    if knowledge_retriever and hasattr(knowledge_retriever.store, "fallback"):
        total_chunks = knowledge_retriever.store.fallback.total_chunks
    elif knowledge_retriever and hasattr(knowledge_retriever.store, "_chunks"):
        total_chunks = len(knowledge_retriever.store._chunks)

    return {
        "status": "healthy",
        "environment": settings.app_env,
        "total_authorized_contacts": len(settings.authorized_contacts),
        "total_indexed_chunks": total_chunks,
        "similarity_threshold": settings.similarity_threshold,
        "strict_ground_truth": settings.strict_ground_truth
    }


@app.post("/webhook/message", response_model=OutboundMessage, tags=["Mensageria Corporativa"])
def receive_webhook_message(inbound: InboundMessage) -> OutboundMessage:
    """
    Endpoint principal para webhooks de canais de mensageria corporativa.
    Aplica validação de Whitelist O(1), higienização LGPD e síntese RAG anti-alucinação.
    """
    if message_gateway is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway de mensageria ainda não inicializado."
        )
    return message_gateway.process_message(inbound)


@app.post("/api/v1/query", tags=["RAG & Conhecimento"])
def direct_query(
    request: QueryRequest,
    x_api_token: Optional[str] = Header(None, alias="X-API-Token")
) -> Dict[str, Any]:
    """
    Consulta direta à base de conhecimento corporativa com verificação factual estrita.
    """
    if knowledge_retriever is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Motor de recuperação indisponível."
        )

    chunks = knowledge_retriever.retrieve(
        query=request.query,
        top_k=request.top_k,
        threshold=request.threshold
    )
    result = AntiHallucinationGuard.verify_and_synthesize(
        query=request.query,
        retrieved_chunks=chunks
    )
    return result


@app.post("/api/v1/admin/ingest", tags=["Administração"])
def admin_ingest_markdown(
    request: IngestTextRequest,
    x_api_token: Optional[str] = Header(None, alias="X-API-Token")
) -> Dict[str, Any]:
    """
    Ingestão dinâmica de novos documentos na base de conhecimento.
    """
    if x_api_token != settings.security_token and settings.app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de segurança administrativo inválido."
        )

    if knowledge_retriever is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Motor de recuperação indisponível."
        )

    full_md = f"# {request.title}\n\n{request.content}"
    count = knowledge_retriever.ingest_markdown(full_md, source_name=request.source_name)
    return {
        "status": "success",
        "chunks_indexed": count,
        "source": request.source_name
    }


@app.get("/api/v1/admin/whitelist", tags=["Administração"])
def admin_list_whitelist() -> Dict[str, Any]:
    """
    Retorna métricas da lista de contatos autorizados (sanitizada com mascaramento para segurança).
    """
    masked_contacts = []
    for c in sorted(settings.authorized_contacts):
        if len(c) > 6:
            masked = c[:4] + "***" + c[-2:]
        else:
            masked = "***"
        masked_contacts.append(masked)

    return {
        "total_authorized": len(settings.authorized_contacts),
        "contacts_masked": masked_contacts,
        "access_policy": "Zero-Trust Strict Whitelisting"
    }
