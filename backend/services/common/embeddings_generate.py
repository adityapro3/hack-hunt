import logging
import os
import warnings
from functools import lru_cache
from typing import TYPE_CHECKING

import httpx

from backend.core.config import get_settings


logger = logging.getLogger(__name__)
_DIMENSION_WARNING_EMITTED: set[tuple[int, int]] = set()
_NOMIC_HF_MODEL = "nomic-ai/nomic-embed-text-v1.5"
_NOMIC_OLLAMA_MODEL = "nomic-embed-text:v1.5"
_OLLAMA_EMBED_NUM_CTX = 4096

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
warnings.filterwarnings("ignore", message=r".*unauthenticated requests to the HF Hub.*")


if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


def _suppress_hf_logs() -> None:
    for logger_name in (
        "sentence_transformers",
        "transformers",
        "huggingface_hub",
        "huggingface_hub.utils._http",
    ):
        logging.getLogger(logger_name).setLevel(logging.ERROR)

    # Suppress HTTP request logs emitted while huggingface_hub resolves model files.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    try:
        from huggingface_hub.utils import disable_progress_bars

        disable_progress_bars()
    except Exception:
        # Some environments may not expose this helper; env var fallback already handles most noise.
        pass


@lru_cache
def _load_model(model_name: str) -> "SentenceTransformer":
    _suppress_hf_logs()
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _generate_huggingface_embedding(text: str) -> list[float]:
    vector = _load_model(_NOMIC_HF_MODEL).encode(text, show_progress_bar=False)
    vector_list = vector.tolist() if hasattr(vector, "tolist") else list(vector)
    return _normalize_dimensions([float(x) for x in vector_list])


def _normalize_dimensions(vector: list[float]) -> list[float]:
    target = get_settings().embedding_vector_dimension
    if len(vector) == target:
        return vector

    if len(vector) > target:
        raise RuntimeError(
            "Embedding dimension mismatch: received "
            f"{len(vector)} dimensions but configured target is {target}. "
            "Increase EMBEDDING_VECTOR_DIMENSION and migrate the database vector column "
            "instead of truncating embeddings."
        )

    warning_key = (len(vector), target)
    if warning_key not in _DIMENSION_WARNING_EMITTED:
        logger.warning("Embedding dimension %s is smaller than target %s; zero-padding", len(vector), target)
        _DIMENSION_WARNING_EMITTED.add(warning_key)
    return vector + [0.0] * (target - len(vector))


def _parse_ollama_embeddings_payload(data: object) -> list[list[float]]:
    if isinstance(data, dict):
        embeddings = data.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            parsed = [
                _normalize_dimensions([float(x) for x in vector])
                for vector in embeddings
                if isinstance(vector, list)
            ]
            if parsed:
                return parsed

        embedding = data.get("embedding")
        if isinstance(embedding, list):
            return [_normalize_dimensions([float(x) for x in embedding])]

    raise RuntimeError("Ollama embedding response did not include embedding vectors")


def generate_embeddings(
    texts: list[str],
    base_url: str | None = None,
) -> list[list[float]]:
    if not texts:
        return []

    resolved_base_url = (base_url or get_settings().embedding_ollama_base_url).rstrip("/")
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{resolved_base_url}/api/embed",
                json={
                    "model": _NOMIC_OLLAMA_MODEL,
                    "input": texts,
                    "options": {"num_ctx": _OLLAMA_EMBED_NUM_CTX},
                },
            )
            response.raise_for_status()
            vectors = _parse_ollama_embeddings_payload(response.json())

        if len(vectors) != len(texts):
            raise RuntimeError(
                f"Ollama returned {len(vectors)} embeddings for {len(texts)} inputs"
            )
        return vectors
    except Exception as exc:
        logger.warning(
            "Ollama embedding failed at %s (%s). Falling back to local HuggingFace model %s",
            resolved_base_url,
            exc,
            _NOMIC_HF_MODEL,
        )
        return [_generate_huggingface_embedding(text) for text in texts]


def generate_embedding(
    text: str,
    base_url: str | None = None,
) -> list[float]:
    vectors = generate_embeddings([text], base_url=base_url)
    if not vectors:
        raise RuntimeError("No embedding vector returned for input text")
    return vectors[0]
