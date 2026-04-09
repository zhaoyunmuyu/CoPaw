# -*- coding: utf-8 -*-
"""Tests for TraceStore."""
# pylint: disable=protected-access,redefined-outer-name,unused-variable

from datetime import datetime, timedelta
import json

import pytest

from copaw.tracing.config import TracingConfig
from copaw.tracing.models import (
    EventType,
    Span,
    Trace,
    TraceStatus,
)
from copaw.tracing.store import TraceStore


@pytest.fixture
def config():
    """Create tracing config for tests."""
    return TracingConfig(enabled=True)


@pytest.fixture
async def store(tmp_path, config):
    """Create TraceStore instance for testing."""
    trace_store = TraceStore(config, tmp_path / "tracing")
    yield trace_store
    await trace_store.close()


class TestTraceStoreCreation:
    """Tests for TraceStore initialization."""

    def test_creates_storage_directory(self, tmp_path, config):
        """Test that storage directory is created."""
        storage_path = tmp_path / "tracing"
        TraceStore(config, storage_path)

        assert storage_path.exists()

    @pytest.mark.asyncio
    async def test_with_existing_data(self, tmp_path, config):
        """Test loading existing data from file."""
        storage_path = tmp_path / "tracing"
        storage_path.mkdir(parents=True, exist_ok=True)

        # Create a trace file with existing data
        now = datetime.now()
        existing_trace = Trace(
            trace_id="existing-trace",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=now,
        )
        existing_span = Span(
            span_id="existing-span",
            trace_id="existing-trace",
            name="test",
            event_type=EventType.LLM_INPUT,
            start_time=now,
        )

        data = {
            "traces": [existing_trace.model_dump()],
            "spans": [existing_span.model_dump()],
        }

        file_path = storage_path / f"traces_{now.strftime('%Y-%m-%d')}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)

        # Create store - should load existing data
        trace_store = TraceStore(config, storage_path)

        assert "existing-trace" in trace_store._traces
        assert "existing-trace" in trace_store._spans

        await trace_store.close()


