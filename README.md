> [!WARNING]
> ## The Solace AI Connector is now deprecated
>
> 👋 Thank you to everyone who has built with the Solace AI Connector! This library is now **deprecated** — it's no longer under active development and won't receive new features, bug fixes or security updates.
>
> 🚀 **Check out the new version of Solace Agent Mesh** → https://docs.solace.com/Agent-Mesh/agent-mesh.htm
>
> 🖥️ A free edition of the Solace Agent Mesh desktop app is available: https://solace.com/products/agent-mesh/download/
>
> This repository will be archived (read-only); existing PyPI releases keep working.

# Solace AI Connector

## Overview

This project provides a standalone, Python-based application to allow Solace event brokers to connect to
a wide range of AI models and services. The application is designed to be easily extensible to
support new AI models and services.

## Documentation

Please see the [documentation](docs/index.md) for more information.

## Getting started quickly

Please see the [getting started guide](docs/getting_started.md) for instructions on how to get started quickly.

## Observability

solace-ai-connector provides OpenTelemetry-based metrics for monitoring duration across:
- Remote service calls (Solace broker, S3, OAuth, etc.)
- LLM inference (duration and time-to-first-token)
- Database operations
- Gateway request handling
- Internal operations

Enable in your configuration:

```yaml
management_server:
  observability:
    enabled: true
    path: /metrics
```

See [Observability Documentation](docs/observability.md) for details.

## Support

This is not an officially supported Solace product.

For more information try these resources:

- Ask the [Solace Community](https://solace.community)
- The Solace Developer Portal website at: https://solace.dev

## Contributing

Contributions are encouraged! Please read [CONTRIBUTING](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

See the [LICENSE](LICENSE) file for details.

