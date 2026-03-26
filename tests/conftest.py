"""Root conftest for pytest configuration."""
import pytest
import sys

sys.path.append("src")

from solace_ai_connector.common.observability.registry import MetricRegistry


@pytest.fixture(autouse=True)
def reset_metric_registry():
    """Reset MetricRegistry singleton before each test."""
    # Reset before the test
    MetricRegistry.reset()
    yield
    # Reset after the test as well for cleanup
    MetricRegistry.reset()