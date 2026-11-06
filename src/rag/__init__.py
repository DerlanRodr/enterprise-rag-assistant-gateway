"""
Módulo RAG (Retrieval-Augmented Generation) com guardrails anti-alucinação.
"""
from src.rag.vector_store import VectorStore, InMemoryVectorStore, DocumentChunk
from src.rag.retriever import KnowledgeRetriever
from src.rag.anti_hallucination import AntiHallucinationGuard

__all__ = [
    "VectorStore",
    "InMemoryVectorStore",
    "DocumentChunk",
    "KnowledgeRetriever",
    "AntiHallucinationGuard",
]
