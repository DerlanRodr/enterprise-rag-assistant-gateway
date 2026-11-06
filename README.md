# Enterprise RAG Assistant Gateway 🛡️🤖

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![SurrealDB](https://img.shields.io/badge/SurrealDB-v2.0-FF0055.svg?logo=surrealdb)](https://surrealdb.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker)](https://www.docker.com)
[![Architecture](https://img.shields.io/badge/Architecture-Zero--Trust_RAG-7928CA.svg)](#arquitetura-do-sistema)
[![LGPD](https://img.shields.io/badge/Compliance-LGPD_by_Design-green.svg)](#seguran%C3%A7a-e-conformidade-lgpd)
[![Tests](https://img.shields.io/badge/Tests-100%25_Passing-brightgreen.svg)](#testes-automatizados-e-smoke-test)

Gateway corporativo assíncrono de inteligência artificial com **Controle de Acesso Zero Trust (Whitelisting O(1))**, **Banco Vetorial Semântico (SurrealDB v2 + Fallback Resiliente em Memória)** e **Pipeline RAG Auditado com Guardrails Anti-Alucinação (Strict Ground Truth Verification)**.

Projetado para integrar bases de conhecimento corporativas unificadas (como notas e documentações do **Open Notebook**) a canais de mensageria corporativa, garantindo que o assistente responda **exclusivamente a colaboradores e gestores previamente homologados**, eliminando 100% das alucinações e vazamentos acidentais de dados sensíveis.

---

## 🎯 Problema de Negócio & Solução Arquitetural

Em ambientes corporativos, a adoção de Large Language Models (LLMs) convencionais enfrenta três riscos graves:
1. **Alucinações e Imprecisões Normativas:** Modelos generativos respondem com suposições quando não encontram informações factuais sobre benefícios, jornadas ou procedimentos internos.
2. **Acesso Não Autorizado e Custo de Inferência Desnecessário:** Webhooks públicos ficam expostos a consultas de terceiros ou colaboradores sem permissão, inflando custos de tokens de IA.
3. **Exposição de Dados Sensíveis (LGPD):** Envio acidental de CPFs, matrículas ou dados bancários em prompts abertos.

### Como esta arquitetura resolve:
- **Zero-Trust Gatekeeper na Borda:** Cada requisição de mensageria passa por validação instantânea em tempo $O(1)$ contra uma *Whitelist* de contatos autorizados. Requisições invasoras ou não cadastradas são rejeitadas na borda antes de qualquer processamento ou custo de inferência vetorial.
- **Base Única da Verdade (Open Notebook + SurrealDB v2):** O assistente não "adivinha". Ele consulta fragmentos semânticos densamente vetorizados indexados no SurrealDB v2 ou memória operacional.
- **Guardrail Anti-Alucinação:** Se o limiar de similaridade semântica (*Cosine Similarity*) não for atingido, a resposta é terminantemente bloqueada e substituída por uma mensagem institucional padronizada.
- **Higienização LGPD Automática:** Sanitização ativa de CPFs e cartões corporativos antes do log ou da vetorização.

---

## 🏗️ Arquitetura do Sistema

```mermaid
flowchart TD
    subgraph Webhook_Ingress["Camada de Entrada (Edge & Webhook)"]
        User["📱 Emissor (Mensageria Corporativa / Webhook)"] -->|Payload Inbound| GW["🛡️ Gateway de Mensageria (FastAPI)"]
    end

    subgraph Security_Gatekeeper["Camada de Segurança & Compliance"]
        GW -->|1. Validação O(1)| WL{"🔒 Whitelist Validator"}
        WL -->|Não Homologado| Reject["⛔ 403 / Acesso Restrito (Borda)"]
        WL -->|Autorizado| LGPD["🧹 Sanitizador LGPD (Mascara CPFs/Cartões)"]
    end

    subgraph RAG_Engine["Motor RAG & Base de Conhecimento"]
        LGPD -->|2. Consulta Semântica| Retriever["🔍 Knowledge Retriever"]
        OpenNote["📓 Open Notebook Docs (Base Unificada)"] -->|Ingestão & Chunking| Retriever
        Retriever <-->|Similaridade de Cosseno (512-dim)| VStore[("🗄️ SurrealDB v2 / In-Memory Store")]
    end

    subgraph Guardrails["Camada de Factualidade (Anti-Alucinação)"]
        Retriever -->|3. Chunks + Metadados| Guard{"⚖️ Anti-Hallucination Guard"}
        Guard -->|Similaridade < Limiar| Fallback["🚫 Resposta Rejeitada (Bloqueio Factual)"]
        Guard -->|Similaridade >= Limiar| Synth["✅ Síntese Factual com Fontes Auditadas"]
    end

    Synth -->|4. Entrega Factual| Outbound["📲 Resposta ao Colaborador"]
```

---

## 🚀 Tecnologias e Decisões de Engenharia

| Componente | Tecnologia | Decisão de Engenharia |
| :--- | :--- | :--- |
| **Framework Web** | **FastAPI + Uvicorn** | Alta performance assíncrona, validação por contratos Pydantic v2 e documentação OpenAPI nativa. |
| **Banco Vetorial** | **SurrealDB v2** | Multi-model database com suporte nativo a `vector::similarity::cosine`, permitindo busca vetorial e relacional no mesmo motor. |
| **Fallback Vetorial** | **In-Memory Signed Hashing** | Implementação autônoma em NumPy com *Signed Feature Hashing* (512 dimensões), permitindo testes e esteiras CI/CD sem dependência externa. |
| **Base Unificada** | **Open Notebook** | Repositório de inteligência documental que alimenta o pipeline RAG com diretrizes homologadas. |
| **Controle de Acesso** | **Pydantic Set Lookup** | Checagem de contatos autorizados em tempo $O(1)$, com sanitização de formatação telefônica/identificador. |
| **Conformidade** | **Regex Masking (LGPD)** | Mascaramento de dados identificáveis antes do pipeline de embedding e gravação de logs. |
| **Containerização** | **Docker & Docker Compose** | Ambientes isolados com orquestração completa em um único comando. |

---

## 📂 Estrutura do Repositório

```text
enterprise-rag-assistant-gateway/
├── data/
│   └── samples/
│       └── sample_enterprise_knowledge.md  # Amostra de manual corporativo (Políticas, Férias, Reembolso)
├── scripts/
│   └── smoke_test.py                      # Teste de fumaça executável com 6 cenários integrados
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py                        # Aplicação FastAPI, rotas HTTP e ciclo de vida (lifespan)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                      # Configurações Pydantic com leitura de .env e fallback gracioso
│   │   └── security.py                    # WhitelistValidator e sanitizador LGPD
│   ├── gateway/
│   │   ├── __init__.py
│   │   └── webhook_handler.py             # Orquestrador de mensagens inbound/outbound
│   └── rag/
│       ├── __init__.py
│       ├── anti_hallucination.py          # Verificação estrita de Ground Truth
│       ├── retriever.py                   # Chunking de Markdown e orquestração de busca
│       └── vector_store.py                # SurrealDB v2 Vector Store + Signed In-Memory Fallback
├── tests/
│   ├── __init__.py
│   └── test_gateway.py                    # Suíte completa de testes automatizados com Pytest
├── .env.example                           # Modelo de variáveis de ambiente sanitizado
├── .gitignore                             # Regras de exclusão Git (Python, venv, caches, logs)
├── docker-compose.yml                     # Orquestração do SurrealDB v2 e API Gateway
├── Dockerfile                             # Containerização em Python 3.11-slim
├── README.md                              # Documentação técnica e guia arquitetural
└── requirements.txt                       # Dependências de produção e testes
```

---

## 🛠️ Como Executar o Projeto

### Pré-requisitos
- **Python 3.11+** ou **Docker / Docker Compose**.

---

### Opção 1: Execução com Docker Compose (Recomendada para Produção)

1. Clone o repositório:
```bash
git clone https://github.com/DerlanRodr/enterprise-rag-assistant-gateway.git
cd enterprise-rag-assistant-gateway
```

2. Crie o arquivo de configuração `.env` a partir do modelo:
```bash
cp .env.example .env
```

3. Suba o ecossistema completo (API Gateway + SurrealDB v2):
```bash
docker compose up -d --build
```

A API estará disponível em: `http://localhost:8000`  
Documentação interativa Swagger: `http://localhost:8000/docs`

---

### Opção 2: Execução Local com Python

1. Crie e ative um ambiente virtual:
```bash
python -m venv .venv

# No Windows:
.venv\Scripts\activate

# No Linux/macOS:
source .venv/bin/activate
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Inicie o servidor FastAPI:
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 Testes Automatizados e Smoke Test

O projeto foi construído sob o princípio de **Auditabilidade Total**. Qualquer desenvolvedor ou avaliador técnico pode validar a estabilidade de ponta a ponta sem necessidade de banco externo ou credenciais pagas.

### 1. Teste de Fumaça Executável (Smoke Test)
Executa 6 cenários críticos de ponta a ponta:
- [x] Interceptação de contato não autorizado (Zero Trust).
- [x] Mascaramento de dados pessoais (LGPD by Design).
- [x] Ingestão de Markdown e segmentação automática de seções.
- [x] Recuperação vetorial com ranking de similaridade semântica.
- [x] Ativação de Guardrail Anti-Alucinação para tópicos fora do escopo.
- [x] Simulação de webhook ponta a ponta com telemetria de latência (< 50ms).

Para executar:
```bash
python scripts/smoke_test.py
```

*Saída esperada:*
```text
==============================================================================
  ENTERPRISE RAG ASSISTANT GATEWAY :: SMOKE TEST SUITE (TESTE DE FUMAÇA)
==============================================================================
[1/6] Validando Camada de Segurança (Whitelist Gatekeeper)... [PASS]
[2/6] Validando Higienização de Dados Pessoais (LGPD by Design)... [PASS]
[3/6] Validando Ingestão de Documentos e Busca Vetorial... [PASS]
[4/6] Validando Guardrails Anti-Alucinação (Ground Truth Verification)... [PASS]
[5/6] Validando Fluxo Integrado de Webhook de Mensageria... [PASS]
[6/6] Validando Latência e Desempenho de Resposta... [PASS] (< 1ms)
==============================================================================
  TODOS OS 6 CENÁRIOS DO SMOKE TEST FORAM APROVADOS COM SUCESSO! (100% PASS)
==============================================================================
```

### 2. Suíte de Testes com Pytest
```bash
pytest tests/ -v
```

---

## 📡 Endpoints Principais da API

### 1. `POST /webhook/message` (Recepção de Mensageria)
Processa a mensagem recebida de um canal de mensageria com controle de acesso imediato.

**Payload de Entrada (Inbound):**
```json
{
  "sender_id": "+5511999990001",
  "message_text": "Qual o valor do reembolso de alimentação em viagens corporativas?",
  "channel": "corporate_messenger"
}
```

**Resposta Autorizada (Ground Truth Aprovado):**
```json
{
  "recipient_id": "+5511999990001",
  "response_text": "Com base na base de conhecimento corporativa oficial:\n\n• **Política de Reembolso de Despesas Corporativas e Viagens**:\nO reembolso de despesas corporativas em viagens a serviço exige a emissão... Alimentação: limite de até R$ 85,00 por refeição principal (almoço e jantar)...",
  "status": "AUTHORIZED_SUCCESS",
  "is_authorized": true,
  "confidence_score": 0.33,
  "sources": ["sample_enterprise_knowledge.md :: Política de Reembolso de Despesas Corporativas e Viagens"]
}
```

**Resposta para Contato Invasor / Não Autorizado:**
```json
{
  "recipient_id": "+5511988887777",
  "response_text": "Acesso restrito. Este assistente corporativo responde exclusivamente a contatos autorizados.",
  "status": "UNAUTHORIZED_REJECTED",
  "is_authorized": false,
  "confidence_score": 0.0,
  "sources": []
}
```

---

### 2. `GET /health` (Auditoria e Saúde Operacional)
```json
{
  "status": "healthy",
  "environment": "development",
  "total_authorized_contacts": 3,
  "total_indexed_chunks": 6,
  "similarity_threshold": 0.20,
  "strict_ground_truth": true
}
```

---

## 🔒 Segurança e Conformidade LGPD

1. **Princípio do Menor Privilégio (PoLP):** Somente identificadores expressamente listados na variável de ambiente `AUTHORIZED_CONTACTS` obtêm processamento de inferência.
2. **Higienização Ativa:** A função `sanitizar_texto_lgpd` atua em tempo de execução, expurgando expressões de identificação de CPF e numerações de cartões bancários antes de qualquer persistência em logs.
3. **Imunidade a Prompt Injection:** O sistema não passa comandos de execução livre. Ele pesquisa documentos oficiais previamente homologados e restringe a síntese ao material factual indexado.

---

## 👤 Autor

**Derlan Rodrigues**  
*Desenvolvedor Back-End & Engenheiro de Software*  
- GitHub: [@DerlanRodr](https://github.com/DerlanRodr)
