"""
Módulo de segurança, controle de acesso e higienização de dados (LGPD by Design).
"""
import re
import logging
from typing import Tuple
from src.core.config import settings

logger = logging.getLogger(__name__)


class WhitelistValidator:
    """
    Controlador de Acesso: Valida se o emissor da mensagem faz parte do
    grupo restrito de contatos autorizados para consulta à base de conhecimento.
    """

    @classmethod
    def is_authorized(cls, sender_id: str) -> bool:
        """
        Verifica a presença do contato na Whitelist em tempo O(1).
        """
        if not sender_id:
            return False
        clean_id = re.sub(r"[^\d+]", "", sender_id.strip())
        return clean_id in settings.authorized_contacts

    @classmethod
    def authorize_or_reject(cls, sender_id: str) -> Tuple[bool, str]:
        """
        Retorna se o acesso foi concedido e a mensagem padronizada.
        """
        if cls.is_authorized(sender_id):
            return True, "Acesso autorizado."
        
        logger.warning(f"Tentativa de acesso não autorizada interceptada para o emissor: {sender_id}")
        return (
            False,
            "Acesso restrito. Este assistente corporativo responde exclusivamente a contatos autorizados."
        )


def sanitizar_texto_lgpd(texto: str) -> str:
    """
    Higieniza o texto de entrada/saída removendo padrões sensíveis como CPFs
    ou cartões antes de qualquer processamento ou log.
    """
    if not texto:
        return ""
    
    # Mascara CPF (ex: 123.456.789-00 ou 12345678900)
    cpf_regex = r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"
    texto_limpo = re.sub(cpf_regex, "[CPF_REMOVIDO]", texto)

    # Mascara cartões de crédito (16 dígitos)
    card_regex = r"\b(?:\d{4}[ -]?){3}\d{4}\b"
    texto_limpo = re.sub(card_regex, "[CARTAO_REMOVIDO]", texto_limpo)

    return texto_limpo
