"""Pinecone long-term conversational memory.

This module stores conversation hints for resolving follow-ups. It must never be
used as the source of sales/profit/customer facts; those come from current data.
"""
import hashlib
import os
import time

from memory.config import (
    MEMORY_ENABLED, PINECONE_API_KEY, PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE, LOCAL_EMBEDDING_MODEL,
)

_model = None
_index = None


def _embedder():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)
    return _model


def _index_for_use():
    global _index
    if _index is not None:
        return _index
    if not PINECONE_API_KEY:
        return None
    from pinecone import Pinecone
    _index = Pinecone(api_key=PINECONE_API_KEY).Index(PINECONE_INDEX_NAME)
    return _index


def _vector(text):
    vector = _embedder().encode(str(text), normalize_embeddings=True).tolist()
    return [float(value) for value in vector]


def remember(conversation_id, role, message, dataset_id=None):
    if not MEMORY_ENABLED or not conversation_id or len(str(message or '').strip()) < 4:
        return False
    try:
        index = _index_for_use()
        if index is None:
            return False
        message = str(message).strip()
        role = str(role or 'unknown').strip().lower()
        scope = 'none' if dataset_id is None else str(dataset_id)
        # Dataset scope in the ID prevents cross-dataset messages overwriting each other.
        vector_id = hashlib.sha256(
            f'{conversation_id}|{scope}|{role}|{message}'.encode('utf-8')
        ).hexdigest()
        metadata = {
            'conversation_id': str(conversation_id),
            'role': role,
            'text': message[:3000],
            'timestamp': int(time.time()),
            'dataset_scope': scope,
        }
        if dataset_id is not None:
            metadata['dataset_id'] = str(dataset_id)
        index.upsert(
            vectors=[{'id': vector_id, 'values': _vector(message), 'metadata': metadata}],
            namespace=PINECONE_NAMESPACE,
        )
        return True
    except Exception as exc:
        print('[MEMORY] Pinecone write skipped:', type(exc).__name__)
        return False


def recall(conversation_id, query, top_k=3, dataset_id=None):
    """Retrieve only relevant records from the same conversation and dataset."""
    if not MEMORY_ENABLED or not conversation_id or not str(query or '').strip():
        return []
    # No dataset means the API has not yet established the data scope. Never mix datasets.
    if dataset_id is None:
        return []
    try:
        index = _index_for_use()
        if index is None:
            return []
        metadata_filter = {
            '$and': [
                {'conversation_id': {'$eq': str(conversation_id)}},
                {'dataset_id': {'$eq': str(dataset_id)}},
            ]
        }
        response = index.query(
            vector=_vector(query),
            top_k=max(1, min(int(top_k), 8)),
            include_metadata=True,
            namespace=PINECONE_NAMESPACE,
            filter=metadata_filter,
        )
        threshold = float(os.getenv('PINECONE_MEMORY_MIN_SCORE', '0.38'))
        matches = []
        for match in (getattr(response, 'matches', None) or []):
            metadata = getattr(match, 'metadata', None) or {}
            text = str(metadata.get('text', '')).strip()
            score = float(getattr(match, 'score', 0) or 0)
            if not text or score < threshold:
                continue
            # Defensively validate scope even after server-side metadata filtering.
            if str(metadata.get('conversation_id', '')) != str(conversation_id):
                continue
            if str(metadata.get('dataset_id', '')) != str(dataset_id):
                continue
            matches.append({
                'role': str(metadata.get('role', 'unknown')),
                'message': text,
                'score': score,
                'dataset_id': str(dataset_id),
            })
        return matches
    except Exception as exc:
        print('[MEMORY] Pinecone recall skipped:', type(exc).__name__)
        return []
