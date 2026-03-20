"""MetricRegistry for managing OpenTelemetry metrics."""

from typing import Optional, Dict, List, Callable
import logging
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.view import View, ExplicitBucketHistogramAggregation
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.metrics import Observation
from prometheus_client import generate_latest, REGISTRY

from .config import DEFAULT_METRIC_CONFIGS, load_observability_config, validate_config
from .recorders import MetricRecorder, NoOpRecorder, HistogramRecorder, CounterRecorder, GaugeRecorder

log = logging.getLogger(__name__)


class MetricRegistry:
    """
    Singleton registry for metrics collection.
    """

    _instance: Optional['MetricRegistry'] = None

    def __init__(self, config: dict):
        """Initialize registry with configuration."""
        if MetricRegistry._instance is not None:
            raise RuntimeError("MetricRegistry already initialized. Use get_instance().")

        # Load observability config
        self.obs_config = load_observability_config(config)

        # Check if observability is enabled
        self.enabled = self.obs_config.get('enabled', False)
        if not self.enabled:
            log.info("Observability disabled in configuration")
            self.recorders = {}
            self._custom_configs = {}
            MetricRegistry._instance = self
            return

        # Validate configuration
        validate_config(self.obs_config)

        # Extract prefix (optional)
        self.metric_prefix = self.obs_config.get('metric_prefix', '')

        # Store custom metric configs for factory methods
        self._custom_configs = self.obs_config.get('custom', {})

        # Prepare metric configurations (merge user config with defaults)
        self.metric_configs = self._prepare_metric_configs()

        # Initialize OpenTelemetry (creates Views + MeterProvider + Histograms)
        self._initialize_otel_and_recorders()

        MetricRegistry._instance = self
        log.info(f"MetricRegistry initialized with {len(self.recorders)} active metrics")

    @classmethod
    def get_instance(cls) -> 'MetricRegistry':
        """Get singleton instance."""
        if cls._instance is None:
            raise RuntimeError("MetricRegistry not initialized")
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None

    def _prepare_metric_configs(self) -> Dict:
        """Merge user config with defaults for all metrics."""
        configs = {}

        # Get system config section
        system_config = self.obs_config.get('system', {})

        for metric_name, default_config in DEFAULT_METRIC_CONFIGS.items():
            # Get user config for this metric from system section (if any)
            user_config = system_config.get(metric_name, {})

            # Start with defaults
            merged = {**default_config}

            # Override buckets if user provided
            if 'values' in user_config:
                merged['buckets'] = user_config['values']

            # Override exclude_labels if user provided
            if 'exclude_labels' in user_config:
                merged['exclude_labels'] = user_config['exclude_labels']

            configs[metric_name] = merged

        return configs

    def _initialize_otel_and_recorders(self):
        """
        Initialize OpenTelemetry SDK and create recorders.

        Process:
        1. Create Views for each metric (defines custom buckets)
        2. Create MeterProvider with Views and Prometheus exporter
        3. Create Histogram instruments (Views apply automatically)
        4. Create HistogramRecorders wrapping the instruments
        """
        # Step 1: Create Views for custom buckets (must happen before MeterProvider)
        views = []
        for metric_name, config in self.metric_configs.items():
            buckets = config.get('buckets', [])
            if not buckets:
                continue  # Skip disabled metrics

            full_name = self._get_full_metric_name(metric_name)

            # Create View for this metric's custom buckets
            view = View(
                instrument_name=full_name,
                aggregation=ExplicitBucketHistogramAggregation(boundaries=buckets)
            )
            views.append(view)
            log.debug(f"Created view for {full_name} with {len(buckets)} buckets")

        # Step 2: Create MeterProvider with Prometheus exporter and Views
        self.prometheus_exporter = PrometheusMetricReader()
        self.meter_provider = MeterProvider(
            metric_readers=[self.prometheus_exporter],
            views=views
        )
        metrics.set_meter_provider(self.meter_provider)

        # Get meter for creating instruments
        meter_name = self.metric_prefix if self.metric_prefix else "solace_ai_connector"
        self.meter = self.meter_provider.get_meter(meter_name)

        log.info(f"OpenTelemetry MeterProvider initialized with {len(views)} views")

        # Step 3 & 4: Create Histograms and Recorders
        self.recorders: Dict[str, MetricRecorder] = {}
        for metric_name, config in self.metric_configs.items():
            buckets = config.get('buckets', [])
            if not buckets:
                continue  # Skip disabled

            # Create histogram instrument (View applies automatically by name match)
            full_name = self._get_full_metric_name(metric_name)
            histogram = self.meter.create_histogram(
                name=full_name,
                unit="s",
                description=f"{metric_name} duration distribution"
            )

            # Create recorder wrapping the histogram
            excluded_labels = config.get('exclude_labels', [])
            recorder = HistogramRecorder(
                histogram=histogram,
                buckets=buckets,
                excluded_labels=excluded_labels
            )

            self.recorders[metric_name] = recorder
            log.debug(f"Created histogram and recorder for {metric_name}")

    def _get_full_metric_name(self, metric_name: str) -> str:
        """Apply prefix to metric name if configured."""
        if self.metric_prefix:
            return f"{self.metric_prefix}.{metric_name}"
        return metric_name

    def _get_custom_excluded_labels(self, name: str) -> list:
        """Get excluded labels for a metric from custom config."""
        return self._custom_configs.get(name, {}).get('exclude_labels', [])

    def _wrap_gauge_callbacks(self, callbacks: List[Callable], excluded_labels: list) -> List[Callable]:
        """Wrap observable gauge callbacks to filter excluded labels."""
        excluded_set = set(excluded_labels)

        def _filter(original_cb):
            def wrapper(options):
                observations = original_cb(options)
                return [
                    Observation(
                        obs.value,
                        {k: v for k, v in (obs.attributes or {}).items() if k not in excluded_set}
                    )
                    for obs in observations
                ]
            return wrapper

        return [_filter(cb) for cb in callbacks]

    def create_counter(self, name: str, description: str = "", unit: str = "1") -> MetricRecorder:
        """
        Create a counter metric.

        Args:
            name: Metric name (without prefix)
            description: Metric description
            unit: Metric unit (default: "1" for dimensionless)

        Returns:
            MetricRecorder - always returns a recorder (NoOpRecorder if disabled)
        """
        if not self.enabled:
            return NoOpRecorder()

        full_name = self._get_full_metric_name(name)
        counter = self.meter.create_counter(name=full_name, unit=unit, description=description)
        excluded = self._get_custom_excluded_labels(name)
        recorder = CounterRecorder(counter=counter, excluded_labels=excluded)
        self.recorders[name] = recorder
        return recorder

    def create_gauge(self, name: str, description: str = "", unit: str = "1") -> MetricRecorder:
        """
        Create push-style gauge metric (UpDownCounter).

        Args:
            name: Metric name (without prefix)
            description: Metric description
            unit: Metric unit (default: "1" for dimensionless)

        Returns:
            MetricRecorder - always returns a recorder (NoOpRecorder if disabled)
        """
        if not self.enabled:
            return NoOpRecorder()

        full_name = self._get_full_metric_name(name)
        up_down_counter = self.meter.create_up_down_counter(name=full_name, unit=unit, description=description)
        excluded = self._get_custom_excluded_labels(name)
        recorder = GaugeRecorder(gauge=up_down_counter, excluded_labels=excluded)
        self.recorders[name] = recorder
        return recorder

    def create_observable_gauge(
        self,
        name: str,
        callbacks: List[Callable],
        description: str = "",
        unit: str = "1"
    ):
        """
        Create callback-based gauge metric.

        OTel calls callbacks at scrape/export time.

        Args:
            name: Metric name (without prefix)
            callbacks: List of callback functions
            description: Metric description
            unit: Metric unit (default: "1" for dimensionless)

        Returns:
            ObservableGauge instrument, or None if disabled
        """
        if not self.enabled:
            return None

        full_name = self._get_full_metric_name(name)
        excluded = self._get_custom_excluded_labels(name)
        wrapped = self._wrap_gauge_callbacks(callbacks, excluded) if excluded else callbacks

        return self.meter.create_observable_gauge(
            name=full_name,
            callbacks=wrapped,
            unit=unit,
            description=description
        )

    def get_recorder(self, metric_name: str) -> Optional[MetricRecorder]:
        """
        Get recorder for a metric.

        Args:
            metric_name: Metric name (e.g., "outbound.request.duration")

        Returns:
            MetricRecorder if metric is enabled, None otherwise
        """
        if not self.enabled:
            return None

        return self.recorders.get(metric_name)

    def get_prometheus_metrics(self) -> bytes:
        """
        Get current metrics in Prometheus format.

        Called by /metrics HTTP endpoint.
        """
        if not self.enabled:
            return b"# Observability disabled\n"

        # Generate Prometheus format output from the registry
        return generate_latest(REGISTRY)

    def add_exporter(self, exporter):
        """
        Add additional metric exporter (OTLP, Datadog, etc.).

        Called by downstream code (solace-agent-mesh-enterprise).

        Args:
            exporter: OpenTelemetry metric exporter instance
        """
        if not self.enabled:
            log.warning("Cannot add exporter - observability is disabled")
            return

        # Wrap exporter in periodic reader
        reader = PeriodicExportingMetricReader(
            exporter=exporter,
            export_interval_millis=60000  # 60 seconds
        )

        # Add to meter provider
        self.meter_provider._sdk_config.metric_readers.append(reader)
        reader._set_meter_provider(self.meter_provider)

        log.info(f"Added metric exporter: {exporter.__class__.__name__}")