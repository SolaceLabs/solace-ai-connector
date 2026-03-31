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

from .config import DEFAULT_DISTRIBUTION_METRICS, DEFAULT_VALUE_METRICS, load_observability_config, validate_config
from .recorders import MetricRecorder, NoOpRecorder, NoOpObservableGauge, HistogramRecorder, CounterRecorder, GaugeRecorder

logger = logging.getLogger(__name__)

class MetricRegistry:
    """
    Singleton registry for metrics collection.
    """

    _instance: Optional['MetricRegistry'] = None

    def __init__(self, config: dict):
        """
        Private constructor - do not call directly.

        Use MetricRegistry.initialize(config) for explicit initialization.
        Use MetricRegistry.get_instance() to retrieve singleton.
        """
        # Load observability config
        self.obs_config = load_observability_config(config)

        # Check if observability is enabled
        self.enabled = self.obs_config.get('enabled', False)
        if not self.enabled:
            logger.info("Observability disabled in configuration")
            self.duration_recorders = {}  # Histogram recorders
            self._value_recorders = {}    # Counter/gauge recorders
            return

        # Validate configuration
        validate_config(self.obs_config)

        # Extract prefix (optional)
        self.metric_prefix = self.obs_config.get('metric_prefix', '')

        # Prepare distribution metric configurations (histograms)
        self.distribution_metric_configs = self._prepare_metric_configs()
        logger.info("Prepared %s distribution metric configs", len(self.distribution_metric_configs))

        # Prepare value metric configurations (counters/gauges)
        self._value_metric_configs = self._prepare_value_metric_configs()
        logger.info("Prepared %s value metric configs", len(self._value_metric_configs))

        # Initialize OpenTelemetry (creates Views + MeterProvider + Histograms + Counters)
        self._initialize_otel_and_recorders()

        logger.info(
            "MetricRegistry initialized with %s duration recorders and %s value recorders",
            len(self.duration_recorders),
            len(self._value_recorders)
        )

    @classmethod
    def initialize(cls, config: dict) -> 'MetricRegistry':
        """
        Initialize MetricRegistry singleton with configuration.

        Call this once at application startup.

        Args:
            config: Full application configuration dict

        Returns:
            MetricRegistry singleton instance

        Raises:
            RuntimeError: If already initialized with different config
        """
        if cls._instance is not None:
            # In tests, allow re-initialization if config is identical (idempotent)
            # Otherwise, require explicit reset first to prevent conflicting configs
            existing_config = cls._instance.obs_config
            new_config = load_observability_config(config)

            if existing_config == new_config:
                # Idempotent initialization - return existing instance
                logger.debug("MetricRegistry already initialized with same config")
                return cls._instance
            else:
                raise RuntimeError(
                    "MetricRegistry already initialized with different config. "
                    "Call MetricRegistry.reset() first."
                )

        cls._instance = cls(config)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'MetricRegistry':
        """
        Get MetricRegistry singleton instance.

        Auto-initializes with observability disabled if not already initialized.
        This ensures instrumented code never fails even when observability not configured.

        Returns:
            MetricRegistry instance (initialized or auto-created no-op instance)

        Note:
            NEVER raises - always returns a valid instance.
            For explicit initialization, use MetricRegistry.initialize(config) instead.
        """
        if cls._instance is None:
            logger.debug("MetricRegistry not initialized - auto-initializing with observability disabled")
            cls._instance = cls({})  # Empty config = disabled observability
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None

    def _prepare_metric_configs(self) -> Dict:
        """Merge user config with defaults for distribution metrics (histograms)."""
        configs = {}

        # Get distribution_metrics config section
        distribution_config = self.obs_config.get('distribution_metrics', {})

        # Process built-in distribution metrics
        for metric_name, default_config in DEFAULT_DISTRIBUTION_METRICS.items():
            # Get user config for this metric (if any)
            user_config = distribution_config.get(metric_name, {})

            # Check if disabled
            if user_config.get('exclude_labels') == ["*"]:
                continue  # Skip disabled metrics

            # Start with defaults
            merged = {**default_config}

            # Override buckets if user provided
            if 'buckets' in user_config:
                merged['buckets'] = user_config['buckets']

            # Override exclude_labels if user provided
            if 'exclude_labels' in user_config:
                merged['exclude_labels'] = user_config['exclude_labels']

            configs[metric_name] = merged

        # Add custom distribution metrics (not in defaults)
        for metric_name, user_config in distribution_config.items():
            if metric_name not in DEFAULT_DISTRIBUTION_METRICS:
                # Custom histogram metric
                if user_config.get('exclude_labels') == ["*"]:
                    continue  # Skip disabled
                configs[metric_name] = user_config

        return configs

    def _prepare_value_metric_configs(self) -> Dict:
        """Merge user config with defaults for value metrics (counters/gauges)."""
        configs = {}

        # Get value_metrics config section
        value_config = self.obs_config.get('value_metrics', {})

        for metric_name, default_config in DEFAULT_VALUE_METRICS.items():
            # Get user config for this metric (if any)
            user_config = value_config.get(metric_name, {})

            # Check if disabled
            if user_config.get('exclude_labels') == ["*"]:
                continue  # Skip disabled metrics

            # Start with defaults
            merged = {**default_config}

            # Override exclude_labels if user provided
            if 'exclude_labels' in user_config:
                merged['exclude_labels'] = user_config['exclude_labels']

            configs[metric_name] = merged

        # Add custom value metrics (not in defaults)
        for metric_name, user_config in value_config.items():
            if metric_name not in DEFAULT_VALUE_METRICS:
                # Custom value metric
                if user_config.get('exclude_labels') == ["*"]:
                    continue  # Skip disabled
                configs[metric_name] = user_config

        return configs

    def _initialize_otel_and_recorders(self):
        """
        Initialize OpenTelemetry SDK and create recorders.

        Process:
        1. Create Views for each metric (defines custom buckets)
        2. Create MeterProvider with Views and Prometheus exporter
        3. Create Histogram instruments (Views apply automatically)
        4. Create HistogramRecorders wrapping the instruments
        5. Create Counter/Gauge recorders
        """
        # Step 1: Create Views for custom buckets (must happen before MeterProvider)
        views = []
        for metric_name, config in self.distribution_metric_configs.items():
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
            logger.debug("Created view for %s with %s buckets", full_name, len(buckets))

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

        logger.info("OpenTelemetry MeterProvider initialized with %s views", len(views))

        # Step 3 & 4: Create Histograms and Recorders (duration/distribution metrics)
        self.duration_recorders: Dict[str, HistogramRecorder] = {}
        for metric_name, config in self.distribution_metric_configs.items():
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

            self.duration_recorders[metric_name] = recorder
            logger.debug("Created histogram and recorder for %s", metric_name)

        # Step 5: Create Counters/Gauges and Recorders for value metrics
        self._value_recorders: Dict[str, MetricRecorder] = {}  # CounterRecorder or GaugeRecorder

        for metric_name, config in self._value_metric_configs.items():
            # Create counter instrument
            full_name = self._get_full_metric_name(metric_name)
            counter = self.meter.create_counter(
                name=full_name,
                unit="1",  # Generic unit for counters
                description=f"{metric_name} counter"
            )

            # Create recorder wrapping the counter
            excluded_labels = config.get('exclude_labels', [])
            recorder = CounterRecorder(
                counter=counter,
                excluded_labels=excluded_labels
            )

            # Store only the recorder (contains the counter internally)
            self._value_recorders[metric_name] = recorder
            logger.debug("Created counter and recorder for %s", metric_name)

    def _get_full_metric_name(self, metric_name: str) -> str:
        """Apply prefix to metric name if configured."""
        if self.metric_prefix:
            return f"{self.metric_prefix}.{metric_name}"
        return metric_name

    def _get_value_metric_excluded_labels(self, name: str) -> list:
        """Get excluded labels for a value metric from config."""
        return self._value_metric_configs.get(name, {}).get('exclude_labels', [])

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
        Create a counter metric dynamically (for custom counters).

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
        excluded = self._get_value_metric_excluded_labels(name)
        recorder = CounterRecorder(counter=counter, excluded_labels=excluded)
        self._value_recorders[name] = recorder  # Store in value recorders, not duration!
        return recorder

    def create_gauge(self, name: str, description: str = "", unit: str = "1") -> MetricRecorder:
        """
        Create push-style gauge metric dynamically (UpDownCounter for custom gauges).

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
        excluded = self._get_value_metric_excluded_labels(name)
        recorder = GaugeRecorder(gauge=up_down_counter, excluded_labels=excluded)
        self._value_recorders[name] = recorder  # Store in value recorders, not duration!
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
            ObservableGauge instrument (or NoOpObservableGauge if disabled)

        Note:
            Consistent with create_counter/create_gauge - always returns an object,
            never None. Uses Null Object pattern for disabled state.
        """
        if not self.enabled:
            return NoOpObservableGauge()

        full_name = self._get_full_metric_name(name)
        excluded = self._get_value_metric_excluded_labels(name)
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
            metric_name: Metric name (e.g., "outbound.request.duration", "gen_ai.tokens.used")

        Returns:
            MetricRecorder if metric is enabled, None otherwise
        """
        if not self.enabled:
            return None

        # Check histogram recorders first
        recorder = self.duration_recorders.get(metric_name)
        if recorder:
            return recorder

        # Check counter recorders
        return self._value_recorders.get(metric_name)

    def record_counter_from_monitor(self, monitor: 'MonitorInstance', value: float):
        """
        Record counter value using Monitor instance.

        Used by built-in Monitor classes (GenAITokenMonitor, GenAICostMonitor).

        Args:
            monitor: MonitorInstance with monitor_type and labels
            value: Value to record (tokens, cost, etc.)

        Example:
            monitor = GenAITokenMonitor.create(model, agent_id, user_id, "input")
            registry.record_counter_from_monitor(monitor, prompt_tokens)
        """
        if not self.enabled:
            return

        recorder = self._value_recorders.get(monitor.monitor_type)
        if recorder:
            recorder.record(value, monitor.labels)

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
            logger.warning("Cannot add exporter - observability is disabled")
            return

        # Wrap exporter in periodic reader
        reader = PeriodicExportingMetricReader(
            exporter=exporter,
            export_interval_millis=60000  # 60 seconds
        )

        # Add to meter provider
        self.meter_provider._sdk_config.metric_readers.append(reader)
        reader._set_meter_provider(self.meter_provider)

        logger.info("Added metric exporter: %s", exporter.__class__.__name__)