class TestTraceOperations:
    """Tests for trace CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_trace(self, store):
        """Test creating a trace."""
        trace = Trace(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=datetime.now(),
        )

        await store.create_trace(trace)

        assert "trace-1" in store._traces
        assert store._traces["trace-1"] == trace

    @pytest.mark.asyncio
    async def test_update_trace(self, store):
        """Test updating a trace."""
        trace = Trace(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=datetime.now(),
        )

        await store.create_trace(trace)

        # Update trace
        trace.status = TraceStatus.COMPLETED
        trace.total_input_tokens = 100
        await store.update_trace(trace)

        assert store._traces["trace-1"].status == TraceStatus.COMPLETED
        assert store._traces["trace-1"].total_input_tokens == 100

    @pytest.mark.asyncio
    async def test_get_trace(self, store):
        """Test getting a trace by ID."""
        trace = Trace(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=datetime.now(),
        )

        await store.create_trace(trace)

        result = await store.get_trace("trace-1")
        assert result == trace

    @pytest.mark.asyncio
    async def test_get_trace_not_found(self, store):
        """Test getting a non-existent trace."""
        result = await store.get_trace("nonexistent")
        assert result is None


class TestSpanOperations:
    """Tests for span CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_span(self, store):
        """Test creating a span."""
        # First create a trace
        trace = Trace(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=datetime.now(),
        )
        await store.create_trace(trace)

        span = Span(
            span_id="span-1",
            trace_id="trace-1",
            name="test_span",
            event_type=EventType.LLM_INPUT,
            start_time=datetime.now(),
        )

        await store.create_span(span)

        assert "trace-1" in store._spans
        assert len(store._spans["trace-1"]) == 1
        assert store._spans["trace-1"][0] == span

    @pytest.mark.asyncio
    async def test_create_multiple_spans(self, store):
        """Test creating multiple spans for the same trace."""
        trace = Trace(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=datetime.now(),
        )
        await store.create_trace(trace)

        for i in range(5):
            span = Span(
                span_id=f"span-{i}",
                trace_id="trace-1",
                name=f"span_{i}",
                event_type=EventType.LLM_INPUT,
                start_time=datetime.now(),
            )
            await store.create_span(span)

        assert len(store._spans["trace-1"]) == 5

    @pytest.mark.asyncio
    async def test_update_span(self, store):
        """Test updating a span."""
        now = datetime.now()
        trace = Trace(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=now,
        )
        await store.create_trace(trace)

        span = Span(
            span_id="span-1",
            trace_id="trace-1",
            name="test_span",
            event_type=EventType.LLM_INPUT,
            start_time=now,
        )
        await store.create_span(span)

        # Update span
        span.end_time = now + timedelta(milliseconds=100)
        span.duration_ms = 100
        span.output_tokens = 200
        await store.update_span(span)

        updated = store._spans["trace-1"][0]
        assert updated.duration_ms == 100
        assert updated.output_tokens == 200

    @pytest.mark.asyncio
    async def test_get_spans(self, store):
        """Test getting spans for a trace."""
        trace = Trace(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=datetime.now(),
        )
        await store.create_trace(trace)

        for i in range(3):
            span = Span(
                span_id=f"span-{i}",
                trace_id="trace-1",
                name=f"span_{i}",
                event_type=EventType.LLM_INPUT,
                start_time=datetime.now(),
            )
            await store.create_span(span)

        spans = await store.get_spans("trace-1")
        assert len(spans) == 3

    @pytest.mark.asyncio
    async def test_get_spans_empty(self, store):
        """Test getting spans for a trace with no spans."""
        spans = await store.get_spans("nonexistent")
        assert spans == []

    @pytest.mark.asyncio
    async def test_batch_create_spans(self, store):
        """Test batch creating spans."""
        now = datetime.now()
        spans = [
            Span(
                span_id=f"span-{i}",
                trace_id="trace-1",
                name=f"span_{i}",
                event_type=EventType.LLM_INPUT,
                start_time=now,
            )
            for i in range(10)
        ]

        await store.batch_create_spans(spans)

        assert len(store._spans["trace-1"]) == 10


class TestFilePersistence:
    """Tests for JSON file persistence."""

    @pytest.mark.asyncio
    async def test_flush_saves_to_file(self, tmp_path, config):
        """Test that flush saves data to file."""
        storage_path = tmp_path / "tracing"
        trace_store = TraceStore(config, storage_path)

        # Create trace and span
        now = datetime.now()
        trace = Trace(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=now,
        )
        await trace_store.create_trace(trace)

        span = Span(
            span_id="span-1",
            trace_id="trace-1",
            name="test",
            event_type=EventType.LLM_INPUT,
            start_time=now,
        )
        await trace_store.create_span(span)

        # Flush
        await trace_store.flush()

        # Check file exists
        file_path = trace_store._get_daily_file_path(
            now,
        )
        assert file_path.exists()

        await trace_store.close()

    @pytest.mark.asyncio
    async def test_atomic_write(self, tmp_path, config):
        """Test that file is written atomically."""
        storage_path = tmp_path / "tracing"
        trace_store = TraceStore(config, storage_path)

        now = datetime.now()
        trace = Trace(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=now,
        )
        await trace_store.create_trace(trace)
        await trace_store.flush()

        # No temp file should remain
        temp_files = list(storage_path.glob("*.tmp"))
        assert len(temp_files) == 0

        await trace_store.close()

    @pytest.mark.asyncio
    async def test_load_historical_data(self, tmp_path, config):
        """Test loading historical data from files."""
        storage_path = tmp_path / "tracing"
        storage_path.mkdir(parents=True, exist_ok=True)

        # Create a file for yesterday
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_file = (
            storage_path / f"traces_{yesterday.strftime('%Y-%m-%d')}.json"
        )

        trace = Trace(
            trace_id="old-trace",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=yesterday,
        )

        data = {
            "traces": [trace.model_dump()],
            "spans": [],
        }

        with open(yesterday_file, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)

        trace_store = TraceStore(config, storage_path)

        # Load historical data
        loaded_traces, _ = await trace_store.load_historical_data(
            yesterday,
            datetime.now(),
        )

        assert "old-trace" in loaded_traces

        await trace_store.close()


