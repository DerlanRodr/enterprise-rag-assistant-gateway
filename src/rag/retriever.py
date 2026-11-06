"""
Módulo de Recuperação de Conhecimento (Knowledge Retriever).
Responsável por ingestão de documentos estruturados (Markdown / Open Notebook),
chunking contextual e busca semântica na base de conhecimento corporativa.
"""
import re
import os
import logging
from typing import List, Optional
from src.core.config import settings
from src.core.security import remover_caminhos_locais
from src.rag.vector_store import (
    DocumentChunk,
    VectorStore,
    InMemoryVectorStore,
    SurrealDBVectorStore
)

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """
    Orquestrador de recuperação semântica de conhecimento corporativo.
    """
    def __init__(self, store: Optional[VectorStore] = None):
        if store is None:
            self._in_memory = InMemoryVectorStore()
            self.store: VectorStore = SurrealDBVectorStore(in_memory_fallback=self._in_memory)
        else:
            self.store = store

    def ingest_markdown(self, markdown_text: str, source_name: str = "manual_ingest") -> int:
        """
        Segmenta documentos Markdown com base em títulos e seções (H1, H2, H3),
        gerando fragmentos contextuais de alta coerência semântica.
        """
        if not markdown_text or not markdown_text.strip():
            return 0

        # Regex para quebrar por seções H2 (##) ou H3 (###)
        sections = re.split(r"\n(?=##\s+)", markdown_text.strip())
        chunks: List[DocumentChunk] = []

        for idx, section in enumerate(sections):
            lines = section.strip().splitlines()
            if not lines:
                continue

            first_line = lines[0].strip()
            title = re.sub(r"^#+\s*", "", first_line)
            content = "\n".join(lines[1:]).strip() if len(lines) > 1 else first_line

            if not content:
                content = title

            # Higienização de infraestrutura: remove caminhos físicos locais da máquina
            content = remover_caminhos_locais(content)

            # Extração simples de tags por palavras-chave
            tags = [w.lower() for w in re.findall(r"\b[A-Za-zÀ-ÿ]{4,}\b", title)]

            chunk_id = f"{source_name}_chunk_{idx+1}"
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    title=title,
                    content=content,
                    source=source_name,
                    tags=tags[:5]
                )
            )

        count = self.store.add_chunks(chunks)
        logger.info(f"Ingestão concluída com sucesso: {count} chunks indexados a partir de '{source_name}'.")
        return count

    def ingest_file(self, file_path: str) -> int:
        """Lê e ingere um arquivo de documentação física do disco."""
        if not os.path.exists(file_path):
            logger.warning(f"Arquivo não localizado para ingestão: {file_path}")
            return 0

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        filename = os.path.basename(file_path)
        return self.ingest_markdown(content, source_name=filename)

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None
    ) -> List[DocumentChunk]:
        """
        Executa busca semântica para recuperar os fragmentos mais relevantes.
        """
        k = top_k if top_k is not None else settings.max_chunks_per_query
        th = threshold if threshold is not None else settings.similarity_threshold
        return self.store.search(query=query, top_k=k, threshold=th)
