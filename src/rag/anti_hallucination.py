"""
Módulo de Guardrails Anti-Alucinação (Ground Truth Verification).
Garante que o assistente responda EXCLUSIVAMENTE com base em documentos oficiais auditados,
eliminando alucinações de modelos generativos em ambientes corporativos críticos.
"""
from typing import List, Dict, Any, Optional
import logging
from src.core.config import settings
from src.core.security import sanitizar_texto_lgpd
from src.rag.vector_store import DocumentChunk

logger = logging.getLogger(__name__)


class AntiHallucinationGuard:
    """
    Camada de proteção e verificação factual (Ground Truth).
    Impede que o assistente responda a perguntas fora do escopo ou invente diretrizes.
    """
    FALLBACK_REJECTION_MESSAGE: str = (
        "Informação não localizada na base de conhecimento corporativa oficial. "
        "Para preservar a integridade dos dados e prevenir alucinações, "
        "consulte o setor responsável ou a documentação homologada."
    )

    @classmethod
    def verify_and_synthesize(
        cls,
        query: str,
        retrieved_chunks: List[DocumentChunk],
        strict: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Valida a relevância dos fragmentos recuperados.
        Caso nenhum fragmento atinja o limiar de similaridade, bloqueia a resposta generativa.
        """
        is_strict = strict if strict is not None else settings.strict_ground_truth

        # 1. Checagem de disponibilidade de chunks
        if not retrieved_chunks:
            logger.info("Guardrail ativado: nenhum fragmento relevante recuperado. Bloqueando resposta.")
            return {
                "grounded": False,
                "answer": cls.FALLBACK_REJECTION_MESSAGE,
                "sources": [],
                "confidence_score": 0.0,
                "guardrail_status": "REJECTED_LOW_SIMILARITY"
            }

        # 2. Avaliação de pontuação do chunk primário
        top_chunk = retrieved_chunks[0]
        confidence = top_chunk.similarity

        if confidence < settings.similarity_threshold:
            logger.info(
                f"Guardrail ativado: confiança {confidence:.2f} inferior ao limiar {settings.similarity_threshold:.2f}."
            )
            return {
                "grounded": False,
                "answer": cls.FALLBACK_REJECTION_MESSAGE,
                "sources": [top_chunk.source],
                "confidence_score": confidence,
                "guardrail_status": "REJECTED_THRESHOLD_UNMET"
            }

        # 3. Síntese factual auditável (Grounded Response)
        # Monta a resposta estritamente lastreada nos trechos oficiais
        resumo_trechos = []
        fontes_usadas = []

        for c in retrieved_chunks:
            fontes_usadas.append(f"{c.source} :: {c.title}")
            resumo_trechos.append(f"• **{c.title}**:\n{c.content}")

        corpo_resposta = (
            f"Com base na base de conhecimento corporativa oficial:\n\n"
            + "\n\n".join(resumo_trechos)
            + f"\n\n*Fontes auditadas: {', '.join(set(c.source for c in retrieved_chunks))}*"
        )

        # Higienização de dados na saída (LGPD by Design)
        resposta_higienizada = sanitizar_texto_lgpd(corpo_resposta)

        return {
            "grounded": True,
            "answer": resposta_higienizada,
            "sources": list(set(fontes_usadas)),
            "confidence_score": confidence,
            "guardrail_status": "APPROVED"
        }

    @classmethod
    def build_llm_prompt(cls, query: str, chunks: List[DocumentChunk]) -> Dict[str, str]:
        """
        Gera os prompts de Sistema e Usuário com restrição estrita de alucinação
        para interoperabilidade com LLMs (Gemini, Claude, GPT).
        """
        context_str = "\n\n---\n\n".join([f"FONTE: {c.source} | SEÇÃO: {c.title}\n{c.content}" for c in chunks])
        
        system_instruction = (
            "Você é um Assistente Corporativo estritamente factual.\n"
            "Diretrizes inegociáveis:\n"
            "1. Responda SOMENTE e EXCLUSIVAMENTE com base no contexto fornecido.\n"
            "2. Nunca invente regras, políticas ou exceções não descritas no texto.\n"
            f"3. Se a informação não constar explicitamente no contexto, responda exatamente: '{cls.FALLBACK_REJECTION_MESSAGE}'\n"
            "4. Não mencione conjecturas ou opiniões externas."
        )

        user_prompt = (
            f"CONTEXTO OFICIAL:\n{context_str}\n\n"
            f"PERGUNTA DO COLABORADOR:\n{query}\n\n"
            "RESPOSTA FACTUAL:"
        )

        return {
            "system_instruction": system_instruction,
            "user_prompt": user_prompt
        }
