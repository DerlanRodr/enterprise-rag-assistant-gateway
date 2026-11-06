"""
Suíte de testes de integração e unidade para Enterprise RAG Assistant Gateway.
Valida:
1. Controle de Acesso e Perfis (Whitelist & RBAC: Analista, Gestor, Operacional)
2. Higienização LGPD e Expurgo de Caminhos Locais da Máquina
3. Armazenamento Vetorial e Similaridade de Cosseno
4. Guardrails Anti-Alucinação e Respostas Adaptadas ao Perfil
5. Regras Reais de Mensageria (Grace Period de 5 min, Ruído, Auditoria)
6. Endpoints HTTP da API FastAPI
"""
import pytest
from fastapi.testclient import TestClient

from src.core.config import settings
from src.core.security import WhitelistValidator, RecipientRole, sanitizar_texto_lgpd, remover_caminhos_locais
from src.rag.vector_store import InMemoryVectorStore, DocumentChunk, EmbeddingEngine
from src.rag.retriever import KnowledgeRetriever
from src.rag.anti_hallucination import AntiHallucinationGuard
from src.gateway.webhook_handler import MessageGatewayHandler, InboundMessage
from src.api.main import app


# ---------------------------------------------------------------------------
# 1. Testes de Segurança e Controle de Acesso
# ---------------------------------------------------------------------------

def test_whitelist_authorized_contact():
    """Valida se contatos cadastrados no .env são autorizados corretamente com seu papel."""
    authorized_number = "+5511999990001"
    is_auth, role, msg = WhitelistValidator.authorize_or_reject(authorized_number)
    assert is_auth is True
    assert role == RecipientRole.ANALYST
    assert "autorizado" in msg.lower()


def test_whitelist_unauthorized_contact():
    """Valida se contatos invasores ou desconhecidos são barrados sumariamente."""
    unauthorized_number = "+5511988887777"
    is_auth, role, msg = WhitelistValidator.authorize_or_reject(unauthorized_number)
    assert is_auth is False
    assert role == RecipientRole.UNAUTHORIZED
    assert "restrito" in msg.lower()


def test_lgpd_sanitizer_removes_sensitive_data():
    """Valida se CPFs e números de cartões são mascarados antes do processamento."""
    texto_com_dados = (
        "Olá, meu CPF é 123.456.789-00 e meu cartão corporativo é 4111 2222 3333 4444. "
        "Como funciona o reembolso de almoço?"
    )
    texto_limpo = sanitizar_texto_lgpd(texto_com_dados)
    assert "123.456.789-00" not in texto_limpo
    assert "[CPF_REMOVIDO]" in texto_limpo
    assert "4111 2222 3333 4444" not in texto_limpo
    assert "[CARTAO_REMOVIDO]" in texto_limpo


def test_remover_caminhos_locais_preserva_chamados():
    """Valida expurgo de caminhos físicos locais mantendo rastreabilidade do chamado."""
    texto = "Script salvo em D:\\Projetos\\query.sql para atender ao chamado #2026059303."
    limpo = remover_caminhos_locais(texto)
    assert "D:\\Projetos" not in limpo
    assert "[CAMINHO_INTERNO]" in limpo
    assert "#2026059303" in limpo


# ---------------------------------------------------------------------------
# 2. Testes de Motor Vetorial e RAG
# ---------------------------------------------------------------------------

def test_embedding_engine_cosine_similarity():
    """Valida cálculo de similaridade vetorial matemática."""
    v1 = EmbeddingEngine.get_embedding("Política de trabalho remoto e home office")
    v2 = EmbeddingEngine.get_embedding("Regras para home office e trabalho à distância")
    v3 = EmbeddingEngine.get_embedding("Receita culinária de bolo de chocolate com morango")

    sim_relacionada = EmbeddingEngine.cosine_similarity(v1, v2)
    sim_alienigena = EmbeddingEngine.cosine_similarity(v1, v3)

    assert sim_relacionada > sim_alienigena
    assert sim_relacionada >= 0.30


