"""
Módulo de Guardrails Anti-Alucinação e Resposta Adaptativa por Papel (Role-Based Personas).
Garante respostas estritamente baseadas na base de conhecimento oficial (Ground Truth)
e adapta o nível de detalhe (Analista, Gestor, Operacional).
"""
from typing import List, Dict, Any, Optional
import logging
from src.core.config import settings
from src.core.security import sanitizar_texto_lgpd, RecipientRole
from src.rag.vector_store import DocumentChunk

logger = logging.getLogger(__name__)


class AntiHallucinationGuard:
    """
    Camada de proteção, verificação factual e síntese adaptativa por perfil corporativo.
    """

    @classmethod
    def get_fallback_message(cls, role: RecipientRole) -> str:
        """Mensagem padronizada quando a documentação não responde à pergunta."""
        if role == RecipientRole.ANALYST:
            return (
                "A informação técnica solicitada não foi localizada na base de conhecimento oficial. "
                "O responsável técnico analisará a solicitação e retornará diretamente."
            )
        elif role == RecipientRole.MANAGER:
            return (
                "A documentação homologada não esclarece esta solicitação no momento. "
                "Esta resposta é baseada estritamente nas diretrizes vigentes e respeita a LGPD. "
                "Favor aguardar o retorno direto do responsável."
            )
        else:  # OPERATIONAL / Demais
            return (
                "A informação solicitada não consta na documentação oficial homologada. "
                "Para prosseguir com sua solicitação, favor abrir um chamado no sistema de "
                "atendimento corporativo ou contatar o responsável técnico."
            )

    @classmethod
    def verify_and_synthesize(
        cls,
        query: str,
        retrieved_chunks: List[DocumentChunk],
        role: RecipientRole = RecipientRole.OPERATIONAL,
        strict: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Valida os fragmentos recuperados e formata a resposta no nível de detalhe
        apropriado para o papel do destinatário.
        """
        is_strict = strict if strict is not None else settings.strict_ground_truth

        # 1. Checagem de disponibilidade de chunks
        if not retrieved_chunks:
            logger.info(f"Guardrail ativado: nenhum chunk recuperado para perfil {role.value}.")
            return {
                "grounded": False,
                "answer": cls.get_fallback_message(role),
                "sources": [],
                "confidence_score": 0.0,
                "role_applied": role.value,
                "guardrail_status": "REJECTED_LOW_SIMILARITY"
            }

        top_chunk = retrieved_chunks[0]
        confidence = top_chunk.similarity

        if confidence < settings.similarity_threshold:
            logger.info(
                f"Guardrail ativado: confiança {confidence:.2f} inferior ao limiar {settings.similarity_threshold:.2f}."
            )
            return {
                "grounded": False,
                "answer": cls.get_fallback_message(role),
                "sources": [top_chunk.source],
                "confidence_score": confidence,
                "role_applied": role.value,
                "guardrail_status": "REJECTED_THRESHOLD_UNMET"
            }

        # 2. Formatação da resposta conforme o papel do destinatário
        fontes_usadas = list(set(c.source for c in retrieved_chunks))
        
        if role == RecipientRole.ANALYST:
            # Perfil Analista: Detalhes técnicos, regras, tabelas e integridade
            detalhes = []
            for c in retrieved_chunks:
                detalhes.append(f"### [{c.title}]\n{c.content}")
            corpo = (
                "**[Detalhamento Técnico Documentado]**\n\n"
                + "\n\n".join(detalhes)
                + f"\n\n*Fontes auditadas: {', '.join(fontes_usadas)}*"
            )
        elif role == RecipientRole.MANAGER:
            # Perfil Gestor: Resumo executivo, impacto de negócio, sem jargões desnecessários
            resumos = [f"• **{c.title}**: {c.content.splitlines()[0]}" for c in retrieved_chunks]
            corpo = (
                "Olá. Com base exclusivamente na documentação corporativa homologada "
                "(autorizado pelo responsável e em conformidade com a LGPD):\n\n"
                + "\n\n".join(resumos)
                + "\n\n*Caso necessite de encaminhamento complementar, o responsável permanece à disposição.*"
            )
        else:
            # Perfil Operacional / Colaboradores: Prático, orientativo, sem jargões
            passos = [f"• **{c.title}**:\n{c.content}" for c in retrieved_chunks]
            corpo = (
                "Informações encontradas na documentação oficial:\n\n"
                + "\n\n".join(passos)
                + "\n\n*Em caso de dúvidas sobre exceções, registre um chamado no sistema corporativo de atendimento.*"
            )

        # Higienização de dados sensíveis na saída
        resposta_higienizada = sanitizar_texto_lgpd(corpo)

        return {
            "grounded": True,
            "answer": resposta_higienizada,
            "sources": [f"{c.source} :: {c.title}" for c in retrieved_chunks],
            "confidence_score": confidence,
            "role_applied": role.value,
            "guardrail_status": "APPROVED"
        }

