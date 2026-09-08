"""Privacy-preserving persistence contracts and SQLAlchemy implementation."""

from clutch.persistence.contracts import (
    ReviewPersistenceRecord,
    build_review_persistence_record,
)
from clutch.persistence.database import create_session_factory, database_url_from_env
from clutch.persistence.models import Base
from clutch.persistence.repository import (
    IN_MEMORY_REVIEW_RECORDER,
    InMemoryReviewRecorder,
    NullReviewRecorder,
    ReviewFindingReader,
    ReviewRecorder,
    SqlAlchemyReviewRecorder,
    review_finding_reader_from_env,
    review_recorder_from_env,
)

__all__ = [
    "Base",
    "IN_MEMORY_REVIEW_RECORDER",
    "InMemoryReviewRecorder",
    "NullReviewRecorder",
    "ReviewPersistenceRecord",
    "ReviewFindingReader",
    "ReviewRecorder",
    "SqlAlchemyReviewRecorder",
    "build_review_persistence_record",
    "create_session_factory",
    "database_url_from_env",
    "review_finding_reader_from_env",
    "review_recorder_from_env",
]