def test_knowledge_retriever_chunking_and_search():
    """Valida segmentação automática de Markdown e busca semântica."""
    md_sample = (
        "# Manual de Governança\n\n"
        "## Horário de Trabalho\n"
        "A jornada corporativa diária é de 8 horas com intervalo de 1 hora de almoço.\n\n"
        "## Estacionamento\n"
        "Vagas reservadas exclusivamente para veículos elétricos e diretoria no subsolo 2."
    )
    retriever = KnowledgeRetriever()
    count = retriever.ingest_markdown(md_sample, source_name="teste_doc.md")
    assert count >= 2

    # Consulta por tema existente
    results = retriever.retrieve("Qual é a jornada de trabalho diária?", threshold=0.20)
    assert len(results) > 0
    assert "Horário de Trabalho" in results[0].title


def test_anti_hallucination_guard_rejection():
    """Valida acionamento do guardrail anti-alucinação quando não há lastro factual."""
    synthesis = AntiHallucinationGuard.verify_and_synthesize(
        query="Como consertar uma nave espacial?",
        retrieved_chunks=[],
        role=RecipientRole.OPERATIONAL
    )
    assert synthesis["grounded"] is False
    assert synthesis["guardrail_status"] == "REJECTED_LOW_SIMILARITY"
    assert "abrir um chamado" in synthesis["answer"].lower()


# ---------------------------------------------------------------------------
# 3. Testes End-to-End da API FastAPI
# ---------------------------------------------------------------------------

def test_api_health_check():
    """Valida endpoint /health."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["total_authorized_contacts"] > 0
        assert data["total_indexed_chunks"] > 0


def test_api_webhook_unauthorized_rejection():
    """Valida interceptação de remetente não autorizado no endpoint de webhook."""
    with TestClient(app) as client:
        payload = {
            "sender_id": "+5500999999999",
            "message_text": "Qual o valor do reembolso de alimentação?",
            "channel": "whatsapp_webhook"
        }
        response = client.post("/webhook/message", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["is_authorized"] is False
        assert data["status"] == "UNAUTHORIZED_REJECTED"
        assert "Acesso restrito" in data["response_text"]


def test_api_webhook_authorized_success():
    """Valida fluxo completo para usuário autorizado com resposta factual fundamentada."""
    with TestClient(app) as client:
        payload = {
            "sender_id": "+5511999990001",
            "message_text": "Qual é o limite de valor para reembolso de alimentação em viagens?",
            "channel": "whatsapp_webhook"
        }
        response = client.post("/webhook/message", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["is_authorized"] is True
        assert data["status"] == "AUTHORIZED_SUCCESS"
        assert data["role_applied"] == "ANALYST"
        assert data["mark_conversation_as_unread"] is True
        assert "R$ 85,00" in data["response_text"] or "refeição principal" in data["response_text"]
        assert len(data["sources"]) > 0


def test_api_webhook_human_answered_grace_period():
    """Valida que o robô aborta se o responsável respondeu manualmente nos 5 minutos."""
    with TestClient(app) as client:
        payload = {
            "sender_id": "+5511999990001",
            "message_text": "@responsavel como funciona o reembolso?",
            "channel": "whatsapp_group",
            "is_group": True,
            "mentions_maintainer": True,
            "maintainer_answered_in_window": True
        }
        response = client.post("/webhook/message", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ABORTED_HUMAN_ANSWERED"
        assert data["response_text"] == ""


def test_api_webhook_noise_ignored():
    """Valida que confirmações simples ('ok', 'obrigado') são ignoradas sem disparar IA."""
    with TestClient(app) as client:
        payload = {
            "sender_id": "+5511999990001",
            "message_text": "ok, muito obrigado!",
            "channel": "whatsapp_webhook"
        }
        response = client.post("/webhook/message", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "IGNORED_NON_ACTIONABLE"


def test_api_webhook_out_of_scope_question():
    """Valida bloqueio factual quando usuário autorizado pergunta sobre tema ausente no manual."""
    with TestClient(app) as client:
        payload = {
            "sender_id": "+5511999990001",
            "message_text": "Qual é a velocidade máxima permitida para motos aquáticas no lago?",
            "channel": "whatsapp_webhook"
        }
        response = client.post("/webhook/message", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["is_authorized"] is True
        assert data["status"] == "AUTHORIZED_OUT_OF_SCOPE"
        assert "não foi localizada" in data["response_text"].lower()