class TestQueryOperations:
    """Tests for query operations."""

    @pytest.mark.asyncio
    async def test_get_overview_stats(self, store):
        """Test getting overview statistics."""
        now = datetime.now()

        # Create traces
        for i in range(3):
            trace = Trace(
                trace_id=f"trace-{i}",
                user_id=f"user-{i % 2}",  # 2 users
                session_id=f"session-{i}",
                channel="console",
                start_time=now,
                status=TraceStatus.COMPLETED,
                total_input_tokens=100 + i * 10,
                total_output_tokens=50 + i * 5,
                model_name="gpt-4",
            )
            await store.create_trace(trace)

        stats = await store.get_overview_stats()

        assert stats.total_users == 2
        assert stats.total_sessions == 3
        assert stats.input_tokens > 0
        assert stats.output_tokens > 0

    @pytest.mark.asyncio
    async def test_get_users(self, store):
        """Test getting user list."""
        now = datetime.now()

        for i in range(5):
            trace = Trace(
                trace_id=f"trace-{i}",
                user_id=f"user-{i}",
                session_id=f"session-{i}",
                channel="console",
                start_time=now,
            )
            await store.create_trace(trace)

        users, total = await store.get_users(page=1, page_size=10)

        assert total == 5
        assert len(users) == 5

    @pytest.mark.asyncio
    async def test_get_users_pagination(self, store):
        """Test user list pagination."""
        now = datetime.now()

        for i in range(25):
            trace = Trace(
                trace_id=f"trace-{i}",
                user_id=f"user-{i}",
                session_id=f"session-{i}",
                channel="console",
                start_time=now,
            )
            await store.create_trace(trace)

        page1, total = await store.get_users(page=1, page_size=10)
        page2, _ = await store.get_users(page=2, page_size=10)

        assert total == 25
        assert len(page1) == 10
        assert len(page2) == 10

    @pytest.mark.asyncio
    async def test_get_user_stats(self, store):
        """Test getting user statistics."""
        now = datetime.now()
        user_id = "test-user"

        for i in range(3):
            trace = Trace(
                trace_id=f"trace-{i}",
                user_id=user_id,
                session_id=f"session-{i}",
                channel="console",
                start_time=now,
                model_name="gpt-4",
                total_input_tokens=100,
                total_output_tokens=50,
            )
            await store.create_trace(trace)

        stats = await store.get_user_stats(user_id)

        assert stats.user_id == user_id
        assert stats.total_sessions == 3
        assert stats.total_tokens == (100 + 50) * 3

    @pytest.mark.asyncio
    async def test_get_traces(self, store):
        """Test getting trace list."""
        now = datetime.now()

        for i in range(5):
            trace = Trace(
                trace_id=f"trace-{i}",
                user_id="user-1",
                session_id="session-1",
                channel="console",
                start_time=now,
            )
            await store.create_trace(trace)

        traces, total = await store.get_traces()

        assert total == 5
        assert len(traces) == 5

    @pytest.mark.asyncio
    async def test_get_traces_filter_by_user(self, store):
        """Test filtering traces by user."""
        now = datetime.now()

        for i in range(5):
            trace = Trace(
                trace_id=f"trace-{i}",
                user_id=f"user-{i % 2}",
                session_id="session-1",
                channel="console",
                start_time=now,
            )
            await store.create_trace(trace)

        traces, total = await store.get_traces(user_id="user-0")

        assert total == 3  # traces 0, 2, 4

    @pytest.mark.asyncio
    async def test_get_traces_filter_by_status(self, store):
        """Test filtering traces by status."""
        now = datetime.now()

        for i in range(4):
            status = TraceStatus.COMPLETED if i < 2 else TraceStatus.ERROR
            trace = Trace(
                trace_id=f"trace-{i}",
                user_id="user-1",
                session_id="session-1",
                channel="console",
                start_time=now,
                status=status,
            )
            await store.create_trace(trace)

        completed, _ = await store.get_traces(status="completed")
        errors, _ = await store.get_traces(status="error")

        assert len(completed) == 2
        assert len(errors) == 2

    @pytest.mark.asyncio
    async def test_get_trace_detail(self, store):
        """Test getting trace detail with spans."""
        now = datetime.now()

        trace = Trace(
            trace_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=now,
        )
        await store.create_trace(trace)

        # Create spans
        llm_span = Span(
            span_id="span-1",
            trace_id="trace-1",
            name="llm_call",
            event_type=EventType.LLM_INPUT,
            start_time=now,
            duration_ms=1000,
        )
        tool_span = Span(
            span_id="span-2",
            trace_id="trace-1",
            name="tool_call",
            event_type=EventType.TOOL_CALL_END,
            start_time=now,
            duration_ms=500,
            tool_name="browser",
        )
        await store.create_span(llm_span)
        await store.create_span(tool_span)

        detail = await store.get_trace_detail("trace-1")

        assert detail is not None
        assert detail.trace.trace_id == "trace-1"
        assert len(detail.spans) == 2

    @pytest.mark.asyncio
    async def test_get_sessions(self, store):
        """Test getting session list."""
        now = datetime.now()

        for i in range(5):
            trace = Trace(
                trace_id=f"trace-{i}",
                user_id="user-1",
                session_id=f"session-{i % 2}",
                channel="console",
                start_time=now,
            )
            await store.create_trace(trace)

        sessions, total = await store.get_sessions()

        assert total == 2  # 2 unique sessions

    @pytest.mark.asyncio
    async def test_get_user_messages(self, store):
        """Test getting user messages."""
        now = datetime.now()

        for i in range(3):
            trace = Trace(
                trace_id=f"trace-{i}",
                user_id="user-1",
                session_id="session-1",
                channel="console",
                start_time=now,
                user_message=f"Message {i}",
                total_input_tokens=10,
                total_output_tokens=20,
            )
            await store.create_trace(trace)

        messages, total = await store.get_user_messages()

        assert total == 3
        assert len(messages) == 3


