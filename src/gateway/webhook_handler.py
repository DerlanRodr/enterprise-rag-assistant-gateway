"""
Orquestrador de Webhook de Mensageria Corporativa (WhatsApp / Canais de Trabalho).
Implementa as regras operacionais homologadas pelo responsável:
1. Controle de Acesso e Perfil RBAC (Analista, Gestor, Operacional).
2. Filtro de Ruído: Desconsidera reações e mensagens não acionáveis.
3. Filtro de Grupos Técnicos: Exige menção direta ao responsável.
4. Janela de Carência de 5 Minutos (Human-in-the-Loop Debounce):
   Se o responsável responder manualmente no prazo, a automação aborta.
5. Marcação da Conversa como Não Lida para Auditoria Humana Posterior.
6. Guardrail Anti-Alucinação com Síntese Adaptada ao Destinatário.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import re
import logging
from pydantic import BaseModel, Field
from src.core.security import WhitelistValidator, RecipientRole, sanitizar_texto_lgpd
from src.rag.retriever import KnowledgeRetriever
from src.rag.anti_hallucination import AntiHallucinationGuard

logger = logging.getLogger(__name__)


class InboundMessage(BaseModel):
    """Payload de entrada padronizado para webhooks de mensageria corporativa."""
    sender_id: str = Field(description="Identificador único do emissor (ex: número internacional +55...)")
    message_text: str = Field(description="Texto da mensagem enviada pelo usuário")
    channel: str = Field(default="whatsapp_group", description="Canal de origem (whatsapp_group, direct, teams)")
    is_group: bool = Field(default=False, description="Indica se a mensagem foi enviada em um grupo monitorado")
    mentions_maintainer: bool = Field(default=True, description="Indica se o responsável foi mencionado/marcado no grupo")
    maintainer_answered_in_window: bool = Field(default=False, description="Flag de verificação: responsável respondeu manualmente nos últimos 5 min?")
    is_reaction_or_acknowledgement: bool = Field(default=False, description="Reação ou confirmação (ex: joinha, 'ok', 'valeu')")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OutboundMessage(BaseModel):
    """Payload de saída padronizado para devolução ao canal de mensageria."""
    recipient_id: str
    response_text: str
    status: str
    is_authorized: bool
    role_applied: str = "NONE"
    mark_conversation_as_unread: bool = False
    confidence_score: float = 0.0
    sources: List[str] = Field(default_factory=list)
    processed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MessageGatewayHandler:
    """
    Gateway de Mensageria Corporativa com Políticas Operacionais de Produção.
    """
    REACTION_PATTERNS = {
        "ok", "blz", "beleza", "obrigado", "obg", "valeu", "show",
        "sim", "nao", "não", "combinado", "perfeito", "certo", "👍", "🙏"
    }

    def __init__(self, retriever: KnowledgeRetriever):
        self.retriever = retriever

    def _is_trivial_acknowledgement(self, text: str) -> bool:
        """Identifica mensagens triviais de confirmação ou agradecimento."""
        clean = re.sub(r"[^\w\s]", "", text.strip().lower()).strip()
        if not clean:
            return True
        words = [w for w in clean.split() if w not in {"muito", "demais", "ai", "aí"}]
        if not words:
            return True
        return all(w in self.REACTION_PATTERNS for w in words)

    def process_message(self, inbound: InboundMessage) -> OutboundMessage:
        sender = inbound.sender_id.strip()
        logger.info(f"Processando mensagem recebida de: {sender} no canal: {inbound.channel} (Grupo: {inbound.is_group})")

        # 1. Validação de Controle de Acesso (Whitelist & Papel do Destinatário)
        authorized, role, reject_reason = WhitelistValidator.authorize_or_reject(sender)
        if not authorized:
            logger.warning(f"Mensagem bloqueada na camada de segurança para o remetente: {sender}")
            return OutboundMessage(
                recipient_id=sender,
                response_text=reject_reason,
                status="UNAUTHORIZED_REJECTED",
                is_authorized=False,
                role_applied="UNAUTHORIZED",
                mark_conversation_as_unread=False,
                confidence_score=0.0,
                sources=[]
            )

        # 2. Filtro de Ruído: Ignora confirmações, reações ou respostas a perguntas anteriores
        if inbound.is_reaction_or_acknowledgement or self._is_trivial_acknowledgement(inbound.message_text):
            logger.info(f"Mensagem de ruído/confirmação ignorada: '{inbound.message_text}'")
            return OutboundMessage(
                recipient_id=sender,
                response_text="",
                status="IGNORED_NON_ACTIONABLE",
                is_authorized=True,
                role_applied=role.value,
                mark_conversation_as_unread=False,
                confidence_score=0.0,
                sources=[]
            )

        # 3. Filtro de Grupos Monitorados: Só atende se marcar o responsável diretamente
        if inbound.is_group and not inbound.mentions_maintainer:
            logger.info("Mensagem em grupo ignorada: responsável não foi mencionado diretamente.")
            return OutboundMessage(
                recipient_id=sender,
                response_text="",
                status="IGNORED_NOT_MENTIONED",
                is_authorized=True,
                role_applied=role.value,
                mark_conversation_as_unread=False,
                confidence_score=0.0,
                sources=[]
            )

        # 4. Janela de Carência de 5 Minutos (Human-in-the-Loop Debounce):
        # Se o responsável respondeu manualmente dentro da janela, o robô aborta a resposta
        if inbound.maintainer_answered_in_window:
            logger.info("Janela de carência: responsável já respondeu manualmente. Abortando envio automático.")
            return OutboundMessage(
                recipient_id=sender,
                response_text="",
                status="ABORTED_HUMAN_ANSWERED",
                is_authorized=True,
                role_applied=role.value,
                mark_conversation_as_unread=False,
                confidence_score=0.0,
                sources=[]
            )

        # 5. Higienização LGPD de Entrada
        clean_query = sanitizar_texto_lgpd(inbound.message_text)

        # 6. Recuperação Vetorial Contextual
        chunks = self.retriever.retrieve(query=clean_query)

        # 7. Guardrail Anti-Alucinação e Síntese Adaptada ao Papel
        synthesis = AntiHallucinationGuard.verify_and_synthesize(
            query=clean_query,
            retrieved_chunks=chunks,
            role=role
        )

        status = "AUTHORIZED_SUCCESS" if synthesis["grounded"] else "AUTHORIZED_OUT_OF_SCOPE"

        # Regra Operacional: Após qualquer resposta automática, deixar conversa como não lida para auditoria
        return OutboundMessage(
            recipient_id=sender,
            response_text=synthesis["answer"],
            status=status,
            is_authorized=True,
            role_applied=role.value,
            mark_conversation_as_unread=True,
            confidence_score=synthesis["confidence_score"],
            sources=synthesis["sources"]
        )
