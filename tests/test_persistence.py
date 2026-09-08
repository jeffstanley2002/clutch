import asyncio
from hashlib import sha256

from sqlalchemy import func, select

from clutch.agent import build_review_graph
from clutch.llm import ModelRouter
from clutch.persistence import (
    Base,
    NullReviewRecorder,
    ReviewPersistenceRecord,
    SqlAlchemyReviewRecorder,
    create_session_factory,
)
from clutch.persistence.database import (
    database_url_from_env,
    normalize_async_database_url,
)
from clutch.persistence.models import (
    GeneratedQuestionModel,
    ReviewFindingModel,
    ReviewSessionModel,
)
from clutch.review.service import ReviewService
from clutch.schemas import ReviewRequest


class CapturingRecorder:
    def __init__(self) -> None:
        self.records: list[ReviewPersistenceRecord] = []

    async def record_review(self, record: ReviewPersistenceRecord) -> None:
        self.records.append(record)


def test_service_reduces_source_to_hash_before_persistence() -> None:
    sentinel = "RAW_SOURCE_MUST_NOT_PERSIST_91f2"
    request = ReviewRequest(
        code=f"def value():\n    return '{sentinel}'\n",
        session_id="local-profile-1",
    )
    recorder = CapturingRecorder()
    service = ReviewService(
        graph=build_review_graph(ModelRouter(primary=None)),
        recorder=recorder,
    )

    response = asyncio.run(service.review(request))

    assert response.mode == "static_fallback"
    assert len(recorder.records) == 1
    record = recorder.records[0]
    assert record.code_sha256 == sha256(request.code.encode("utf-8")).hexdigest()
    assert record.line_count == 2
    assert record.external_session_id == "local-profile-1"
    assert sentinel not in record.model_dump_json()


def test_review_record_round_trips_through_sqlalchemy_without_raw_code() -> None:
    async def exercise() -> None:
        engine, session_factory = create_session_factory("sqlite+aiosqlite://")
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=[
                        ReviewSessionModel.__table__,
                        ReviewFindingModel.__table__,
                        GeneratedQuestionModel.__table__,
                    ],
                )
            )

        recorder = CapturingRecorder()
        service = ReviewService(
            graph=build_review_graph(ModelRouter(primary=None)),
            recorder=recorder,
        )
        await service.review(
            ReviewRequest(
                code="def collect(value, bucket=[]):\n    return bucket\n"
            )
        )
        sql_repository = SqlAlchemyReviewRecorder(session_factory)
        await sql_repository.record_review(recorder.records[0])
        restored_findings = await sql_repository.get_findings(
            recorder.records[0].review_session_id
        )

        async with session_factory() as session:
            stored_review = await session.scalar(select(ReviewSessionModel))
            finding_count = await session.scalar(
                select(func.count()).select_from(ReviewFindingModel)
            )
            question_count = await session.scalar(
                select(func.count()).select_from(GeneratedQuestionModel)
            )

        assert stored_review is not None
        assert stored_review.code_sha256 == recorder.records[0].code_sha256
        assert finding_count == 1
        assert question_count == 1
        assert restored_findings == recorder.records[0].findings
        await engine.dispose()

    asyncio.run(exercise())


def test_persistence_schema_has_no_raw_code_or_evidence_columns() -> None:
    prohibited_columns = {"code", "raw_code", "source_code", "evidence"}
    persisted_columns = {
        column.name
        for table in Base.metadata.tables.values()
        for column in table.columns
    }

    assert persisted_columns.isdisjoint(prohibited_columns)


def test_database_url_normalization_preserves_explicit_drivers() -> None:
    assert normalize_async_database_url(
        "postgresql://clutch@localhost/clutch"
    ) == "postgresql+asyncpg://clutch@localhost/clutch"
    assert (
        normalize_async_database_url("sqlite+aiosqlite://")
        == "sqlite+aiosqlite://"
    )


def test_database_url_can_be_assembled_from_secret_friendly_parts(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CLUTCH_DB_HOST", "database.internal")
    monkeypatch.setenv(  # pragma: allowlist secret
        "CLUTCH_DB_PASSWORD", "safe/example:value"
    )
    monkeypatch.setenv("CLUTCH_DB_USER", "clutch-user")

    assert database_url_from_env() == (
        "postgresql+asyncpg://clutch-user:safe%2Fexample%3Avalue@"  # pragma: allowlist secret
        "database.internal:5432/clutch"
    )


def test_null_recorder_accepts_privacy_reduced_records() -> None:
    recorder = NullReviewRecorder()
    record = ReviewPersistenceRecord(
        review_session_id="review-id",
        code_sha256="0" * 64,
        language="python",
        line_count=1,
        role_context="backend intern",
        mode="static_fallback",
        confidence=0.5,
        latency_ms=1.0,
    )

    asyncio.run(recorder.record_review(record))