class TestCleanup:
    """Tests for data cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, store):
        """Test cleaning up old data from memory."""
        # Create old trace
        old_date = datetime.now() - timedelta(days=60)
        old_trace = Trace(
            trace_id="old-trace",
            user_id="user-1",
            session_id="session-1",
            channel="console",
            start_time=old_date,
        )
        await store.create_trace(old_trace)

        # Create recent trace
        recent_trace = Trace(
            trace_id="recent-trace",
            user_id="user-1",
            session_id="session-2",
            channel="console",
            start_time=datetime.now(),
        )
        await store.create_trace(recent_trace)

        # Clean up data older than 30 days
        cutoff = datetime.now() - timedelta(days=30)
        await store.cleanup_old_data(cutoff)

        assert "old-trace" not in store._traces
        assert "recent-trace" in store._traces


class TestTokenSummary:
    """Tests for token summary generation."""

    @pytest.mark.asyncio
    async def test_get_token_summary(self, store):
        """Test getting token usage summary."""
        now = datetime.now()

        for i in range(5):
            trace = Trace(
                trace_id=f"trace-{i}",
                user_id="user-1",
                session_id="session-1",
                channel="console",
                start_time=now,
                model_name="gpt-4",
                total_input_tokens=100 + i * 10,
                total_output_tokens=50 + i * 5,
            )
            await store.create_trace(trace)

            # Create LLM input span for call counting
            span = Span(
                span_id=f"span-{i}",
                trace_id=f"trace-{i}",
                name="llm_call",
                event_type=EventType.LLM_INPUT,
                start_time=now,
            )
            await store.create_span(span)

        summary = await store.get_token_summary(
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
        )

        assert summary.total_prompt_tokens > 0
        assert summary.total_completion_tokens > 0
        assert summary.total_calls == 5
