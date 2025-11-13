# SSL Proxy and Certificate Configuration

This document describes how to configure SSL certificate validation and proxy settings for components that make external API calls, such as the LiteLLM components.

## Environment Variables

| Environment Variable | Required | Description |
|---|---:|---|
| `DISABLE_SSL_VERIFY` | No | When set to a true value disables SSL certificate validation for outgoing requests. **Insecure — only for development or troubleshooting.** |
| `SSL_CERT_FILE` | No | Path to a custom CA certificate file or bundle used by some Python/OpenSSL-based clients. Useful when connecting through MITM proxies or to services with custom/self-signed certs. |
| `REQUESTS_CA_BUNDLE` | No | Path to a custom CA certificate file or bundle used by `requests` and a number of other libraries. Use alongside `SSL_CERT_FILE` to maximize compatibility. |
| `HTTP_PROXY` | No | HTTP proxy URL (plain HTTP). Example: `http://127.0.0.1:8080`. |
| `HTTPS_PROXY` | No | HTTPS proxy URL (used for `CONNECT` tunneling). Example: `http://127.0.0.1:8080`. |
| `NO_PROXY` | No | Comma-separated list of hosts that should bypass the proxy (e.g., `localhost,127.0.0.1`). |


## Behavior & precedence

When the application makes outbound HTTPS requests, the following precedence is used:

1. If `DISABLE_SSL_VERIFY` is true → **TLS verification is disabled** (applies globally).
2. Else if REQUESTS_CA_BUNDLE or SSL_CERT_FILE is set → the provided file is used as the trusted CA bundle for TLS validation.
    **Recommendation**: set both REQUESTS_CA_BUNDLE and SSL_CERT_FILE to the same path to maximize compatibility, because different components/libraries may read one or the other.
3. Else → the system's default/trusted CA bundle is used.

### 1. Disable SSL Verification

Set `DISABLE_SSL_VERIFY=true` to bypass certificate validation entirely. This is insecure and should only be used in development environments.
Note: setting DISABLE_SSL_VERIFY=true and SSL_CERT_FILE=<path-to-certificate> - will throw an error, since these are incompatible settings.


```bash
# Example: Disable SSL verification (less secure)
export DISABLE_SSL_VERIFY=true
# run the app
```

### 2. Enable Https Proxy 

```bash
# Example: Enabpe https proxy + custom certificate
export HTTPS_PROXY="http://127.0.0.1:8181"
export REQUESTS_CA_BUNDLE="/path/to/certificate.pem"
export SSL_CERT_FILE="$REQUESTS_CA_BUNDLE"
# run the app
```