#!/usr/bin/env python3
"""
Script Executável de Smoke Test (Teste de Fumaça).
Valida 100% dos componentes operacionais e arquiteturais da solução:
1. Controle de Acesso e Perfis (Whitelist & RBAC: Analista, Gestor, Operacional)
2. Higienização LGPD e Expurgo de Caminhos Físicos da Máquina
3. Ingestão de Markdown e Segmentação de Chunks
4. Guardrails Anti-Alucinação e Respostas Adaptativas por Perfil
5. Fluxo de Webhook com Regras de Negócio Reais:
   - Janela de Carência de 5 Minutos (Human-in-the-Loop Debounce)
   - Filtro de Ruído (ignora 'ok', reações)
   - Filtro de Grupos Técnicos (exige menção direta)
   - Marcação como Não Lida para Auditoria Humana Posterior
6. Latência e Desempenho Ultrarrápido

Uso:
    python scripts/smoke_test.py
"""
import sys
import os
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.core.config import settings
from src.core.security import WhitelistValidator, RecipientRole, sanitizar_texto_lgpd, remover_caminhos_locais
from src.rag.vector_store import EmbeddingEngine
from src.rag.retriever import KnowledgeRetriever
from src.rag.anti_hallucination import AntiHallucinationGuard
from src.gateway.webhook_handler import MessageGatewayHandler, InboundMessage


def print_banner():
    print("=" * 78)
    print("  ENTERPRISE RAG ASSISTANT GATEWAY :: SMOKE TEST SUITE (OPERAÇÃO REAL)")
    print("=" * 78)
    print(f" Ambiente: {settings.app_env.upper()} | Python: {sys.version.split()[0]}")
    print(f" Diretório Raiz: {ROOT_DIR}")
    print("=" * 78)
    print()


def test_scenario_whitelist_and_rbac():
    print("[1/6] Validando Camada de Segurança (Whitelist & RBAC por Perfil)...")
    analyst_user = "+5511999990001"
    manager_user = "+5511999990002"
    operational_user = "+5585999990003"
    intruder_user = "+5511988887777"

    # 1. Analista
    is_auth, role, _ = WhitelistValidator.authorize_or_reject(analyst_user)
    assert is_auth is True and role == RecipientRole.ANALYST
    print(f"      -> {analyst_user}: PERMITIDO [Perfil: {role.value}]")

    # 2. Gestor
    is_auth, role, _ = WhitelistValidator.authorize_or_reject(manager_user)
    assert is_auth is True and role == RecipientRole.MANAGER
    print(f"      -> {manager_user}: PERMITIDO [Perfil: {role.value}]")

    # 3. Operacional
    is_auth, role, _ = WhitelistValidator.authorize_or_reject(operational_user)
    assert is_auth is True and role == RecipientRole.OPERATIONAL
    print(f"      -> {operational_user}: PERMITIDO [Perfil: {role.value}]")

    # 4. Invasor
    is_auth, role, reject_msg = WhitelistValidator.authorize_or_reject(intruder_user)
    assert is_auth is False and role == RecipientRole.UNAUTHORIZED
    assert "Acesso restrito" in reject_msg
    print(f"      -> {intruder_user}: BLOQUEADO [Zero Trust Ativo]")
    print("      [PASS] Whitelist e Perfis RBAC 100% Operacionais.\n")


def test_scenario_lgpd_and_path_sanitization():
    print("[2/6] Validando Higienização LGPD e Expurgo de Caminhos Locais...")
    # A. Mascaramento LGPD
    texto_sensivel = "Reembolso com CPF 012.345.678-99 e cartão corporativo 5555 4444 3333 2222."
    limpo = sanitizar_texto_lgpd(texto_sensivel)
    assert "012.345.678-99" not in limpo and "[CPF_REMOVIDO]" in limpo
    assert "5555 4444 3333 2222" not in limpo and "[CARTAO_REMOVIDO]" in limpo

    # B. Expurgo de caminhos locais (mantendo número de chamado #2026...)
    texto_doc = "Arquivo em D:\\Visual Code\\scripts\\consulta.py gerado para o Chamado #2026059303."
    doc_limpo = remover_caminhos_locais(texto_doc)
    assert "D:\\Visual Code" not in doc_limpo and "[CAMINHO_INTERNO]" in doc_limpo
    assert "#2026059303" in doc_limpo  # Rastreabilidade mantida!

    print("      -> Dados Pessoais (CPF/Cartão): MASCARADOS")
    print("      -> Caminhos da Máquina: EXPURGADOS (Rastreabilidade de chamado preservada)")
    print("      [PASS] Módulos de Higienização e LGPD 100% Operacionais.\n")


def test_scenario_retriever_and_ingestion():
    print("[3/6] Validando Ingestão de Documentos e Busca Vetorial...")
    sample_file = os.path.join(ROOT_DIR, "data", "samples", "sample_enterprise_knowledge.md")
    assert os.path.exists(sample_file), f"Arquivo não encontrado: {sample_file}"

    retriever = KnowledgeRetriever()
    count = retriever.ingest_file(sample_file)
    assert count > 0

    query = "Como funciona o reembolso de almoço e alimentação?"
    chunks = retriever.retrieve(query=query, top_k=2, threshold=0.20)
    assert len(chunks) > 0
    assert "Reembolso" in chunks[0].title

    print(f"      -> Chunks Indexados: {count} seções")
    print(f"      -> Busca Vetorial: Top chunk '{chunks[0].title}' (Similaridade: {chunks[0].similarity:.4f})")
    print("      [PASS] Ingestão e Motor Vetorial 100% Operacionais.\n")
    return retriever


