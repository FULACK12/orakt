"""Generate, inspect and review local-AI multi-step logic hypotheses."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.logic_chains import (
    LocalLogicChainError,
    LogicChainHypothesisNotFoundError,
    LogicChainJobNotFoundError,
    generate_logic_hypotheses,
    list_logic_hypotheses,
    list_training_signals,
    review_logic_hypothesis,
    validate_logic_hypotheses,
)
from app.logic_memory import (
    ExternalTrainingExampleNotFoundError,
    build_training_dataset,
    import_external_training_examples,
    list_external_training_examples,
    list_verified_logic_memories,
    review_external_training_example,
)
from app.research import (
    ResearchInquiryNotFoundError,
    ResearchProviderError,
    review_logic_chain_with_openai,
)
from app.schemas.logic_chains import (
    ExternalTrainingExampleList,
    ExternalTrainingExampleView,
    ExternalTrainingImportRequest,
    ExternalTrainingImportResponse,
    ExternalTrainingReviewRequest,
    LogicChainGenerationResponse,
    LogicChainResponse,
    LogicChainReviewRequest,
    LogicChainTrainingSignalsResponse,
    LogicChainValidationResponse,
    TrainingDatasetResponse,
    VerifiedLogicMemoryResponse,
)
from app.schemas.research import ChatGPTResearchReview

router = APIRouter(prefix="/logic-chains", tags=["logic-chains"])


@router.post(
    "/{job_id}/generate",
    response_model=LogicChainGenerationResponse,
    summary="Generate local-AI multi-step logic hypotheses",
)
def generate_chains(
    job_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> LogicChainGenerationResponse:
    """Generate constrained hypotheses; no causal statement is confirmed."""
    try:
        response = generate_logic_hypotheses(
            session,
            job_id=job_id,
            include_external_market=True,
        )
        session.commit()
        return response
    except LogicChainJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"completed cluster job not found: {exc}",
        ) from exc
    except LocalLogicChainError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post(
    "/{job_id}/validate",
    response_model=LogicChainValidationResponse,
    summary="Revalidate stored hypotheses with the causal-validation agent",
)
def validate_chains(
    job_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> LogicChainValidationResponse:
    """Refresh official evidence and rerun all six causal-validation gates."""
    try:
        validated_count = validate_logic_hypotheses(
            session,
            job_id=job_id,
            include_external_evidence=True,
        )
        response = list_logic_hypotheses(session, job_id=job_id)
        session.commit()
        return LogicChainValidationResponse(
            **response.model_dump(),
            validated_count=validated_count,
        )
    except LogicChainJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"completed cluster job not found: {exc}",
        ) from exc


@router.get(
    "/training-signals",
    response_model=LogicChainTrainingSignalsResponse,
    summary="List retained human logic-chain feedback",
)
def get_training_signals(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=5_000)] = 500,
) -> LogicChainTrainingSignalsResponse:
    """Expose the append-only review trail for later local tuning."""
    return list_training_signals(session, limit=limit)


@router.get(
    "/verified-memory",
    response_model=VerifiedLogicMemoryResponse,
    summary="List strict evidence-qualified reusable logic memory",
)
def get_verified_memory(
    session: Annotated[Session, Depends(get_db_session)],
    focus: Annotated[str, Query(max_length=2_000)] = "",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> VerifiedLogicMemoryResponse:
    """Return analogies reusable by the local model; never claim causal proof."""
    return list_verified_logic_memories(session, focus=focus, limit=limit)


@router.get(
    "/training-dataset",
    response_model=TrainingDatasetResponse,
    summary="Build an auditable chat-JSONL training dataset",
)
def get_training_dataset(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=10_000)] = 2_000,
) -> TrainingDatasetResponse:
    """Export qualified examples; exporting is not the same as model training."""
    return build_training_dataset(session, limit=limit)


@router.get(
    "/training-dataset.jsonl",
    response_class=Response,
    summary="Download the qualified training dataset as chat JSONL",
)
def download_training_dataset(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=10_000)] = 2_000,
) -> Response:
    """Serialize one training example per line without claiming a training run."""
    dataset = build_training_dataset(session, limit=limit)
    body = "\n".join(
        json.dumps(example.model_dump(mode="json"), ensure_ascii=False)
        for example in dataset.examples
    )
    if body:
        body += "\n"
    return Response(
        content=body,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": 'attachment; filename="news-map-training.jsonl"',
            "X-Training-Performed": "false",
        },
    )


@router.post(
    "/external-training/import",
    response_model=ExternalTrainingImportResponse,
    summary="Stage licensed external examples in the review quarantine",
)
def import_external_training_data(
    request: ExternalTrainingImportRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ExternalTrainingImportResponse:
    """Import a bounded JSON batch; every new example remains pending."""
    response = import_external_training_examples(session, request)
    session.commit()
    return response


@router.get(
    "/external-training",
    response_model=ExternalTrainingExampleList,
    summary="List external training examples and review states",
)
def get_external_training_data(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=5_000)] = 500,
) -> ExternalTrainingExampleList:
    """Return provenance and review state without the full training payload."""
    return list_external_training_examples(session, limit=limit)


@router.patch(
    "/external-training/{example_id}",
    response_model=ExternalTrainingExampleView,
    summary="Approve or reject one quarantined external example",
)
def review_external_training_data(
    example_id: int,
    request: ExternalTrainingReviewRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ExternalTrainingExampleView:
    """Only approved examples are eligible for a later training export."""
    try:
        response = review_external_training_example(
            session,
            example_id=example_id,
            status=request.status,
            quality_score=request.quality_score,
            review_note=request.review_note,
        )
        session.commit()
        return response
    except ExternalTrainingExampleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"external training example not found: {exc}",
        ) from exc


@router.get(
    "/{job_id}",
    response_model=LogicChainResponse,
    summary="List reviewable multi-step logic hypotheses",
)
def get_chains(
    job_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> LogicChainResponse:
    """Return current hypotheses and retained feedback count."""
    try:
        return list_logic_hypotheses(session, job_id=job_id)
    except LogicChainJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"completed cluster job not found: {exc}",
        ) from exc


@router.patch(
    "/hypotheses/{hypothesis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Review a logic hypothesis and retain the feedback",
)
def set_hypothesis_decision(
    hypothesis_id: int,
    request: LogicChainReviewRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Store current state and append a never-overwritten training signal."""
    try:
        review_logic_hypothesis(
            session,
            hypothesis_id=hypothesis_id,
            decision=request.status,
            reviewer_note=request.reviewer_note,
            suggested_correction=request.suggested_correction,
        )
        session.commit()
    except LogicChainHypothesisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"logic hypothesis not found: {exc}",
        ) from exc


@router.post(
    "/hypotheses/{hypothesis_id}/chatgpt-review",
    response_model=ChatGPTResearchReview,
    summary="Request an optional OpenAI second review of a local logic chain",
)
def chatgpt_review_hypothesis(
    hypothesis_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ChatGPTResearchReview:
    """Retain an OpenAI audit alongside the original local-model result."""
    try:
        review = review_logic_chain_with_openai(
            session,
            hypothesis_id=hypothesis_id,
        )
        session.commit()
        return review
    except ResearchInquiryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="logic hypothesis not found",
        ) from exc
    except ResearchProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
