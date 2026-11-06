"""
Orquestrador de Webhook de Mensageria Corporativa com Controle de Acesso e RAG Factual.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging
from pydantic import BaseModel, Field
from src.core.security import WhitelistValidator, sanitizar_texto_lgpd
from src.rag.retriever import KnowledgeRetriever
from src.rag.anti_hallucination import AntiHallucinationGuard

logger = logging.getLogger(__name__)


class InboundMessage(BaseModel):
    """Payload de entrada padronizado para webhooks de mensageria corporativa."""
    sender_id: str = Field(description="Identificador único do emissor (ex: número internacional +55...)")
    message_text: str = Field(description="Texto da mensagem enviada pelo usuário")
    channel: str = Field(default="corporate_messenger", description="Canal de origem (webhook, teams, rest)")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OutboundMessage(BaseModel):
    """Payload de saída padronizado para devolução ao canal de mensageria."""
    recipient_id: str
    response_text: str
    status: str
    is_authorized: bool
    confidence_score: float = 0.0
    sources: List[str] = Field(default_factory=list)
    processed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MessageGatewayHandler:
    """
    Gateway de Mensageria:
    1. Intercepta mensagens e valida a Whitelist de segurança (Zero Trust).
    2. Aplica higienização LGPD aos dados recebidos.
    3. Aciona o pipeline RAG com verificação estrita anti-alucinação.
    4. Formata a resposta com lastro documental e telemetria de confiança.
    """
    def __init__(self, retriever: KnowledgeRetriever):
        self.retriever = retriever

    def process_message(self, inbound: InboundMessage) -> OutboundMessage:
        sender = inbound.sender_id.strip()
        logger.info(f"Processando mensagem recebida de: {sender} no canal: {inbound.channel}")

        # 1. Validação de Controle de Acesso (Whitelist Gatekeeper)
        authorized, reject_reason = WhitelistValidator.authorize_or_reject(sender)
        if not authorized:
            logger.warning(f"Mensagem bloqueada na camada de segurança para o remetente: {sender}")
            return OutboundMessage(
                recipient_id=sender,
                response_text=reject_reason,
                status="UNAUTHORIZED_REJECTED",
                is_authorized=False,
                confidence_score=0.0,
                sources=[]
            )

        # 2. Higienização LGPD de Entrada
        clean_query = sanitizar_texto_lgpd(inbound.message_text)

        # 3. Recuperação Vetorial Contextual
        chunks = self.retriever.retrieve(query=clean_query)

        # 4. Guardrail Anti-Alucinação (Ground Truth Verification)
        synthesis = AntiHallucinationGuard.verify_and_synthesize(
            query=clean_query,
            retrieved_chunks=chunks
        )

        status = "AUTHORIZED_SUCCESS" if synthesis["grounded"] else "AUTHORIZED_OUT_OF_SCOPE"

        return OutboundMessage(
            recipient_id=sender,
            response_text=synthesis["answer"],
            status=status,
            is_authorized=True,
            confidence_score=synthesis["confidence_score"],
            sources=synthesis["sources"]
        )