def test_scenario_anti_hallucination_and_roles(retriever: KnowledgeRetriever):
    print("[4/6] Validando Respostas Adaptativas por Perfil e Anti-Alucinação...")

    # Perfil Analista: Detalhes técnicos
    chunks = retriever.retrieve("Como funciona o reembolso de almoço?", top_k=1, threshold=0.20)
    resp_analista = AntiHallucinationGuard.verify_and_synthesize("reembolso", chunks, role=RecipientRole.ANALYST)
    assert resp_analista["grounded"] is True
    assert "[Detalhamento Técnico Documentado]" in resp_analista["answer"]
    print("      -> Perfil Analista: Resposta técnica detalhada aprovada.")

    # Perfil Gestor: Linguagem executiva e aviso LGPD
    resp_gestor = AntiHallucinationGuard.verify_and_synthesize("reembolso", chunks, role=RecipientRole.MANAGER)
    assert resp_gestor["grounded"] is True
    assert "LGPD" in resp_gestor["answer"]
    print("      -> Perfil Gestor: Resumo executivo com aviso LGPD aprovado.")

    # Pergunta Fora do Escopo para Colaborador: Direcionamento para abertura de chamado
    resp_operacional_fora = AntiHallucinationGuard.verify_and_synthesize(
        "Como consertar um telescópio espacial?", [], role=RecipientRole.OPERATIONAL
    )
    assert resp_operacional_fora["grounded"] is False
    assert "abrir um chamado" in resp_operacional_fora["answer"]
    print("      -> Fora do Escopo: Direcionamento formal para abertura de chamado aprovado.")
    print("      [PASS] Respostas por Perfil e Guardrails 100% Operacionais.\n")


def test_scenario_real_world_webhook(retriever: KnowledgeRetriever):
    print("[5/6] Validando Regras Reais do Webhook (Grace Period, Ruído, Auditoria)...")
    gateway = MessageGatewayHandler(retriever=retriever)

    # 1. Filtro de Ruído: Mensagem 'ok' ou 'valeu' não gera resposta
    msg_ruido = InboundMessage(sender_id="+5511999990001", message_text="ok, muito obrigado!")
    resp_ruido = gateway.process_message(msg_ruido)
    assert resp_ruido.status == "IGNORED_NON_ACTIONABLE"
    print("      -> Filtro de Ruído: 'ok/obrigado' ignorado com sucesso.")

    # 2. Grupo Técnico sem menção direta ao responsável: Não responde
    msg_grupo_sem_tag = InboundMessage(
        sender_id="+5511999990001",
        message_text="Pessoal, alguém sabe as regras de férias?",
        is_group=True,
        mentions_maintainer=False
    )
    resp_sem_tag = gateway.process_message(msg_grupo_sem_tag)
    assert resp_sem_tag.status == "IGNORED_NOT_MENTIONED"
    print("      -> Grupo Técnico sem Tag: Ignorado para evitar spam no grupo.")

    # 3. Janela de Carência de 5 Minutos: Responsável respondeu manualmente -> Robô aborta
    msg_grace = InboundMessage(
        sender_id="+5511999990001",
        message_text="@responsavel como funciona o reembolso?",
        is_group=True,
        mentions_maintainer=True,
        maintainer_answered_in_window=True
    )
    resp_grace = gateway.process_message(msg_grace)
    assert resp_grace.status == "ABORTED_HUMAN_ANSWERED"
    print("      -> Janela de 5 Minutos (Human-in-the-Loop): Resposta manual detectada, robô abortou.")

    # 4. Mensagem Válida: Responde e marca como não lida para auditoria do responsável
    msg_valida = InboundMessage(
        sender_id="+5511999990001",
        message_text="Em quantos períodos posso dividir as minhas férias?",
        is_group=False
    )
    resp_valida = gateway.process_message(msg_valida)
    assert resp_valida.status == "AUTHORIZED_SUCCESS"
    assert resp_valida.mark_conversation_as_unread is True  # Regra de ouro da auditoria
    print("      -> Mensagem Válida: Respondida e marcada como NÃO LIDA para auditoria posterior.")
    print("      [PASS] Regras Operacionais de Mensageria 100% Operacionais.\n")


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
        test_scenario_whitelist_and_rbac()
        test_scenario_lgpd_and_path_sanitization()
        retriever = test_scenario_retriever_and_ingestion()
        test_scenario_anti_hallucination_and_roles(retriever)
        test_scenario_real_world_webhook(retriever)
        test_scenario_performance_and_latency(retriever)

        print("=" * 78)
        print("  TODOS OS 6 CENÁRIOS DO SMOKE TEST FORAM APROVADOS COM SUCESSO! (100% PASS)")
        print("=" * 78)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[ERRO DE VALIDAÇÃO]: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as ex:
        print(f"\n[EXCEÇÃO INESPERADA]: {ex}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
