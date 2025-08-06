# LiteLLMEmbeddings

Embed text using a LiteLLM model

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: litellm_embeddings
component_config:
  load_balancer: <string>
  embedding_params: <string>
  temperature: <string>
  set_response_uuid_in_user_properties: <boolean>
  timeout: <string>
  suppress_debug_info: <boolean>
  aiohttp_trust_env: <boolean>
  ssl_verify: <string>
  retry_policy: <string>
  allowed_fails_policy: <string>
  stream_to_flow: <string>
  stream_to_next_component: <string>
  llm_mode: <string>
  stream_batch_size: <string>
  history_max_turns: <string>
  history_max_time: <string>
  stream_to_flow: <string>
  stream_to_next_component: <string>
  llm_mode: <string>
  stream_batch_size: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| load_balancer | False |  | A list of models to configure for the LiteLLM load balancer. Each item in the list is a dictionary defining a model and must contain:
  - 'model_name': An alias for this model configuration (e.g., 'my-openai-model', 'my-bedrock-claude').
  - 'litellm_params': A dictionary of parameters passed directly to LiteLLM for this model.
    Common 'litellm_params' include:
      - 'model': The actual model identifier (e.g., 'gpt-4o', 'anthropic.claude-3-sonnet-20240229-v1:0').
      - 'api_key': Required for many providers like OpenAI, Anthropic direct (but NOT for AWS Bedrock).
      - 'api_base': The base URL for the API endpoint, if not default.
      - 'temperature', 'max_tokens', etc., as supported by LiteLLM and the provider.
    For AWS Bedrock models:
      - 'model' format: 'bedrock/<provider>.<model_id>' (e.g., 'bedrock/anthropic.claude-3-sonnet-20240229-v1:0').
      - 'api_key' is NOT used.
      - AWS credentials (aws_access_key_id, aws_secret_access_key, aws_session_token (optional), aws_region_name) can be provided directly in 'litellm_params'. If not, LiteLLM (via Boto3) attempts to use standard AWS environment variables (e.g., AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION/AWS_REGION_NAME).
      - 'aws_region_name' is generally required for Bedrock, either in 'litellm_params' or as an environment variable.
      - Other Bedrock-specific params like 'model_id' (for provisioned throughput) or 'aws_bedrock_runtime_endpoint' can be included. |
| embedding_params | False |  | LiteLLM model parameters. The model, api_key and base_url are mandatory.find more models at https://docs.litellm.ai/docs/providersfind more parameters at https://docs.litellm.ai/docs/completion/input |
| temperature | False | 0.7 | Sampling temperature to use |
| set_response_uuid_in_user_properties | False | False | Whether to set the response_uuid in the user_properties of the input_message. This will allow other components to correlate streaming chunks with the full response. |
| timeout | False | 60 | Request timeout in seconds |
| suppress_debug_info | False | False | Whether to suppress debug info in LiteLLM |
| aiohttp_trust_env | False | True | Whether to trust environment variables for aiohttp |
| ssl_verify | False | False | Whether to verify SSL certificates. Can be a boolean or a path to a PEM file. |
| retry_policy | False |  | Retry policy for the load balancer. Find more at https://docs.litellm.ai/docs/routing#cooldowns |
| allowed_fails_policy | False |  | Allowed fails policy for the load balancer. Find more at https://docs.litellm.ai/docs/routing#cooldowns |
| stream_to_flow | False |  | Name the flow to stream the output to - this must be configured for llm_mode='stream'. This is mutually exclusive with stream_to_next_component. |
| stream_to_next_component | False | False | Whether to stream the output to the next component in the flow. This is mutually exclusive with stream_to_flow. |
| llm_mode | False | none | The mode for streaming results: 'none' or 'stream'. 'stream' will just stream the results to the named flow. 'none' will wait for the full response. |
| stream_batch_size | False | 15 | The minimum number of words in a single streaming result. Default: 15. |
| history_max_turns | False | 10 | Maximum number of conversation turns to keep in history |
| history_max_time | False | 3600 | Maximum time to keep conversation history (in seconds) |
| stream_to_flow | False |  | Name the flow to stream the output to - this must be configured for llm_mode='stream'. This is mutually exclusive with stream_to_next_component. |
| stream_to_next_component | False | False | Whether to stream the output to the next component in the flow. This is mutually exclusive with stream_to_flow. |
| llm_mode | False | none | The mode for streaming results: 'none' or 'stream'. 'stream' will just stream the results to the named flow. 'none' will wait for the full response. |
| stream_batch_size | False | 15 | The minimum number of words in a single streaming result. Default: 15. |


## Component Input Schema

```
{
  items: [
,
    ...
  ]
}
```
| Field | Required | Description |
| --- | --- | --- |
| items | True | A single element or a list of elements to embed |


## Component Output Schema

```
{
  embeddings: [
    <float>,
    ...
  ]
}
```
| Field | Required | Description |
| --- | --- | --- |
| embeddings | True | A list of floating point numbers representing the embeddings. Its length is the size of vector that the embedding model produces |
