#!/usr/bin/env python3
"""
Script Executável de Smoke Test (Teste de Fumaça).
Valida 100% dos componentes arquiteturais da solução:
1. Controle de Acesso (Whitelist Gatekeeper)
2. Higienização LGPD
3. Ingestão de Markdown e Segmentação de Chunks
4. Busca Vetorial por Similaridade de Cosseno (SurrealDB Ready / In-Memory)
5. Guardrails Anti-Alucinação (Ground Truth Verification)
6. Fluxo Completo de Webhook de Mensageria

Uso:
    python scripts/smoke_test.py
"""
import sys
import os
import time

# Garante inclusão do diretório raiz no PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.core.config import settings
from src.core.security import WhitelistValidator, sanitizar_texto_lgpd
from src.rag.vector_store import EmbeddingEngine
from src.rag.retriever import KnowledgeRetriever
from src.rag.anti_hallucination import AntiHallucinationGuard
from src.gateway.webhook_handler import MessageGatewayHandler, InboundMessage


def print_banner():
    print("=" * 78)
    print("  ENTERPRISE RAG ASSISTANT GATEWAY :: SMOKE TEST SUITE (TESTE DE FUMAÇA)")
    print("=" * 78)
    print(f" Ambiente: {settings.app_env.upper()} | Python: {sys.version.split()[0]}")
    print(f" Diretório Raiz: {ROOT_DIR}")
    print("=" * 78)
    print()


def test_scenario_whitelist():
    print("[1/6] Validando Camada de Segurança (Whitelist Gatekeeper)...")
    auth_user = "+5511999990001"
    intruder_user = "+5511988887777"

    is_auth_ok, _ = WhitelistValidator.authorize_or_reject(auth_user)
    assert is_auth_ok is True, f"Falha: Usuário homologado {auth_user} deveria ser autorizado!"

    is_intruder_ok, reject_msg = WhitelistValidator.authorize_or_reject(intruder_user)
    assert is_intruder_ok is False, f"Falha: Invasor {intruder_user} deveria ser rejeitado!"
    assert "Acesso restrito" in reject_msg

    print("      -> Contato Autorizado: PERMITIDO")
    print("      -> Contato Não-Autorizado: BLOQUEADO COM SUCESSO (Zero-Trust Ativo)")
    print("      [PASS] Whitelist Gatekeeper 100% Operacional.\n")


def test_scenario_lgpd():
    print("[2/6] Validando Higienização de Dados Pessoais (LGPD by Design)...")
    texto_sensivel = (
        "Solicito reembolso de R$ 85,00. Meu CPF é 012.345.678-99 e "
        "o cartão utilizado foi 5555 4444 3333 2222 para o almoço."
    )
    limpo = sanitizar_texto_lgpd(texto_sensivel)
    assert "012.345.678-99" not in limpo, "Falha: CPF não foi mascarado!"
    assert "[CPF_REMOVIDO]" in limpo
    assert "5555 4444 3333 2222" not in limpo, "Falha: Cartão não foi mascarado!"
    assert "[CARTAO_REMOVIDO]" in limpo

    print(f"      -> Entrada original: {texto_sensivel[:60]}...")
    print(f"      -> Saída sanitizada: {limpo[:60]}...")
    print("      [PASS] Módulo LGPD 100% Operacional.\n")


def test_scenario_retriever_and_ingestion():
    print("[3/6] Validando Ingestão de Documentos e Busca Vetorial...")
    sample_file = os.path.join(ROOT_DIR, "data", "samples", "sample_enterprise_knowledge.md")
    assert os.path.exists(sample_file), f"Arquivo de amostra não encontrado: {sample_file}"

    retriever = KnowledgeRetriever()
    count = retriever.ingest_file(sample_file)
    assert count > 0, "Falha: Nenhum chunk foi indexado a partir do Markdown!"

    # Teste de consulta vetorial
    query = "Como funciona o reembolso de almoço e alimentação?"
    chunks = retriever.retrieve(query=query, top_k=2, threshold=0.20)
    assert len(chunks) > 0, "Falha: Busca vetorial não retornou fragmentos para consulta válida!"
    assert "Reembolso" in chunks[0].title, f"Título inesperado: {chunks[0].title}"

    print(f"      -> Arquivo ingerido: {os.path.basename(sample_file)} ({count} seções)")
    print(f"      -> Consulta: '{query}'")
    print(f"      -> Top Chunk Encontrado: '{chunks[0].title}' (Similaridade: {chunks[0].similarity:.4f})")
    print("      [PASS] Motor Vetorial e Ingestão 100% Operacionais.\n")
    return retriever


