"""
Módulo de segurança, controle de acesso, perfis de destinatário e higienização (LGPD by Design).
"""
import re
import logging
from enum import Enum
from typing import Tuple, Dict, Optional, Set
from src.core.config import settings

logger = logging.getLogger(__name__)


class RecipientRole(str, Enum):
    """Perfis de destinatários homologados para adequação de tom e profundidade técnica."""
    ANALYST = "ANALYST"          # Analistas técnicos: tabelas, fórmulas, consultas
    MANAGER = "MANAGER"          # Gestores: impacto executivo, linguagem simples, LGPD
    OPERATIONAL = "OPERATIONAL"  # Demais colaboradores: prático, sem jargão, direciona a chamado
    UNAUTHORIZED = "UNAUTHORIZED"# Contatos desconhecidos ou não homologados


class WhitelistValidator:
    """
    Controlador de Acesso e Perfis (Role-Based Access Control - RBAC).
    Valida a autorização do emissor e define o perfil de resposta adequado.
    """
    # Mapeamento sintético de contatos para demonstração pública (configurável via ambiente)
    ROLES_MAP: Dict[str, RecipientRole] = {
        "+5511999990001": RecipientRole.ANALYST,
        "+5511999990002": RecipientRole.MANAGER,
        "+5585999990003": RecipientRole.OPERATIONAL,
    }

    @classmethod
    def get_role(cls, sender_id: str) -> RecipientRole:
        """Retorna o perfil corporativo do contato homologado."""
        if not sender_id:
            return RecipientRole.UNAUTHORIZED
        clean_id = re.sub(r"[^\d+]", "", sender_id.strip())
        
        # Verifica se está no mapa de papéis ou na whitelist genérica
        if clean_id in cls.ROLES_MAP:
            return cls.ROLES_MAP[clean_id]
        if clean_id in settings.authorized_contacts:
            return RecipientRole.OPERATIONAL
        return RecipientRole.UNAUTHORIZED

    @classmethod
    def is_authorized(cls, sender_id: str) -> bool:
        return cls.get_role(sender_id) != RecipientRole.UNAUTHORIZED

    @classmethod
    def authorize_or_reject(cls, sender_id: str) -> Tuple[bool, RecipientRole, str]:
        role = cls.get_role(sender_id)
        if role != RecipientRole.UNAUTHORIZED:
            return True, role, "Acesso autorizado."
        
        logger.warning(f"Acesso não autorizado interceptado para o emissor: {sender_id}")
        return (
            False,
            RecipientRole.UNAUTHORIZED,
            "Acesso restrito. Este assistente corporativo responde exclusivamente a contatos homologados pelo responsável."
        )


def remover_caminhos_locais(texto: str) -> str:
    """
    Higieniza o documento de conhecimento removendo caminhos físicos locais da máquina
    (ex: D:\\..., C:\\..., scripts/..., /var/...) para proteção da infraestrutura,
    mas preservando identificadores de chamados (ex: #2026...), tabelas e normas.
    """
    if not texto:
        return ""
    # Remove caminhos Windows e Linux (ex: D:\pasta\arquivo.ext ou /home/user/...)
    texto_sem_caminhos = re.sub(r"[a-zA-Z]:\\[^ \n\r\t]+", "[CAMINHO_INTERNO]", texto)
    texto_sem_caminhos = re.sub(r"(?:/[a-zA-Z0-9_\-\.]+){2,}", "[CAMINHO_INTERNO]", texto_sem_caminhos)
    return texto_sem_caminhos


def sanitizar_texto_lgpd(texto: str) -> str:
    """
    Higieniza o texto mascarando dados pessoais (LGPD by Design):
    Remove CPFs e números de cartão corporativo, preservando conteúdo técnico.
    """
    if not texto:
        return ""
    
    # Mascara CPF
    cpf_regex = r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"
    texto_limpo = re.sub(cpf_regex, "[CPF_REMOVIDO]", texto)

    # Mascara cartões de crédito
    card_regex = r"\b(?:\d{4}[ -]?){3}\d{4}\b"
    texto_limpo = re.sub(card_regex, "[CARTAO_REMOVIDO]", texto_limpo)

    return texto_limpo
