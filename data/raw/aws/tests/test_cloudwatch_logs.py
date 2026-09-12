"""Tests for CloudWatch Logs data source adapter."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from data_sources.cloudwatch_logs import (
    CloudWatchLogsDataSource,
    create_cloudwatch_source,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cw_event(stream: str, message: str, ts_ms: int) -> dict:
    """Build a CloudWatch filter_log_events event dict."""
    return {
        "logStreamName": stream,
        "message": message,
        "timestamp": ts_ms,
        "ingestionTime": ts_ms + 100,
        "eventId": f"evt-{ts_ms}",
    }


TIME_START = datetime(2024, 3, 15, 14, 0, 0)
TIME_END = datetime(2024, 3, 15, 14, 30, 0)
TS_START_MS = int(TIME_START.timestamp() * 1000)
TS_END_MS = int(TIME_END.timestamp() * 1000)

# Timestamp in the middle of the window (14:15)
MID_TS_MS = int(datetime(2024, 3, 15, 14, 15, 0).timestamp() * 1000)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    @patch.dict("os.environ", {}, clear=True)
    def test_default_region(self):
        ds = CloudWatchLogsDataSource(log_group_names=["/aws/lambda/fn"])
        assert ds.region == "us-east-1"

    def test_custom_region(self):
        ds = CloudWatchLogsDataSource(
            log_group_names=["/aws/lambda/fn"], region="eu-west-1"
        )
        assert ds.region == "eu-west-1"

    @patch.dict("os.environ", {"AWS_REGION": "ap-southeast-1"})
    def test_region_from_env(self):
        ds = CloudWatchLogsDataSource(log_group_names=["/aws/lambda/fn"])
        assert ds.region == "ap-southeast-1"

    def test_custom_query_timeout(self):
        ds = CloudWatchLogsDataSource(
            log_group_names=["/aws/lambda/fn"], query_timeout=60
        )
        assert ds.query_timeout == 60

    def test_convenience_factory(self):
        ds = create_cloudwatch_source(
            log_group_names=["/aws/lambda/fn"],
            region="us-west-2",
        )
        assert isinstance(ds, CloudWatchLogsDataSource)
        assert ds.region == "us-west-2"


# ---------------------------------------------------------------------------
# Log group discovery
# ---------------------------------------------------------------------------


class TestLogGroupDiscovery:
    def test_explicit_log_group_names(self):
        ds = CloudWatchLogsDataSource(log_group_names=["/a", "/b"])
        assert ds.log_group_names == ["/a", "/b"]

    def test_discover_by_prefix(self):
        ds = CloudWatchLogsDataSource(log_group_prefix="/aws/lambda/rca-")
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"logGroups": [{"logGroupName": "/aws/lambda/rca-fn1"}]},
            {"logGroups": [{"logGroupName": "/aws/lambda/rca-fn2"}]},
        ]
        mock_client.get_paginator.return_value = mock_paginator
        ds._client = mock_client

        groups = ds.log_group_names
        assert groups == ["/aws/lambda/rca-fn1", "/aws/lambda/rca-fn2"]
        mock_client.get_paginator.assert_called_once_with("describe_log_groups")

    def test_no_groups_or_prefix_raises(self):
        ds = CloudWatchLogsDataSource()
        ds._client = MagicMock()
        with pytest.raises(ValueError, match="Must provide either"):
            _ = ds.log_group_names


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.fixture()
    def ds(self):
        """DataSource with a mocked boto3 client."""
        source = CloudWatchLogsDataSource(log_group_names=["/app/svc"])
        mock_client = MagicMock()
        source._client = mock_client
        return source, mock_client

    def _setup_paginator(self, mock_client, pages):
        """Wire a mock paginator that yields *pages*."""
        paginator = MagicMock()
        paginator.paginate.return_value = pages
        mock_client.get_paginator.return_value = paginator
        return paginator

    def test_basic_search(self, ds):
        source, client = ds
        self._setup_paginator(
            client,
            [
                {
                    "events": [
                        _make_cw_event("stream-1", "timeout in handler", MID_TS_MS),
                        _make_cw_event(
                            "stream-2", "timeout connecting to db", MID_TS_MS + 1000
                        ),
                    ],
                },
            ],
        )

        resp = source.search("timeout", TIME_START, TIME_END)

        assert len(resp.results) == 2
        assert resp.total_matches == 2
        assert resp.query == "timeout"
        assert resp.results[0].source == "stream-1"
        assert "timeout in handler" in resp.results[0].content
        assert resp.results[0].metadata == {"log_group": "/app/svc"}

    def test_timestamp_parsing(self, ds):
        source, client = ds
        self._setup_paginator(
            client,
            [
                {"events": [_make_cw_event("s", "msg", MID_TS_MS)]},
            ],
        )

        resp = source.search("msg", TIME_START, TIME_END)
        assert resp.results[0].timestamp == datetime(2024, 3, 15, 14, 15, 0)

    def test_invalid_timestamp_returns_none(self, ds):
        source, client = ds
        event = _make_cw_event("s", "msg", MID_TS_MS)
        event["timestamp"] = "not-a-number"
        self._setup_paginator(client, [{"events": [event]}])

        resp = source.search("msg", TIME_START, TIME_END)
        assert resp.results[0].timestamp is None

    def test_missing_timestamp_returns_none(self, ds):
        source, client = ds
        event = {"logStreamName": "s", "message": "msg"}
        self._setup_paginator(client, [{"events": [event]}])

        resp = source.search("msg", TIME_START, TIME_END)
        assert resp.results[0].timestamp is None

    def test_limit_respected(self, ds):
        source, client = ds
        events = [_make_cw_event("s", f"msg-{i}", MID_TS_MS + i) for i in range(20)]
        self._setup_paginator(client, [{"events": events}])

        resp = source.search("msg", TIME_START, TIME_END, limit=5)
        assert len(resp.results) == 5

    def test_truncated_flag_is_false_when_at_limit(self, ds):
        """Adapter caps total_matched at limit, so truncated stays False.

        The inner loop breaks as soon as len(results) >= limit and
        total_matched only counts appended results — so it can never
        exceed limit.  This is a known limitation: CloudWatch's
        filter_log_events doesn't expose a total count.
        """
        source, client = ds
        events = [_make_cw_event("s", f"msg-{i}", MID_TS_MS + i) for i in range(20)]
        self._setup_paginator(client, [{"events": events}])

        resp = source.search("msg", TIME_START, TIME_END, limit=5)
        assert len(resp.results) == 5
        assert resp.truncated is False  # total_matched == limit, not >
        assert resp.total_matches == 5

    def test_no_results(self, ds):
        source, client = ds
        self._setup_paginator(client, [{"events": []}])

        resp = source.search("nonexistent", TIME_START, TIME_END)
        assert len(resp.results) == 0
        assert resp.total_matches == 0
        assert resp.quality_score == 0.0

    def test_service_filter_sets_stream_prefix(self, ds):
        source, client = ds
        paginator = self._setup_paginator(client, [{"events": []}])

        source.search("error", TIME_START, TIME_END, filters={"service": "pricing"})

        call_kwargs = paginator.paginate.call_args[1]
        assert call_kwargs["logStreamNamePrefix"] == "pricing"

    def test_level_filter_appended_to_pattern(self, ds):
        source, client = ds
        paginator = self._setup_paginator(client, [{"events": []}])

        source.search("timeout", TIME_START, TIME_END, filters={"level": "error"})

        call_kwargs = paginator.paginate.call_args[1]
        assert call_kwargs["filterPattern"] == "timeout ERROR"

    def test_time_window_converted_to_millis(self, ds):
        source, client = ds
        paginator = self._setup_paginator(client, [{"events": []}])

        source.search("q", TIME_START, TIME_END)

        call_kwargs = paginator.paginate.call_args[1]
        assert call_kwargs["startTime"] == TS_START_MS
        assert call_kwargs["endTime"] == TS_END_MS

    def test_multiple_log_groups(self):
        source = CloudWatchLogsDataSource(log_group_names=["/app/a", "/app/b"])
        mock_client = MagicMock()
        source._client = mock_client

        # Each log group returns one event
        paginator = MagicMock()
        paginator.paginate.side_effect = [
            [{"events": [_make_cw_event("a-stream", "error-a", MID_TS_MS)]}],
            [{"events": [_make_cw_event("b-stream", "error-b", MID_TS_MS)]}],
        ]
        mock_client.get_paginator.return_value = paginator

        resp = source.search("error", TIME_START, TIME_END)
        assert len(resp.results) == 2
        assert resp.results[0].metadata["log_group"] == "/app/a"
        assert resp.results[1].metadata["log_group"] == "/app/b"

    def test_multiple_pages(self, ds):
        source, client = ds
        self._setup_paginator(
            client,
            [
                {"events": [_make_cw_event("s", "page1", MID_TS_MS)]},
                {"events": [_make_cw_event("s", "page2", MID_TS_MS + 1000)]},
            ],
        )

        resp = source.search("msg", TIME_START, TIME_END)
        assert len(resp.results) == 2

    def test_missing_fields_in_event(self, ds):
        source, client = ds
        self._setup_paginator(client, [{"events": [{}]}])

        resp = source.search("q", TIME_START, TIME_END)
        assert resp.results[0].source == "unknown"
        assert resp.results[0].content == ""

    def test_quality_score_excellent(self, ds):
        source, client = ds
        events = [_make_cw_event("s", f"m{i}", MID_TS_MS + i) for i in range(3)]
        self._setup_paginator(client, [{"events": events}])

        resp = source.search("q", TIME_START, TIME_END)
        assert resp.quality_score == 1.0

    def test_quality_score_broad(self, ds):
        source, client = ds
        events = [_make_cw_event("s", f"m{i}", MID_TS_MS + i) for i in range(30)]
        self._setup_paginator(client, [{"events": events}])

        resp = source.search("q", TIME_START, TIME_END, limit=30)
        assert resp.quality_score == 0.3


# ---------------------------------------------------------------------------
# Retry / error handling
# ---------------------------------------------------------------------------


class TestRetryAndErrors:
    def test_throttle_retries(self):
        from botocore.exceptions import ClientError

        source = CloudWatchLogsDataSource(log_group_names=["/app/svc"])
        mock_client = MagicMock()
        source._client = mock_client

        error_response = {
            "Error": {"Code": "ThrottlingException", "Message": "slow down"}
        }
        paginator = MagicMock()
        # First two calls raise throttle, third succeeds
        paginator.paginate.side_effect = [
            ClientError(error_response, "FilterLogEvents"),
            ClientError(error_response, "FilterLogEvents"),
            [{"events": [_make_cw_event("s", "ok", MID_TS_MS)]}],
        ]
        mock_client.get_paginator.return_value = paginator

        with patch("data_sources.cloudwatch_logs.time.sleep"):
            resp = source.search("q", TIME_START, TIME_END)

        assert len(resp.results) == 1
        assert paginator.paginate.call_count == 3

    def test_non_retryable_error_stops(self):
        from botocore.exceptions import ClientError

        source = CloudWatchLogsDataSource(log_group_names=["/app/svc"])
        mock_client = MagicMock()
        source._client = mock_client

        error_response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "gone"}
        }
        paginator = MagicMock()
        paginator.paginate.side_effect = ClientError(error_response, "FilterLogEvents")
        mock_client.get_paginator.return_value = paginator

        resp = source.search("q", TIME_START, TIME_END)
        assert len(resp.results) == 0
        assert paginator.paginate.call_count == 1

    def test_generic_exception_stops(self):
        source = CloudWatchLogsDataSource(log_group_names=["/app/svc"])
        mock_client = MagicMock()
        source._client = mock_client

        paginator = MagicMock()
        paginator.paginate.side_effect = RuntimeError("unexpected")
        mock_client.get_paginator.return_value = paginator

        resp = source.search("q", TIME_START, TIME_END)
        assert len(resp.results) == 0

    def test_max_retries_exhausted(self):
        from botocore.exceptions import ClientError

        source = CloudWatchLogsDataSource(log_group_names=["/app/svc"])
        mock_client = MagicMock()
        source._client = mock_client

        error_response = {
            "Error": {"Code": "ThrottlingException", "Message": "slow down"}
        }
        paginator = MagicMock()
        paginator.paginate.side_effect = ClientError(error_response, "FilterLogEvents")
        mock_client.get_paginator.return_value = paginator

        with patch("data_sources.cloudwatch_logs.time.sleep"):
            resp = source.search("q", TIME_START, TIME_END)

        assert len(resp.results) == 0
        # Initial call + MAX_RETRIES (3) retries = 4
        assert paginator.paginate.call_count == 4


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_healthy_with_log_groups(self):
        ds = CloudWatchLogsDataSource(log_group_names=["/app/svc"])
        mock_client = MagicMock()
        mock_client.describe_log_groups.return_value = {
            "logGroups": [{"logGroupName": "/app/svc"}]
        }
        ds._client = mock_client

        result = ds.health_check()
        assert result["status"] == "ok"
        assert result["details"]["log_group_count"] == 1

    def test_healthy_with_prefix(self):
        ds = CloudWatchLogsDataSource(log_group_prefix="/aws/lambda/rca-")
        mock_client = MagicMock()
        mock_client.describe_log_groups.return_value = {
            "logGroups": [{"logGroupName": "/aws/lambda/rca-fn1"}]
        }
        ds._client = mock_client

        result = ds.health_check()
        assert result["status"] == "ok"

    def test_unhealthy_no_matching_groups(self):
        ds = CloudWatchLogsDataSource(log_group_names=["/nonexistent"])
        mock_client = MagicMock()
        mock_client.describe_log_groups.return_value = {"logGroups": []}
        ds._client = mock_client

        result = ds.health_check()
        assert result["status"] == "error"
        assert "No matching" in result["message"]

    def test_unhealthy_no_matching_prefix(self):
        ds = CloudWatchLogsDataSource(log_group_prefix="/nonexistent/")
        mock_client = MagicMock()
        mock_client.describe_log_groups.return_value = {"logGroups": []}
        ds._client = mock_client

        result = ds.health_check()
        assert result["status"] == "error"
        assert "No log groups matching prefix" in result["message"]

    def test_unhealthy_no_config(self):
        ds = CloudWatchLogsDataSource()
        ds._client = MagicMock()

        result = ds.health_check()
        assert result["status"] == "error"
        assert "No log groups or prefix" in result["message"]

    def test_client_error_returns_error(self):
        ds = CloudWatchLogsDataSource(log_group_names=["/app/svc"])
        mock_client = MagicMock()
        mock_client.describe_log_groups.side_effect = Exception("connection refused")
        ds._client = mock_client

        result = ds.health_check()
        assert result["status"] == "error"
        assert "connection refused" in result["message"]


# ---------------------------------------------------------------------------
# list_sources / list_log_groups
# ---------------------------------------------------------------------------


class TestListSources:
    def test_list_sources_returns_groups(self):
        ds = CloudWatchLogsDataSource(log_group_names=["/a", "/b"])
        assert ds.list_sources() == ["/a", "/b"]

    def test_list_sources_no_config_returns_empty(self):
        ds = CloudWatchLogsDataSource()
        ds._client = MagicMock()
        assert ds.list_sources() == []

    def test_list_log_groups(self):
        ds = CloudWatchLogsDataSource(log_group_names=["/a"])
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"logGroups": [{"logGroupName": "/g1"}, {"logGroupName": "/g2"}]},
        ]
        mock_client.get_paginator.return_value = paginator
        ds._client = mock_client

        groups = ds.list_log_groups(prefix="/g")
        assert groups == ["/g1", "/g2"]
        paginator.paginate.assert_called_once_with(logGroupNamePrefix="/g")

    def test_list_log_groups_no_prefix(self):
        ds = CloudWatchLogsDataSource(log_group_names=["/a"])
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"logGroups": [{"logGroupName": "/all"}]},
        ]
        mock_client.get_paginator.return_value = paginator
        ds._client = mock_client

        groups = ds.list_log_groups()
        assert groups == ["/all"]
        paginator.paginate.assert_called_once_with()