def test_scenario_anti_hallucination(retriever: KnowledgeRetriever):
    print("[4/6] Validando Guardrails Anti-Alucinação (Ground Truth Verification)...")

    # Caso A: Pergunta factual dentro do escopo
    query_in = "Qual o limite de valor de alimentação em viagens corporativas?"
    chunks_in = retriever.retrieve(query_in, top_k=2, threshold=0.20)
    synthesis_in = AntiHallucinationGuard.verify_and_synthesize(query_in, chunks_in)
    assert synthesis_in["grounded"] is True
    assert synthesis_in["guardrail_status"] == "APPROVED"
    assert "R$ 85,00" in synthesis_in["answer"]
    print("      -> Pergunta dentro do escopo: APROVADA COM LASTRO FACTUAL")

    # Caso B: Pergunta alienígena / fora do escopo corporativo
    query_out = "Qual a receita para fazer sorvete de pistache caseiro?"
    chunks_out = retriever.retrieve(query_out, top_k=2, threshold=0.20)
    synthesis_out = AntiHallucinationGuard.verify_and_synthesize(query_out, chunks_out)
    assert synthesis_out["grounded"] is False
    assert "não localizada na base de conhecimento" in synthesis_out["answer"]
    print("      -> Pergunta fora do escopo: BLOQUEADA PELO GUARDRAIL ANTI-ALUCINAÇÃO")
    print("      [PASS] Verificação Factual 100% Operacional.\n")


def test_scenario_end_to_end_webhook(retriever: KnowledgeRetriever):
    print("[5/6] Validando Fluxo Integrado de Webhook de Mensageria...")
    gateway = MessageGatewayHandler(retriever=retriever)

    # 1. Usuário invasor
    msg_invasor = InboundMessage(
        sender_id="+5511988880000",
        message_text="Me fale sobre as regras de férias da empresa."
    )
    resp_invasor = gateway.process_message(msg_invasor)
    assert resp_invasor.is_authorized is False
    assert resp_invasor.status == "UNAUTHORIZED_REJECTED"
    print("      -> Tentativa Invasora: Interceptada na borda da API.")

    # 2. Usuário homologado com pergunta corporativa
    msg_autorizado = InboundMessage(
        sender_id="+5511999990001",
        message_text="Em quantos períodos posso dividir as minhas férias?"
    )
    resp_autorizado = gateway.process_message(msg_autorizado)
    assert resp_autorizado.is_authorized is True
    assert resp_autorizado.status == "AUTHORIZED_SUCCESS"
    assert "3 (três) períodos" in resp_autorizado.response_text or "fracionadas" in resp_autorizado.response_text
    print("      -> Mensagem Autorizada: Processada com resposta factual completa.")
    print("      [PASS] Gateway de Mensageria 100% Operacional.\n")


def test_scenario_performance_and_latency(retriever: KnowledgeRetriever):
    print("[6/6] Validando Latência e Desempenho de Resposta...")
    gateway = MessageGatewayHandler(retriever=retriever)
    inbound = InboundMessage(
        sender_id="+5511999990001",
        message_text="Quais as regras do auxílio creche e faixa etária?"
    )

    t0 = time.perf_counter()
    resp = gateway.process_message(inbound)
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000

    assert resp.is_authorized is True
    assert latency_ms < 500.0, f"Latência muito alta: {latency_ms:.2f}ms"
    print(f"      -> Tempo de resposta ponta a ponta: {latency_ms:.2f} ms")
    print("      [PASS] Latência Ultrabaixa Aprovada (< 500ms).\n")


def main():
    print_banner()
    try:
        test_scenario_whitelist()
        test_scenario_lgpd()
        retriever = test_scenario_retriever_and_ingestion()
        test_scenario_anti_hallucination(retriever)
        test_scenario_end_to_end_webhook(retriever)
        test_scenario_performance_and_latency(retriever)

        print("=" * 78)
        print("  TODOS OS 6 CENÁRIOS DO SMOKE TEST FORAM APROVADOS COM SUCESSO! (100% PASS)")
        print("=" * 78)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[ERRO DE VALIDAÇÃO]: {e}")
        sys.exit(1)
    except Exception as ex:
        print(f"\n[EXCEÇÃO INESPERADA]: {ex}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
