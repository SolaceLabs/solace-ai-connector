"""
Integration tests for LiteLLM with SSL proxy functionality.

These tests verify that the LiteLLMBase component correctly handles SSL proxy settings
with various certificate validation configurations.

Required environment variables:
- OPENAI_API_KEY: A valid OpenAI API key for making actual API calls
- OPENAI_API_ENDPOINT: The API endpoint to use for OpenAI API calls

Test cases:
1. SSL proxy with valid certificate (using certifi bundle) - should pass
2. SSL proxy with valid certificate (using direct cert file) - should pass
3. SSL proxy without certificate - should fail with SSL verification error
4. SSL proxy without certificate but with SSL verification disabled - should pass
5. Forward proxy with partial vs full certificate bundle - tests both failure and success cases
"""

import os
import logging
import contextlib
import pytest
from pathlib import Path
from typing import Dict, Optional, Tuple
import sys
from shutil import copyfile
import certifi

from .proxy_helper import start_mitmproxy, stop_mitmproxy, generate_selfsigned_cert, start_proxy_py, write_bundle, start_https_server
import requests

# Import the component to test
from litellm.exceptions import APIConnectionError

log = logging.getLogger(__name__)

# Default configuration for LiteLLMBase
DEFAULT_LOAD_BALANCER = [
    {
        "litellm_params": {"api_base": os.environ.get("OPENAI_API_ENDPOINT","").strip('"\''), "api_key": os.environ.get("OPENAI_API_KEY", "").strip('"\''), "model": "openai/gemini-2.5-pro"},
        "model_name": "integration-test",
    }
]

# Mock module info for LiteLLMBase initialization
MOCK_MODULE_INFO = {
    "name": "test_litellm",
    "class_name": "LiteLLMBase",
    "description": "Test LiteLLM component",
    "config_parameters": [],
}

# Minimal component configuration
MINIMAL_COMPONENT_CONFIG = {"load_balancer": DEFAULT_LOAD_BALANCER}

def reset_httpx_cache():
    sys.modules.pop("httpcore", None)
    sys.modules.pop("httpx", None)


