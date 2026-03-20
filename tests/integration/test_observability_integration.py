"""Integration tests for observability /metrics endpoint"""

import pytest
import time
import socket
import asyncio
import urllib.request
from unittest.mock import patch
from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from solace_ai_connector.common.observability import (
    MetricRegistry,
    MonitorLatency,
    OperationMonitor,
    DBMonitor
)


class TestObservabilityIntegration:
    """Integration tests for observability metrics endpoint."""

    def _find_available_port(self):
        """Helper: Find available port for management server."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def _create_base_config(self, port, observability_config=None, metric_prefix="sam"):
        """
        Helper: Create base connector config with observability enabled.

        Args:
            port: Management server port
            observability_config: Optional dict to override observability settings
            metric_prefix: Metric prefix (default: "sam")

        Returns:
            Complete connector config dict
        """
        obs_config = {
            "enabled": True,
            "path": "/metrics",
            "metric_prefix": metric_prefix
        }

        # Merge with custom observability config
        if observability_config:
            obs_config.update(observability_config)

        return {
            "log": {
                "stdout_log_level": "ERROR",
                "log_file_level": "ERROR",
                "log_file": "/tmp/test_observability.log"
            },
            "apps": [{
                "name": "test_app",
                "flows": [{
                    "name": "test_flow",
                    "components": [{
                        "component_name": "test_component",
                        "component_module": "pass_through"
                    }]
                }]
            }],
            "management_server": {
                "enabled": True,
                "port": port,
                "observability": obs_config
            }
        }

    def _get_metrics(self, port):
        """
        Helper: Fetch metrics from /metrics endpoint.

        Returns:
            String containing Prometheus-formatted metrics
        """
        response = urllib.request.urlopen(f"http://localhost:{port}/metrics")
        assert response.status == 200
        return response.read().decode()

    def _parse_metric_lines(self, metrics_output, metric_name):
        """
        Helper: Extract all lines for a specific metric from Prometheus output.

        Args:
            metrics_output: Full metrics text
            metric_name: Metric name to find

        Returns:
            List of lines (TYPE, HELP, and value lines) for the metric
        """
        lines = []
        for line in metrics_output.split('\n'):
            if line.startswith('#') and metric_name in line:
                lines.append(line)
            elif line.startswith(metric_name):
                lines.append(line)
        return lines

    def test_metrics_endpoint_availability_and_format(self):
        """Test /metrics endpoint is accessible and returns proper Prometheus format"""
        port = self._find_available_port()
        config = self._create_base_config(port)

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Fetch metrics
            response = urllib.request.urlopen(f"http://localhost:{port}/metrics")

            # Verify HTTP response
            assert response.status == 200
            assert response.getheader('Content-Type') == 'text/plain; version=0.0.4; charset=utf-8'

            # Parse metrics
            metrics = response.read().decode()

            # Verify Prometheus format
            assert '# TYPE' in metrics
            assert '# HELP' in metrics

            # Verify we got valid metrics output (should have at least Python GC metrics)
            assert 'python_gc_objects_collected_total' in metrics or 'target_info' in metrics

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_gauge_basic_operations(self):
        """Test push-style gauge increment/decrement operations"""
        port = self._find_available_port()
        config = self._create_base_config(port)

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Get registry and create gauge
            registry = MetricRegistry.get_instance()
            gauge = registry.create_gauge(
                name="test.queue.depth",
                description="Test queue depth gauge"
            )

            # Record increments
            gauge.record(1, {"queue": "main"})
            gauge.record(1, {"queue": "main"})
            gauge.record(1, {"queue": "main"})

            # Record decrement
            gauge.record(-1, {"queue": "main"})

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify metric exists (Prometheus naming: dots->underscores)
            assert 'sam_test_queue_depth' in metrics

            # Verify TYPE declaration
            assert '# TYPE sam_test_queue_depth' in metrics

            # Verify value is 2 (3 increments - 1 decrement)
            metric_lines = self._parse_metric_lines(metrics, 'sam_test_queue_depth')
            value_line = [l for l in metric_lines if l.startswith('sam_test_queue_depth{')][0]
            assert 'queue="main"' in value_line
            # Value should be 2.0
            assert ' 2.0' in value_line or ' 2' in value_line

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_gauge_label_filtering(self):
        """Test gauge label filtering excludes specified labels"""
        port = self._find_available_port()

        # Configure label filtering
        config = self._create_base_config(
            port,
            observability_config={
                "enabled": True,
                "path": "/metrics",
                "metric_prefix": "sam",
                "custom": {
                    "active.connections": {
                        "exclude_labels": ["connection_id", "internal_detail"]
                    }
                }
            }
        )

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Get registry and create gauge
            registry = MetricRegistry.get_instance()
            gauge = registry.create_gauge(
                name="active.connections",
                description="Active connections with filtering"
            )

            # Record with multiple labels including excluded ones
            gauge.record(1, {
                "broker": "prod",
                "connection_id": "conn-123",  # Should be filtered
                "internal_detail": "xyz"       # Should be filtered
            })

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify metric exists (Prometheus naming: dots->underscores)
            assert 'sam_active_connections' in metrics

            # Verify allowed label present
            assert 'broker="prod"' in metrics

            # Verify excluded labels NOT present
            assert 'connection_id' not in metrics
            assert 'internal_detail' not in metrics

            # Verify value is 1
            metric_lines = self._parse_metric_lines(metrics, 'sam_active_connections')
            value_line = [l for l in metric_lines if l.startswith('sam_active_connections{')][0]
            assert ' 1.0' in value_line or ' 1' in value_line

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_observable_gauge(self):
        """Test callback-based observable gauge"""
        port = self._find_available_port()
        config = self._create_base_config(port)

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Get registry
            registry = MetricRegistry.get_instance()

            # Define callback data
            queue_data = {"main": 10, "errors": 3}

            def report_queue_depth(options):
                from opentelemetry.metrics import Observation
                return [
                    Observation(queue_data["main"], {"queue": "main"}),
                    Observation(queue_data["errors"], {"queue": "errors"})
                ]

            # Create observable gauge
            obs_gauge = registry.create_observable_gauge(
                name="queue.current.depth",
                callbacks=[report_queue_depth],
                description="Current queue depth"
            )

            assert obs_gauge is not None

            # Fetch metrics (triggers callback)
            metrics = self._get_metrics(port)

            # Verify both observations present (Prometheus naming: dots->underscores)
            assert 'sam_queue_current_depth' in metrics

            metric_lines = self._parse_metric_lines(metrics, 'sam_queue_current_depth')
            value_lines = [l for l in metric_lines if l.startswith('sam_queue_current_depth{')]

            # Find the lines with specific queue labels
            main_line = [l for l in value_lines if 'queue="main"' in l][0]
            errors_line = [l for l in value_lines if 'queue="errors"' in l][0]

            # Verify values
            assert ' 10.0' in main_line or ' 10' in main_line
            assert ' 3.0' in errors_line or ' 3' in errors_line

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_counter_basic_operations(self):
        """Test counter increments and label combinations create separate series"""
        port = self._find_available_port()
        config = self._create_base_config(port)

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Get registry and create counter
            registry = MetricRegistry.get_instance()
            counter = registry.create_counter(
                name="events.processed",
                description="Events processed counter"
            )

            # Record multiple increments with different labels
            counter.record(5, {"gateway": "chat", "event_type": "message"})
            counter.record(3, {"gateway": "chat", "event_type": "message"})  # Same labels
            counter.record(2, {"gateway": "chat", "event_type": "command"})   # Different event_type
            counter.record(1, {"gateway": "api", "event_type": "message"})    # Different gateway

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify metric exists (Prometheus naming: dots->underscores, _total suffix for counters)
            assert 'sam_events_processed_total' in metrics

            # Verify TYPE declaration
            assert '# TYPE sam_events_processed_total counter' in metrics

            # Parse metric lines
            metric_lines = self._parse_metric_lines(metrics, 'sam_events_processed_total')
            value_lines = [l for l in metric_lines if l.startswith('sam_events_processed_total{')]

            # Verify three separate counter series exist
            chat_message = [l for l in value_lines if 'gateway="chat"' in l and 'event_type="message"' in l][0]
            chat_command = [l for l in value_lines if 'gateway="chat"' in l and 'event_type="command"' in l][0]
            api_message = [l for l in value_lines if 'gateway="api"' in l and 'event_type="message"' in l][0]

            # Verify accumulated values
            assert ' 8.0' in chat_message or ' 8' in chat_message  # 5 + 3
            assert ' 2.0' in chat_command or ' 2' in chat_command
            assert ' 1.0' in api_message or ' 1' in api_message

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_counter_label_filtering(self):
        """Test counter label filtering aggregates at higher level"""
        port = self._find_available_port()

        # Configure label filtering
        config = self._create_base_config(
            port,
            observability_config={
                "enabled": True,
                "path": "/metrics",
                "metric_prefix": "sam",
                "custom": {
                    "requests.total": {
                        "exclude_labels": ["request_id", "trace_id"]
                    }
                }
            }
        )

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Get registry and create counter
            registry = MetricRegistry.get_instance()
            counter = registry.create_counter(
                name="requests.total",
                description="Total requests with filtering"
            )

            # Record with multiple labels including excluded ones
            counter.record(1, {
                "endpoint": "/api/users",
                "status": "200",
                "request_id": "req-123",  # Should be filtered
                "trace_id": "trace-abc"   # Should be filtered
            })
            counter.record(1, {
                "endpoint": "/api/users",
                "status": "200",
                "request_id": "req-456",  # Different ID, should still aggregate
                "trace_id": "trace-def"   # Different trace, should still aggregate
            })
            counter.record(1, {
                "endpoint": "/api/users",
                "status": "500",
                "request_id": "req-789",
                "trace_id": "trace-ghi"
            })

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify metric exists (Prometheus naming: dots->underscores)
            # Note: "requests.total" becomes "sam_requests_total" (already has total in name)
            assert 'sam_requests_total' in metrics

            # Verify excluded labels NOT present
            assert 'request_id' not in metrics
            assert 'trace_id' not in metrics

            # Parse metric lines
            metric_lines = self._parse_metric_lines(metrics, 'sam_requests_total')
            value_lines = [l for l in metric_lines if l.startswith('sam_requests_total{')]

            # Find aggregated counters
            status_200 = [l for l in value_lines if 'endpoint="/api/users"' in l and 'status="200"' in l][0]
            status_500 = [l for l in value_lines if 'endpoint="/api/users"' in l and 'status="500"' in l][0]

            # Verify aggregation (2 requests with status 200 despite different request_id/trace_id)
            assert ' 2.0' in status_200 or ' 2' in status_200
            assert ' 1.0' in status_500 or ' 1' in status_500

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_histogram_sync_decorator(self):
        """Test MonitorLatency as synchronous decorator"""
        port = self._find_available_port()
        config = self._create_base_config(port)

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Define decorated function
            @MonitorLatency(OperationMonitor.instance(
                component_type="processor",
                component_name="test_processor",
                operation="process_data"
            ))
            def process_data():
                time.sleep(0.05)
                return "done"

            # Call function
            result = process_data()
            assert result == "done"

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify histogram exists (Prometheus naming: _seconds suffix for duration)
            assert 'sam_operation_duration_seconds' in metrics

            # Verify TYPE declaration
            assert '# TYPE sam_operation_duration_seconds histogram' in metrics

            # Parse metric lines
            metric_lines = self._parse_metric_lines(metrics, 'sam_operation_duration_seconds')

            # Find lines with our specific labels (Prometheus converts dots to underscores)
            relevant_lines = [
                l for l in metric_lines
                if 'type="processor"' in l
                and 'component_name="test_processor"' in l
                and 'operation_name="process_data"' in l
                and 'error_type="none"' in l
            ]

            assert len(relevant_lines) > 0, "Expected histogram buckets with correct labels"

            # Verify at least one bucket has count >= 1
            bucket_lines = [l for l in relevant_lines if '_bucket{' in l]
            assert any('_bucket{' in l and not l.endswith(' 0') for l in bucket_lines)

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_histogram_async_decorator(self):
        """Test MonitorLatency as asynchronous decorator"""
        port = self._find_available_port()
        config = self._create_base_config(port)

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Define async decorated function
            @MonitorLatency(OperationMonitor.instance(
                component_type="async_processor",
                component_name="test_async",
                operation="async_process"
            ))
            async def async_process_data():
                await asyncio.sleep(0.05)
                return "done"

            # Call async function
            result = asyncio.run(async_process_data())
            assert result == "done"

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify histogram exists
            assert 'sam_operation_duration_seconds' in metrics

            # Parse metric lines
            metric_lines = self._parse_metric_lines(metrics, 'sam_operation_duration_seconds')

            # Find lines with our specific labels
            relevant_lines = [
                l for l in metric_lines
                if 'type="async_processor"' in l
                and 'component_name="test_async"' in l
                and 'operation_name="async_process"' in l
                and 'error_type="none"' in l
            ]

            assert len(relevant_lines) > 0, "Expected histogram buckets with correct labels"

            # Verify at least one bucket has count >= 1
            bucket_lines = [l for l in relevant_lines if '_bucket{' in l]
            assert any('_bucket{' in l and not l.endswith(' 0') for l in bucket_lines)

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_histogram_sync_context(self):
        """Test MonitorLatency with synchronous context manager"""
        port = self._find_available_port()
        config = self._create_base_config(port)

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Use context manager
            with MonitorLatency(OperationMonitor.instance(
                component_type="service",
                component_name="test_service",
                operation="sync_operation"
            )):
                time.sleep(0.05)

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify histogram exists
            assert 'sam_operation_duration_seconds' in metrics

            # Parse metric lines
            metric_lines = self._parse_metric_lines(metrics, 'sam_operation_duration_seconds')

            # Find lines with our specific labels
            relevant_lines = [
                l for l in metric_lines
                if 'type="service"' in l
                and 'component_name="test_service"' in l
                and 'operation_name="sync_operation"' in l
                and 'error_type="none"' in l
            ]

            assert len(relevant_lines) > 0, "Expected histogram buckets with correct labels"

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_histogram_async_context(self):
        """Test MonitorLatency with asynchronous context manager"""
        port = self._find_available_port()
        config = self._create_base_config(port)

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Use async context manager
            async def run_async_context():
                async with MonitorLatency(OperationMonitor.instance(
                    component_type="async_service",
                    component_name="test_async_service",
                    operation="async_context_op"
                )):
                    await asyncio.sleep(0.05)

            asyncio.run(run_async_context())

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify histogram exists
            assert 'sam_operation_duration_seconds' in metrics

            # Parse metric lines
            metric_lines = self._parse_metric_lines(metrics, 'sam_operation_duration_seconds')

            # Find lines with our specific labels
            relevant_lines = [
                l for l in metric_lines
                if 'type="async_service"' in l
                and 'component_name="test_async_service"' in l
                and 'operation_name="async_context_op"' in l
                and 'error_type="none"' in l
            ]

            assert len(relevant_lines) > 0, "Expected histogram buckets with correct labels"

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_histogram_manual_start_stop(self):
        """Test MonitorLatency with manual start()/stop() calls"""
        port = self._find_available_port()
        config = self._create_base_config(port)

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Create monitor and use manually
            monitor = MonitorLatency(OperationMonitor.instance(
                component_type="manual",
                component_name="test_manual",
                operation="manual_operation"
            ))

            monitor.start()
            time.sleep(0.05)
            monitor.stop()

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify histogram exists
            assert 'sam_operation_duration_seconds' in metrics

            # Parse metric lines
            metric_lines = self._parse_metric_lines(metrics, 'sam_operation_duration_seconds')

            # Find lines with our specific labels
            relevant_lines = [
                l for l in metric_lines
                if 'type="manual"' in l
                and 'component_name="test_manual"' in l
                and 'operation_name="manual_operation"' in l
                and 'error_type="none"' in l
            ]

            assert len(relevant_lines) > 0, "Expected histogram buckets with correct labels"

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_histogram_error_handling(self):
        """Test that exceptions are captured in error.type label"""
        port = self._find_available_port()
        config = self._create_base_config(port)

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Test with decorator
            @MonitorLatency(OperationMonitor.instance(
                component_type="error_test",
                component_name="test_errors",
                operation="failing_operation"
            ))
            def failing_function():
                raise ValueError("Test error")

            try:
                failing_function()
            except ValueError:
                pass  # Expected

            # Test with context manager
            try:
                with MonitorLatency(OperationMonitor.instance(
                    component_type="error_test",
                    component_name="test_errors",
                    operation="context_fail"
                )):
                    raise RuntimeError("Context error")
            except RuntimeError:
                pass  # Expected

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify histogram exists
            assert 'sam_operation_duration_seconds' in metrics

            # Parse metric lines
            metric_lines = self._parse_metric_lines(metrics, 'sam_operation_duration_seconds')

            # Find lines with error labels (error_type should NOT be "none")
            error_lines = [
                l for l in metric_lines
                if 'component_name="test_errors"' in l
                and 'error_type=' in l
                and 'error_type="none"' not in l
            ]

            assert len(error_lines) > 0, "Expected histogram buckets with error_type labels"

            # Verify both error types are captured
            failing_op_errors = [l for l in error_lines if 'operation_name="failing_operation"' in l]
            context_fail_errors = [l for l in error_lines if 'operation_name="context_fail"' in l]

            assert len(failing_op_errors) > 0, "Expected error_type for failing_operation"
            assert len(context_fail_errors) > 0, "Expected error_type for context_fail"

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_histogram_label_filtering(self):
        """Test histogram label filtering aggregates at higher level"""
        port = self._find_available_port()

        # Configure label filtering for db.duration
        config = self._create_base_config(
            port,
            observability_config={
                "enabled": True,
                "path": "/metrics",
                "metric_prefix": "sam",
                "system": {
                    "db.duration": {
                        "exclude_labels": ["db.operation.name"]
                    }
                }
            }
        )

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Perform different operations on same collection
            with MonitorLatency(DBMonitor.query(collection="users")):
                time.sleep(0.01)

            with MonitorLatency(DBMonitor.insert(collection="users")):
                time.sleep(0.01)

            # Perform operation on different collection
            with MonitorLatency(DBMonitor.query(collection="sessions")):
                time.sleep(0.01)

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify metric exists (Prometheus naming: _seconds suffix)
            assert 'sam_db_duration_seconds' in metrics

            # Verify db.collection.name label present (OpenTelemetry keeps label names as-is)
            assert 'db_collection_name=' in metrics

            # Verify db.operation.name label NOT present (filtered)
            metric_lines = self._parse_metric_lines(metrics, 'sam_db_duration_seconds')
            db_lines = [l for l in metric_lines if l.startswith('sam_db_duration_seconds')]

            for line in db_lines:
                assert 'db_operation_name=' not in line, f"db_operation_name should be filtered: {line}"

            # Verify aggregation at collection level
            users_count_lines = [l for l in db_lines if 'db_collection_name="users"' in l and '_count{' in l]
            sessions_count_lines = [l for l in db_lines if 'db_collection_name="sessions"' in l and '_count{' in l]

            # Users collection should have count 2 (query + insert aggregated)
            assert len(users_count_lines) > 0, "Expected histogram count for users collection"
            users_count_line = users_count_lines[0]
            count_value = float(users_count_line.split()[-1])
            assert count_value == 2.0, f"Expected count 2 for users, got {count_value}"

            # Sessions collection should have count 1
            assert len(sessions_count_lines) > 0, "Expected histogram count for sessions collection"
            sessions_count_line = sessions_count_lines[0]
            count_value = float(sessions_count_line.split()[-1])
            assert count_value == 1.0, f"Expected count 1 for sessions, got {count_value}"

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass

    def test_metric_prefix_applied(self):
        """Test metric_prefix configuration is applied to all metrics"""
        port = self._find_available_port()
        config = self._create_base_config(port, metric_prefix="custom_prefix")

        sac = None
        try:
            sac = SolaceAiConnector(config)
            with patch.object(sac, 'wait_for_flows'):
                sac.run()
            time.sleep(0.2)

            # Get registry
            registry = MetricRegistry.get_instance()

            # Create custom metrics
            counter = registry.create_counter("test.counter")
            gauge = registry.create_gauge("test.gauge")

            # Record values
            counter.record(1, {"label": "value"})
            gauge.record(1, {"label": "value"})

            # Use built-in histogram
            with MonitorLatency(OperationMonitor.instance(
                component_type="test",
                component_name="prefix_test",
                operation="test_op"
            )):
                time.sleep(0.01)

            # Fetch metrics
            metrics = self._get_metrics(port)

            # Verify all metrics have custom prefix (Prometheus naming: dots->underscores)
            assert 'custom_prefix_test_counter_total' in metrics
            assert 'custom_prefix_test_gauge' in metrics
            assert 'custom_prefix_operation_duration_seconds' in metrics

            # Verify metrics do NOT appear with default prefix
            assert 'sam_test_counter' not in metrics
            assert 'sam_test_gauge' not in metrics

            # Check that unprefixed version doesn't exist
            lines = metrics.split('\n')
            for line in lines:
                if line.startswith('test_counter') or line.startswith('test_gauge'):
                    assert False, f"Found metric without prefix: {line}"

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass