"""Configuration loading and validation for observability framework."""

import logging
from typing import Dict, List

log = logging.getLogger(__name__)


# Default configurations for each histogram family
DEFAULT_METRIC_CONFIGS = {
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
            log.debug("Using management_server.observability config")
            return mgmt['observability']

    log.debug("No observability config found - disabled")
    return {'enabled': False}


def validate_buckets(buckets: List[float], metric_name: str):
    """
    Validate bucket configuration.

    Args:
        buckets: Bucket boundaries
        metric_name: Metric name (for error messages)

    Raises:
        ValueError: If buckets are invalid
    """
    if not buckets:
        return  # Empty = disabled, valid

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
    reserved_keys = {'enabled', 'metric_prefix', 'path', 'system', 'custom'}

    # Validate no unknown top-level keys (catches stale configs)
    for key in obs_config.keys():
        if key not in reserved_keys:
            raise ValueError(
                f"Unknown configuration key '{key}'. "
                f"Valid keys: {sorted(reserved_keys)}"
            )

    # Validate system: section (built-in histogram tuning)
    if 'system' in obs_config:
        system_config = obs_config['system']
        if not isinstance(system_config, dict):
            raise ValueError("'system' must be a dictionary")

        for metric_name, metric_config in system_config.items():
            # Check if metric name is valid
            if metric_name not in DEFAULT_METRIC_CONFIGS:
                raise ValueError(
                    f"Unknown system metric '{metric_name}'. "
                    f"Valid metrics: {list(DEFAULT_METRIC_CONFIGS.keys())}"
                )

            # Validate buckets if provided
            if 'values' in metric_config:
                validate_buckets(metric_config['values'], metric_name)

            # Validate exclude_labels if provided
            if 'exclude_labels' in metric_config:
                exclude_labels = metric_config['exclude_labels']
                if not isinstance(exclude_labels, list):
                    raise ValueError(f"system.{metric_name}.exclude_labels must be a list")
                if not all(isinstance(label, str) for label in exclude_labels):
                    raise ValueError(f"system.{metric_name}.exclude_labels must contain only strings")

    # Validate custom: section (custom metric label filtering)
    if 'custom' in obs_config:
        custom_config = obs_config['custom']
        if not isinstance(custom_config, dict):
            raise ValueError("'custom' must be a dictionary")

        for metric_name, metric_config in custom_config.items():
            if not isinstance(metric_config, dict):
                raise ValueError(f"custom.{metric_name} must be a dictionary")

            # Only exclude_labels is allowed for custom metrics
            for key in metric_config.keys():
                if key != 'exclude_labels':
                    raise ValueError(
                        f"custom.{metric_name}: only 'exclude_labels' is allowed, got '{key}'"
                    )

            # Validate exclude_labels if provided
            if 'exclude_labels' in metric_config:
                exclude_labels = metric_config['exclude_labels']
                if not isinstance(exclude_labels, list):
                    raise ValueError(f"custom.{metric_name}.exclude_labels must be a list")
                if not all(isinstance(label, str) for label in exclude_labels):
                    raise ValueError(f"custom.{metric_name}.exclude_labels must contain only strings")