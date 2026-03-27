"""Configuration loading and validation for observability framework."""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Default configurations for distribution metrics (histograms)
DEFAULT_DISTRIBUTION_METRICS = {
    "outbound.request.duration": {
        "buckets": [0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        "exclude_labels": []
    },
    "gen_ai.client.operation.duration": {
        "buckets": [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0],
        "exclude_labels": ["tokens"]
    },
    "gen_ai.client.operation.ttft.duration": {
        "buckets": [0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0],
        "exclude_labels": []
    },
    "db.duration": {
        "buckets": [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
        "exclude_labels": []
    },
    "gateway.duration": {
        "buckets": [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        "exclude_labels": []
    },
    "gateway.ttfb.duration": {
        "buckets": [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        "exclude_labels": []
    },
    "operation.duration": {
        "buckets": [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        "exclude_labels": []
    }
}


# Default configurations for value metrics (counters and gauges)
DEFAULT_VALUE_METRICS = {
    "gen_ai.tokens.used": {
        "exclude_labels": ["owner.id"]  # Default: component-level visibility only
    },
    "gen_ai.cost.total": {
        "exclude_labels": ["owner.id"]  # Default: component-level visibility only
    }
}


def load_observability_config(config: dict) -> dict:
    """
    Load observability config from management_server.observability.

    Args:
        config: Full connector configuration

    Returns:
        Observability configuration dict
    """
    if 'management_server' in config:
        mgmt = config['management_server']
        if 'observability' in mgmt:
            logger.debug("Using management_server.observability config")
            return mgmt['observability']

    logger.debug("No observability config found - disabled")
    return {'enabled': False}


def validate_buckets(buckets: List[float], metric_name: str):
    """
    Validate bucket configuration.

    Args:
        buckets: Bucket boundaries (must not be empty - caller validates)
        metric_name: Metric name (for error messages)

    Raises:
        ValueError: If buckets are invalid
    """
    if not all(isinstance(b, (int, float)) for b in buckets):
        raise ValueError(f"{metric_name}: buckets must be numeric")

    if buckets != sorted(buckets):
        raise ValueError(f"{metric_name}: buckets must be in ascending order")

    if any(b <= 0 for b in buckets):
        raise ValueError(f"{metric_name}: buckets must be positive")


def validate_config(obs_config: dict):
    """
    Validate observability configuration.

    Args:
        obs_config: User observability config

    Raises:
        ValueError: If configuration is invalid
    """
    # Reserved top-level keys
    reserved_keys = {'enabled', 'metric_prefix', 'path', 'distribution_metrics', 'value_metrics'}

    # Validate no unknown top-level keys (catches stale configs)
    for key in obs_config.keys():
        if key not in reserved_keys:
            raise ValueError(
                f"Unknown configuration key '{key}'. "
                f"Valid keys: {sorted(reserved_keys)}"
            )

    # Validate distribution_metrics:
    if 'distribution_metrics' in obs_config:
        distribution_config = obs_config['distribution_metrics']
        if not isinstance(distribution_config, dict):
            raise ValueError("'distribution_metrics' must be a dictionary")

        for metric_name, metric_config in distribution_config.items():
            if not isinstance(metric_config, dict):
                raise ValueError(f"distribution_metrics.{metric_name} must be a dictionary")

            # Check if explicitly disabled
            exclude_labels = metric_config.get('exclude_labels', [])
            if exclude_labels == ["*"]:
                # Explicitly disabled - no further validation needed
                continue

            # Check if buckets are provided
            if 'buckets' in metric_config:
                buckets = metric_config['buckets']

                # buckets must be a list
                if not isinstance(buckets, list):
                    raise ValueError(f"distribution_metrics.{metric_name}.buckets must be a list")

                # Empty buckets is an ERROR
                if len(buckets) == 0:
                    raise ValueError(
                        f"distribution_metrics.{metric_name}: buckets cannot be empty. "
                        f"Use exclude_labels: ['*'] to disable this metric."
                    )

                validate_buckets(buckets, f"distribution_metrics.{metric_name}")
            else:
                # No buckets provided
                # Built-in metrics: OK, will use defaults
                # Custom metrics: ERROR, no defaults available
                if metric_name not in DEFAULT_DISTRIBUTION_METRICS:
                    raise ValueError(
                        f"distribution_metrics.{metric_name}: 'buckets' is required for custom metrics. "
                        f"Use exclude_labels: ['*'] to disable this metric."
                    )

            # Validate exclude_labels if provided
            if 'exclude_labels' in metric_config:
                if not isinstance(exclude_labels, list):
                    raise ValueError(f"distribution_metrics.{metric_name}.exclude_labels must be a list")
                if not all(isinstance(label, str) for label in exclude_labels):
                    raise ValueError(f"distribution_metrics.{metric_name}.exclude_labels must contain only strings")

    # Validate value_metrics: (counters and gauges)
    if 'value_metrics' in obs_config:
        value_config = obs_config['value_metrics']
        if not isinstance(value_config, dict):
            raise ValueError("'value_metrics' must be a dictionary")

        for metric_name, metric_config in value_config.items():
            if not isinstance(metric_config, dict):
                raise ValueError(f"value_metrics.{metric_name} must be a dictionary")

            # Check if explicitly disabled
            exclude_labels = metric_config.get('exclude_labels', [])
            if exclude_labels == ["*"]:
                # Explicitly disabled - no further validation needed
                continue

            # Only exclude_labels is allowed for value metrics
            allowed_keys = {'exclude_labels'}
            for key in metric_config.keys():
                if key not in allowed_keys:
                    raise ValueError(
                        f"value_metrics.{metric_name}: only 'exclude_labels' is allowed, got '{key}'"
                    )

            # Validate exclude_labels if provided
            if 'exclude_labels' in metric_config:
                if not isinstance(exclude_labels, list):
                    raise ValueError(f"value_metrics.{metric_name}.exclude_labels must be a list")
                if not all(isinstance(label, str) for label in exclude_labels):
                    raise ValueError(f"value_metrics.{metric_name}.exclude_labels must contain only strings")