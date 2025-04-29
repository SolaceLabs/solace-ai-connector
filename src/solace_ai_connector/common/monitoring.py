from typing import Any, List, Callable
from enum import Enum
from threading import Lock

from ..common.messaging.solace_messaging import ConnectionStatus


class Metrics(Enum):
    SOLCLIENT_STATS_RX_SETTLE_ACCEPTED = "SOLCLIENT_STATS_RX_SETTLE_ACCEPTED"
    SOLCLIENT_STATS_RX_SETTLE_FAILED = "SOLCLIENT_STATS_RX_SETTLE_FAILED"
    SOLCLIENT_STATS_RX_SETTLE_REJECTED = "SOLCLIENT_STATS_RX_SETTLE_REJECTED"
    SOLCLIENT_STATS_TX_TOTAL_CONNECTION_ATTEMPTS = (
        "SOLCLIENT_STATS_TX_TOTAL_CONNECTION_ATTEMPTS"
    )
    LITELLM_STATS_PROMPT_TOKENS = "LITELLM_STATS_PROMPT_TOKENS"
    LITELLM_STATS_RESPONSE_TOKENS = "LITELLM_STATS_RESPONSE_TOKENS"
    LITELLM_STATS_TOTAL_TOKENS = "LITELLM_STATS_TOTAL_TOKENS"
    LITELLM_STATS_RESPONSE_TIME = "LITELLM_STATS_RESPONSE_TIME"
    LITELLM_STATS_COST = "LITELLM_STATS_COST"


