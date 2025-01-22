from typing import Any, List
from enum import Enum
from threading import Lock

from ..common.messaging.solace_messaging import ConnectionStatus


class Metrics(Enum):
    SOLCLIENT_STATS_RX_SETTLE_ACCEPTED = "SOLCLIENT_STATS_RX_SETTLE_ACCEPTED"
    SOLCLIENT_STATS_TX_TOTAL_CONNECTION_ATTEMPTS = (
        "SOLCLIENT_STATS_TX_TOTAL_CONNECTION_ATTEMPTS"
    )

    @staticmethod
    def get_type(metric: "Metrics") -> str:
        """
        Get the type of the metric.

        :param metric: Metric
        :return: Type of the metric
        """
        if metric in [
            Metrics.SOLCLIENT_STATS_RX_SETTLE_ACCEPTED,
            Metrics.SOLCLIENT_STATS_TX_TOTAL_CONNECTION_ATTEMPTS,
        ]:
            return "integer"
        # Add more cases here if needed
        return "unknown"


class Monitoring:
    """
    A singleton class to collect and send metrics.
    """

    _instance = None
    _initialized = False
    _interval = 10

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Monitoring, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: dict[str, Any] = None) -> None:
        """
        Initialize the MetricCollector with Datadog configuration.

        :param config: Configuration for Datadog
        """

        if self._initialized:
            return

        self._initialized = True
        self._collected_metrics = {}
        self._connection_status = {}
        self._lock = Lock()
        self._initialize_metrics()

    def _initialize_metrics(self) -> None:
        """
        Initialize the MetricCollector.
        """
        self._required_metrics = [metric for metric in Metrics]

    def get_required_metrics(self) -> List[Metrics]:
        """
        Get the required metrics for the MetricCollector.

        :return: List of required metrics
        """
        return self._required_metrics

    def set_required_metrics(self, required_metrics: List[Metrics]) -> None:
        """
        Set the required metrics for the MetricCollector.

        :param required_metrics: List of required metrics
        """
        self._required_metrics = [metric for metric in required_metrics]

    def set_interval(self, interval: int) -> None:
        """
        Set the interval for the MetricCollector.

        :param interval: Interval
        """
        self._interval = interval

    def get_interval(self) -> int:
        """
        Get the interval for the MetricCollector.

        :return: Interval
        """
        return self._interval

    def set_connection_status(self, key, value: int) -> None:
        """
        Set the connection status of the broker.

        :param key: Key
        """
        self._connection_status[key] = value

    def get_connection_status(self) -> int:
        """
        Get the connection status of the broker.
        """
        started = True
        # default status is disconnected
        status = ConnectionStatus.DISCONNECTED
        for _, value in self._connection_status.items():
            if started:
                status = value
                started = False

            # if a module is connecting, the status is connecting
            if (
                status == ConnectionStatus.CONNECTED
                and value == ConnectionStatus.RECONNECTING
            ):
                status = ConnectionStatus.RECONNECTING

            # if a module is disconnected, the status is disconnected
            if value == ConnectionStatus.DISCONNECTED:
                status = ConnectionStatus.DISCONNECTED
                break

        return status

    def collect_metrics(self, metrics: dict[Metrics, dict[Metrics, Any]]) -> None:
        """
        Collect metrics.

        :param metrics: Dictionary of metrics
        """
        with self._lock:
            for key, value in metrics.items():
                self._collected_metrics[key] = value

    def get_detailed_metrics(self) -> List[dict[str, Any]]:
        """
        Retrieve collected metrics.

        :return: Dictionary of collected metrics
        """
        return self._collected_metrics

    def get_aggregated_metrics(
        self, required_metrics: List[Metrics] = None
    ) -> List[dict[str, Any]]:
        """
        Retrieve collected metrics.

        :return: Dictionary of collected metrics
        """
        aggregated_metrics = {}
        for key, value in self._collected_metrics.items():
            # get metric
            metric = next(item[1] for item in key if item[0] == "metric")

            # skip metrics that are not required
            if required_metrics and metric not in required_metrics:
                continue

            # filter flow, flow_index, component, component_index from key
            new_key = tuple(
                item
                for item in key
                if item[0]
                not in ["flow", "flow_index", "component_module", "component_index"]
            )

            if new_key not in aggregated_metrics:
                aggregated_metrics[new_key] = value
            else:
                # aggregate metrics: sum
                aggregated_timestamp = aggregated_metrics[new_key].timestamp
                metric_value = value.value
                metric_timestamp = value.timestamp

                if metric in [
                    Metrics.SOLCLIENT_STATS_RX_SETTLE_ACCEPTED,
                    Metrics.SOLCLIENT_STATS_TX_TOTAL_CONNECTION_ATTEMPTS,
                ]:  # add metrics that need to be aggregated by sum
                    aggregated_metrics[new_key].value += sum(metric_value)

                # set timestamp to the latest
                if metric_timestamp > aggregated_timestamp:
                    aggregated_metrics[new_key].timestamp = metric_timestamp

        # convert to dictionary
        formatted_metrics = []
        for key, value in aggregated_metrics.items():
            metric_dict = dict(key)
            formatted_metrics.append(
                {
                    "component": metric_dict.get("component"),
                    "metric": metric_dict.get("metric"),
                    "timestamp": value["timestamp"],
                    "value": value["value"],
                }
            )

        return formatted_metrics
