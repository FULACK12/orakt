"""Reusable extraction, embedding and global clustering workflow."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.cluster_review import sign_cluster_preview
from app.clustering import (
    CandidateFeatures,
    EventClusterer,
    candidate_embedding_text,
    source_event_anchors,
)
from app.db.base import utc_now
from app.db.models import Document, DocumentAnalysis
from app.embeddings import EmbeddingClient
from app.extractors import EventExtractor
from app.schemas.analyses import CachedEmbeddingBatch
from app.schemas.clusters import (
    ClusterDocumentFingerprint,
    ClusterPreviewRequest,
    ClusterPreviewResponse,
)
from app.schemas.extractions import (
    DocumentExtractionInput,
    EventExtractionResult,
)


class MissingClusterDocumentsError(ValueError):
    """One or more snapshotted documents no longer exist."""

    def __init__(self, document_ids: list[int]) -> None:
        self.document_ids = document_ids
        super().__init__(f"missing document ids: {document_ids}")


def build_cluster_preview(
    session: Session,
    *,
    request: ClusterPreviewRequest,
    extractor: EventExtractor,
    embedding_client: EmbeddingClient,
    review_secret: str,
    batch_size: int | None = None,
    progress_callback: Callable[[int], None] | None = None,
    phase_callback: Callable[[str, float, str], None] | None = None,
    cache_results: bool = False,
) -> ClusterPreviewResponse:
    """Build one signed preview while clustering across the complete snapshot."""
    documents = list(
        session.scalars(
            select(Document)
            .where(Document.id.in_(request.document_ids))
            .options(selectinload(Document.source))
        )
    )
    documents_by_id = {document.id: document for document in documents}
    missing_ids = sorted(set(request.document_ids) - documents_by_id.keys())
    if missing_ids:
        raise MissingClusterDocumentsError(missing_ids)

    effective_batch_size = batch_size or len(request.document_ids)
    analyses_by_id: dict[int, DocumentAnalysis] = {}
    if cache_results:
        analyses_by_id = {
            analysis.document_id: analysis
            for analysis in session.scalars(
                select(DocumentAnalysis).where(
                    DocumentAnalysis.document_id.in_(request.document_ids)
                )
            )
        }
    extractions_by_id: dict[int, EventExtractionResult] = {}
    for position, document_id in enumerate(request.document_ids, start=1):
        document = documents_by_id[document_id]
        analysis = analyses_by_id.get(document_id)
        extraction_result = _read_cached_extraction(
            analysis,
            document=document,
            extractor_name=extractor.name,
        )
        if extraction_result is None:
            extraction_result = extractor.extract(
                DocumentExtractionInput(
                    document_id=document.id,
                    title=document.title,
                    body=document.body or "",
                    published_at=document.published_at,
                    language=document.language,
                    source_country=document.source.country,
                )
            )
        extractions_by_id[document_id] = extraction_result
        if cache_results:
            keep_embeddings = (
                analysis is not None
                and analysis.content_hash == document.content_hash
                and analysis.extractor_name == extractor.name
                and analysis.embedding_provider == embedding_client.name
            )
            if analysis is None:
                analysis = DocumentAnalysis(document_id=document_id)
                analyses_by_id[document_id] = analysis
                session.add(analysis)
            analysis.content_hash = document.content_hash
            analysis.extractor_name = extractor.name
            analysis.extraction = extraction_result.model_dump(mode="json")
            analysis.embedding_provider = embedding_client.name
            if not keep_embeddings:
                analysis.embeddings = CachedEmbeddingBatch().model_dump(
                    mode="json"
                )
            analysis.analyzed_at = utc_now()
        if (
            position % effective_batch_size == 0
            or position == len(request.document_ids)
        ):
            if cache_results:
                session.commit()
            if progress_callback is not None:
                progress_callback(position)

    extracted = [
        (
            document_id,
            event_index,
            extraction.extractor,
            event,
        )
        for document_id in request.document_ids
        for extraction in [extractions_by_id[document_id]]
        for event_index, event in enumerate(extraction.events)
    ]
    if phase_callback is not None:
        phase_callback(
            "embedding_events",
            76,
            f"文档抽取完成, 正在检查 {len(extracted)} 个事件向量",
        )
    vectors_by_candidate: dict[tuple[int, int], list[float]] = {}
    missing_embeddings: list[tuple[int, int, str]] = []
    for document_id in request.document_ids:
        extraction = extractions_by_id[document_id]
        cached_vectors = _read_cached_embeddings(
            analyses_by_id.get(document_id),
            document=documents_by_id[document_id],
            extractor_name=extractor.name,
            embedding_provider=embedding_client.name,
            event_count=len(extraction.events),
        )
        for event_index, event in enumerate(extraction.events):
            if cached_vectors is not None:
                vectors_by_candidate[(document_id, event_index)] = (
                    cached_vectors[event_index]
                )
            else:
                missing_embeddings.append(
                    (
                        document_id,
                        event_index,
                        candidate_embedding_text(event),
                    )
                )

    for offset in range(0, len(missing_embeddings), effective_batch_size):
        batch = missing_embeddings[offset : offset + effective_batch_size]
        generated = embedding_client.embed([item[2] for item in batch])
        for (document_id, event_index, _), vector in zip(
            batch,
            generated,
            strict=True,
        ):
            vectors_by_candidate[(document_id, event_index)] = vector
        if phase_callback is not None:
            embedded = min(offset + len(batch), len(missing_embeddings))
            share = embedded / max(1, len(missing_embeddings))
            phase_callback(
                "embedding_events",
                76 + share * 8,
                f"正在生成事件向量 {embedded}/{len(missing_embeddings)}",
            )

    if cache_results:
        for document_id in request.document_ids:
            analysis = analyses_by_id.get(document_id)
            if analysis is None:  # pragma: no cover - guarded above
                raise RuntimeError("analysis cache row was not initialized")
            document = documents_by_id[document_id]
            extraction = extractions_by_id[document_id]
            analysis.content_hash = document.content_hash
            analysis.extractor_name = extractor.name
            analysis.extraction = extraction.model_dump(mode="json")
            analysis.embedding_provider = embedding_client.name
            analysis.embeddings = CachedEmbeddingBatch(
                vectors=[
                    vectors_by_candidate[(document_id, event_index)]
                    for event_index in range(len(extraction.events))
                ]
            ).model_dump(mode="json")
            analysis.analyzed_at = utc_now()
        # The extraction/embedding cache is independently useful even if the
        # later O(n²) clustering stage fails or the worker is interrupted.
        session.commit()

    anchors_by_document = {
        document_id: source_event_anchors(
            documents_by_id[document_id].title,
            documents_by_id[document_id].body or "",
        )
        for document_id in request.document_ids
    }
    candidates = [
        CandidateFeatures(
            candidate_id=f"{document_id}:{event_index}",
            document_id=document_id,
            event_index=event_index,
            extractor=extractor_name,
            event=event,
            embedding=tuple(vector),
            source_occurred_at=anchors_by_document[document_id][0],
            source_latitude=anchors_by_document[document_id][1],
            source_longitude=anchors_by_document[document_id][2],
            source_magnitude=anchors_by_document[document_id][3],
        )
        for document_id, event_index, extractor_name, event in extracted
        for vector in [vectors_by_candidate[(document_id, event_index)]]
    ]
    if phase_callback is not None:
        phase_callback(
            "global_clustering",
            86,
            f"正在对 {len(candidates)} 个事件候选进行全局相似度聚类",
        )
    clustering_result = EventClusterer(
        merge_threshold=request.merge_threshold,
        time_window_hours=request.time_window_hours,
        location_radius_km=request.location_radius_km,
    ).cluster(candidates)
    if phase_callback is not None:
        phase_callback(
            "signing_preview",
            90,
            f"聚类完成, 正在整理 {len(clustering_result.clusters)} 个事件组",
        )
    unsigned_preview = ClusterPreviewResponse(
        embedding_provider=embedding_client.name,
        requested_document_ids=request.document_ids,
        document_fingerprints=[
            ClusterDocumentFingerprint(
                document_id=document_id,
                content_hash=documents_by_id[document_id].content_hash,
            )
            for document_id in request.document_ids
        ],
        candidate_count=len(candidates),
        clusters=clustering_result.clusters,
        merge_edges=clustering_result.merge_edges,
        rejected_near_matches=clustering_result.rejected_near_matches,
        potential_duplicate_document_ids=(
            clustering_result.potential_duplicate_document_ids
        ),
        review_signature="0" * 64,
    )
    return sign_cluster_preview(unsigned_preview, review_secret)


def _read_cached_extraction(
    analysis: DocumentAnalysis | None,
    *,
    document: Document,
    extractor_name: str,
) -> EventExtractionResult | None:
    if (
        analysis is None
        or analysis.content_hash != document.content_hash
        or analysis.extractor_name != extractor_name
    ):
        return None
    try:
        result = EventExtractionResult.model_validate(analysis.extraction)
    except ValidationError:
        return None
    return result if result.document_id == document.id else None


def _read_cached_embeddings(
    analysis: DocumentAnalysis | None,
    *,
    document: Document,
    extractor_name: str,
    embedding_provider: str,
    event_count: int,
) -> list[list[float]] | None:
    if (
        analysis is None
        or analysis.content_hash != document.content_hash
        or analysis.extractor_name != extractor_name
        or analysis.embedding_provider != embedding_provider
    ):
        return None
    try:
        cached = CachedEmbeddingBatch.model_validate(analysis.embeddings)
    except ValidationError:
        return None
    return cached.vectors if len(cached.vectors) == event_count else None