class Monitoring:
    """
    A singleton class to collect and send metrics.
    """

    _instance = None
    _initialized = False
    _interval = 10
    _reset_callback = []

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Monitoring, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: dict[str, Any] = None) -> None:
        """
        Initialize the Monitoring instance with configuration.

        :param config: Configuration for Monitoring
        """
        if self._initialized:
            return

        self._initialized = True
        self._is_flush_manual = config.get("manual_flush", False) if config else False
        self._collected_metrics = {}
        self._connection_status = {}
        self._lock = Lock()
        self._initialize_metrics()

    def _initialize_metrics(self) -> None:
        """
        Initialize the required metrics.
        """
        self._required_metrics = [metric for metric in Metrics]

    def is_flush_manual(self) -> bool:
        """
        Check if the metrics are manually flushed.

        :return: True if metrics are manually flushed, False otherwise
        """
        return self._is_flush_manual

    def register_callback(self, method: Callable) -> None:
        """
        Register methods to flush metrics.

        :param method: Method to register
        """
        self._reset_callback.append(method)

    def get_required_metrics(self) -> List[Metrics]:
        """
        Get the list of required metrics.

        :return: List of required metrics
        """
        return self._required_metrics

    def set_required_metrics(self, required_metrics: List[Metrics]) -> None:
        """
        Set the list of required metrics.

        :param required_metrics: List of required metrics
        """
        self._required_metrics = [metric for metric in required_metrics]

    def set_interval(self, interval: int) -> None:
        """
        Set the interval for metric collection.

        :param interval: Interval in seconds
        """
        self._interval = interval

    def get_interval(self) -> int:
        """
        Get the interval for metric collection.

        :return: Interval in seconds
        """
        return self._interval

    def set_connection_status(self, key, value: int) -> None:
        """
        Set the connection status of the broker.

        :param key: Key for the connection status
        :param value: Connection status value
        """
        self._connection_status[key] = value

    def get_connection_status(self) -> int:
        """
        Get the connection status of the broker.

        :return: Connection status value
        """
        started = True
        status = ConnectionStatus.DISCONNECTED
        for _, value in self._connection_status.items():
            if started:
                status = value
                started = False

            if (
                status == ConnectionStatus.CONNECTED
                and value == ConnectionStatus.RECONNECTING
            ):
                status = ConnectionStatus.RECONNECTING

            if value == ConnectionStatus.DISCONNECTED:
                status = ConnectionStatus.DISCONNECTED
                break

        return status

    def collect_metrics(self, metrics: dict[Metrics, dict[Metrics, Any]]) -> None:
        """
        Collect metrics.

        :param metrics: Dictionary of metrics to collect
        """
        with self._lock:
            for key, value in metrics.items():
                self._collected_metrics[key] = value

    def get_detailed_metrics(self) -> List[dict[str, Any]]:
        """
        Retrieve detailed collected metrics.

        :return: List of detailed collected metrics
        """
        return self._collected_metrics

    def get_aggregated_metrics(
        self, required_metrics: List[Metrics] = None
    ) -> List[dict[str, Any]]:
        """
        Retrieve aggregated collected metrics.

        :param required_metrics: List of required metrics to aggregate
        :return: List of aggregated collected metrics
        """
        aggregated_metrics = self._aggregate_metrics(required_metrics)
        return self._format_metrics(aggregated_metrics)

    def _aggregate_metrics(self, required_metrics: List[Metrics]) -> dict:
        """
        Aggregate the collected metrics.

        :param required_metrics: List of required metrics to aggregate
        :return: Dictionary of aggregated metrics
        """
        aggregated_metrics = {}
        for key, value in self._collected_metrics.items():
            metric = next(item[1] for item in key if item[0] == "metric")
            if required_metrics and metric not in required_metrics:
                continue
            new_key = self._filter_key(key)
            self._update_aggregated_metrics(aggregated_metrics, new_key, metric, value)
        return aggregated_metrics

    def _filter_key(self, key: tuple) -> tuple:
        """
        Filter the key to remove flow, flow_index, component_module, and component_index.

        :param key: Original key
        :return: Filtered key
        """
        return tuple(
            item
            for item in key
            if item[0]
            not in ["flow", "flow_index", "component_module", "component_index"]
        )

    def _update_aggregated_metrics(
        self, aggregated_metrics: dict, new_key: tuple, metric: Metrics, value: Any
    ) -> None:
        """
        Aggregate values of a component's metric for all instances in flows.

        :param aggregated_metrics: Dictionary of aggregated metrics
        :param new_key: Filtered key
        :param metric: Metric type
        :param value: Metric value
        """
        if new_key not in aggregated_metrics:
            aggregated_metrics[new_key] = value
        elif metric in [
            Metrics.SOLCLIENT_STATS_RX_SETTLE_ACCEPTED,
            Metrics.SOLCLIENT_STATS_RX_SETTLE_FAILED,
            Metrics.SOLCLIENT_STATS_RX_SETTLE_REJECTED,
            Metrics.SOLCLIENT_STATS_TX_TOTAL_CONNECTION_ATTEMPTS,
        ]:
            aggregated_timestamp = aggregated_metrics[new_key].timestamp
            metric_value = value.value
            metric_timestamp = value.timestamp
            aggregated_metrics[new_key].value += sum(metric_value)
            if metric_timestamp > aggregated_timestamp:
                aggregated_metrics[new_key].timestamp = metric_timestamp
        elif metric in [
            Metrics.LITELLM_STATS_PROMPT_TOKENS,
            Metrics.LITELLM_STATS_RESPONSE_TOKENS,
            Metrics.LITELLM_STATS_TOTAL_TOKENS,
            Metrics.LITELLM_STATS_RESPONSE_TIME,
            Metrics.LITELLM_STATS_COST,
        ]:
            aggregated_metrics[new_key] = value

    def _format_metrics(self, aggregated_metrics: dict) -> List[dict[str, Any]]:
        """
        Format the aggregated metrics for output.

        :param aggregated_metrics: Dictionary of aggregated metrics
        :return: List of formatted metrics
        """
        formatted_metrics = []
        for key, value in aggregated_metrics.items():
            metric_dict = dict(key)
            if metric_dict.get("metric") in [
                Metrics.LITELLM_STATS_PROMPT_TOKENS,
                Metrics.LITELLM_STATS_RESPONSE_TOKENS,
                Metrics.LITELLM_STATS_TOTAL_TOKENS,
                Metrics.LITELLM_STATS_RESPONSE_TIME,
                Metrics.LITELLM_STATS_COST,
            ]:
                for sub_metric in value:
                    formatted_metrics.append(
                        {
                            "component": metric_dict.get("component"),
                            "metric": metric_dict.get("metric"),
                            "timestamp": sub_metric["timestamp"],
                            "value": sub_metric["value"],
                        }
                    )
            else:
                formatted_metrics.append(
                    {
                        "component": metric_dict.get("component"),
                        "metric": metric_dict.get("metric"),
                        "timestamp": value["timestamp"],
                        "value": value["value"],
                    }
                )
        return formatted_metrics

    def flush_metrics(self) -> None:
        """
        Flush the collected metrics.
        """
        for callback in self._reset_callback:
            callback()