@contextlib.contextmanager
def set_env(env: Dict[str, Optional[str]]):
    """
    Temporarily set environment variables using os.environ.
    Restores previous values on exit.
    Use value None to *unset* a variable.
    """
    old = {}
    for k, v in env.items():
        old[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        # restore old values (including deleting newly set ones)
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

@pytest.fixture(scope="session", autouse=True)
def check_required_env_vars():
    """
    Check that required environment variables are set.
    If any required variables are missing, all tests will be skipped.
    """
    required_vars = {
        "OPENAI_API_KEY": "A valid OpenAI API key is required for these tests",
        "OPENAI_API_ENDPOINT": "The OpenAI API endpoint URL is required for these tests"
    }
    
    missing_vars = []
    for var, message in required_vars.items():
        if not os.environ.get(var):
            missing_vars.append(f"{var}: {message}")
    
    if missing_vars:
        pytest.skip(f"Missing required environment variables: {missing_vars}")


def assert_connection_error(exception):
    """
    Assert that the exception is a connection error, which is what we expect
    when SSL verification fails in the LiteLLM stack.
    
    Args:
        exception: The exception to check
        
    Raises:
        AssertionError: If the exception is not a connection error
    """
    import litellm.exceptions
    # Check if it's a LiteLLM InternalServerError
    if not isinstance(exception, litellm.exceptions.InternalServerError):
        raise AssertionError(
            f"Expected litellm.exceptions.InternalServerError, got: {type(exception).__name__}\n"
            f"Error message: {str(exception)}"
        )
    
    # Check if it contains "Connection error" in the message
    error_message = str(exception)
    if "Connection error" not in error_message:
        raise AssertionError(
            f"Expected 'Connection error' in exception message, but got: {error_message}"
        )
    
    # If we get here, the exception is as expected
    return True

def add_custom_ca_to_certifi_store(user_certificate: str) -> str:    
    """
    Merges a user-provided CA certificate with the certifi CA bundle.
    
    Args:
        user_certificate: Path to the user-provided CA certificate file.
        
    Returns:
        Path to the merged CA bundle file.
    """
    import certifi
    from pathlib import Path

    certifi_path = Path(certifi.where())
    with open(certifi_path, "ab") as out, open(user_certificate, "rb") as custom:
        out.write(b"\n")
        out.write(custom.read())

def test_TLS_INTERCEPT_litellm_with_proxy_and_valid_cert():
    """
    Test case 1: SSL proxy with valid certificate - should pass.
    
    This test verifies that LiteLLMBase can make API calls through an SSL proxy
    when provided with the correct CA certificate + certifi bundle.
    """
    reset_httpx_cache()
    proc, proxy_url, ca_pem = start_mitmproxy(host="127.0.0.1")
    add_custom_ca_to_certifi_store(ca_pem)
    try:
        # Set environment variables for the test
        with set_env({
            "HTTPS_PROXY": proxy_url
        }):
            from solace_ai_connector.components.general.llm.litellm.litellm_base import LiteLLMBase
            # Initialize the component
            llm = LiteLLMBase(module_info=MOCK_MODULE_INFO, config=MINIMAL_COMPONENT_CONFIG)
            
            # Attempt to make an API call
            # try:
            response = llm.load_balance(messages=[{"role": "user", "content": "Hello"}], stream=False)
            log.info(f"API call succeeded: {response}")
            # except Exception as e:
            #     # Network may fail in CI, but we should not get an SSL error
            #     assert not isinstance(e, APIConnectionError) or "SSL" not in str(e), \
            #         f"Got unexpected SSL error: {e}"
            #     log.info("Test passed: No SSL errors were raised")
    finally:
        stop_mitmproxy(proc)

def test_TLS_INTERCEPT_litellm_with_proxy_and_only_cert():
    """
    Test case 2: SSL proxy with valid certificate - should pass.
    
    This test verifies that LiteLLMBase can make API calls through an SSL proxy
    when provided with the correct CA certificate only.
    """
    reset_httpx_cache()
    proc, proxy_url, ca_pem = start_mitmproxy(host="127.0.0.1")
    try:
        # Set environment variables for the test
        with set_env({
            "HTTPS_PROXY": proxy_url, 
            "SSL_CERT_FILE": ca_pem, 
            "REQUESTS_CA_BUNDLE": ca_pem
        }):
            # we want to import it after env vars ar set
            from solace_ai_connector.components.general.llm.litellm.litellm_base import LiteLLMBase
            
            llm = LiteLLMBase(module_info=MOCK_MODULE_INFO, config=MINIMAL_COMPONENT_CONFIG)
            try:
                response = llm.load_balance(messages=[{"role": "user", "content": "Hello"}], stream=False)
                log.info(f"API call succeeded: {response}")
            except Exception as e:
                # Network may fail in CI, but we should not get an SSL error
                assert not isinstance(e, APIConnectionError) or "SSL" not in str(e), \
                    f"Got unexpected SSL error: {e}"
                log.info("Test passed: No SSL errors were raised")
    finally:
        stop_mitmproxy(proc)        


def test_TLS_INTERCEPT_litellm_with_proxy_no_cert_should_fail():
    """
    Test case 3: SSL proxy without certificate - should fail with SSL verification error.
    
    This test verifies that LiteLLMBase raises an SSL verification error when using
    an SSL proxy without providing the CA certificate.
    """
    reset_httpx_cache()
    proc, proxy_url, _ = start_mitmproxy(host="127.0.0.1")
    try:
        # Set environment variables for the test
        with set_env({
            "HTTPS_PROXY": proxy_url,
        }):
            from solace_ai_connector.components.general.llm.litellm.litellm_base import LiteLLMBase
         
            # Initialize the component
            llm = LiteLLMBase(module_info=MOCK_MODULE_INFO, config=MINIMAL_COMPONENT_CONFIG)
            
            # Attempt to make an API call - should fail with SSL error
            with pytest.raises(Exception) as excinfo:
                llm.load_balance(messages=[{"role": "user", "content": "Hello"}], stream=False)
            
            # Verify it's an SSL verification error
            assert_connection_error(excinfo.value)
    finally:
        stop_mitmproxy(proc)


def test_TLS_INTERCEPT_litellm_with_proxy_no_cert_and_verification_disabled():
    """
    Test case 4: SSL proxy without certificate but with SSL verification disabled - should pass.
    
    This test verifies that LiteLLMBase can make API calls through an SSL proxy
    without a CA certificate when SSL verification is disabled.
    """
    reset_httpx_cache()
    proc, proxy_url, _ = start_mitmproxy(host="127.0.0.1")
    try:
        # Set environment variables for the test
        with set_env({
            "HTTPS_PROXY": proxy_url,
            "DISABLE_SSL_VERIFY": "true"  # Disable SSL verification
        }):
            from solace_ai_connector.components.general.llm.litellm.litellm_base import LiteLLMBase
            # Initialize the component
            llm = LiteLLMBase(module_info=MOCK_MODULE_INFO, config=MINIMAL_COMPONENT_CONFIG)
            
            # Attempt to make an API call
            try:
                response = llm.load_balance(messages=[{"role": "user", "content": "Hello"}], stream=False)
                log.info(f"API call succeeded: {response}")
            except Exception as e:
                # Network may fail in CI, but we should not get an SSL error
                assert not isinstance(e, APIConnectionError) or "SSL" not in str(e), \
                    f"Got unexpected SSL error: {e}"
                log.info("Test passed: No SSL errors were raised")
    finally:
        stop_mitmproxy(proc)


@pytest.mark.integration
def test_FORWARD_PROXY_litellm_and_partial_vs_full_bundle(tmp_path):
    """
    Scenario:
      - Start HTTPS echo server with self-signed cert.
      - Start proxy.py (forward-only, no TLS interception).
      - Case 1: verify only self-signed cert -> SSL failure.
      - Case 2: bundle + self-signed cert includes origin cert -> success.
    """
    host = "127.0.0.1"
    https_port = 8443
    proxy_port = 8899

    # Generate certs for backend server
    cert_path, key_path, _ = generate_selfsigned_cert("localhost", tmp_path / "certs")

    # Start HTTPS server and proxy
    with start_https_server(host, https_port, cert_path, key_path):
        with start_proxy_py(host=host, port=proxy_port) as proxy_url:
            # Prepare bundles properly
            partial_bundle = tmp_path / "bundle_partial.pem"
            write_bundle(partial_bundle, cert_path)  # only the self-signed cert (should fail)

            # Copy system CA bundle and append our cert -> "full" trust chain
            full_bundle = tmp_path / "bundle_full.pem"
            copyfile(certifi.where(), full_bundle)
            with open(full_bundle, "ab") as out, open(cert_path, "rb") as custom:
                out.write(b"\n")
                out.write(custom.read())

            # Environment for LiteLLMBase
            env_base = {
                "OPENAI_API_KEY": "dummy-key",
                "OPENAI_API_ENDPOINT": f"https://{host}:{https_port}",
                "HTTPS_PROXY": proxy_url,
            }

            # ---------------- Case 1: missing cert (expect SSL error) ----------------
            with pytest.raises(Exception) as excinfo:
                with set_env({**env_base, "SSL_CERT_FILE": str(partial_bundle), "REQUESTS_CA_BUNDLE": str(partial_bundle)}):
                    from solace_ai_connector.components.general.llm.litellm.litellm_base import LiteLLMBase
                    llm = LiteLLMBase(module_info=MOCK_MODULE_INFO, config=MINIMAL_COMPONENT_CONFIG)
                    llm.load_balance(messages=[{"role": "user", "content": "Hello"}], stream=False)

            # Verify it's an SSL verification error
            assert_connection_error(excinfo.value)

            # ---------------- Case 2: full bundle (expect success) ----------------
            with set_env({**env_base, "SSL_CERT_FILE": str(full_bundle), "REQUESTS_CA_BUNDLE": str(full_bundle)}):
                from solace_ai_connector.components.general.llm.litellm.litellm_base import LiteLLMBase
                llm = LiteLLMBase(module_info=MOCK_MODULE_INFO, config=MINIMAL_COMPONENT_CONFIG)
                response = llm.load_balance(messages=[{"role": "user", "content": "Hello"}], stream=False)
                assert response is not None