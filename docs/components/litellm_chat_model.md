# LiteLLMChatModel

LiteLLM chat component

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: litellm_chat_model
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

## Using AWS Bedrock with LiteLLMChatModel

The `LiteLLMChatModel` component can leverage AWS Bedrock as a provider for LLM models through its `load_balancer` configuration. This allows you to use models hosted on Bedrock, such as those from Anthropic (Claude), AI21 Labs, Cohere, Meta, Stability AI, and Amazon itself.

### Bedrock Configuration in `load_balancer`

When configuring a Bedrock model within the `load_balancer` list, pay attention to the following in the `litellm_params` for that model entry:

*   **`model` (Model Identifier)**: This is crucial and must follow a specific format for Bedrock:
    *   Format: `"bedrock/<provider>.<model_id>"`
    *   Example: `"bedrock/anthropic.claude-3-sonnet-20240229-v1:0"` for Claude 3 Sonnet.
    *   Example: `"bedrock/amazon.titan-text-express-v1"` for Amazon Titan Text Express.
    *   You can find the exact model IDs in the AWS Bedrock console or AWS documentation.

*   **AWS Credentials & Region**:
    *   **`api_key`**: This parameter is **NOT** used for Bedrock models. If provided, a warning will be logged, but it will be ignored.
    *   **Authentication Methods**:
        1.  **Environment Variables (Recommended)**: LiteLLM (via Boto3) will automatically attempt to use AWS credentials configured in your environment. This typically involves setting:
            *   `AWS_ACCESS_KEY_ID`
            *   `AWS_SECRET_ACCESS_KEY`
            *   `AWS_SESSION_TOKEN` (if using temporary credentials)
            *   `AWS_REGION_NAME` or `AWS_DEFAULT_REGION` (e.g., `us-east-1`)
        2.  **Directly in `litellm_params`**: You can provide AWS credentials directly within the `litellm_params` dictionary for a specific model. This is generally less recommended for production environments.
            *   `aws_access_key_id`: Your AWS Access Key ID.
            *   `aws_secret_access_key`: Your AWS Secret Access Key.
            *   `aws_session_token`: (Optional) Your AWS Session Token if using temporary credentials.
            *   `aws_region_name`: The AWS region where the Bedrock model is hosted (e.g., `"us-east-1"`). This is generally required. If you provide `aws_access_key_id` and `aws_secret_access_key` in `litellm_params`, it's strongly recommended to also provide `aws_region_name` here.
    *   **`aws_region_name`**: Whether using environment variables or direct parameters, specifying the AWS region is important.

*   **Other Bedrock-Specific Parameters**:
    *   Some Bedrock models might support or require additional parameters. These can be included in the `litellm_params` dictionary. For example, if using provisioned throughput, you might need to pass a specific `model_id` that refers to your provisioned model.
    *   `aws_bedrock_runtime_endpoint`: If you are using a custom Bedrock runtime endpoint (e.g., VPC endpoint), you can specify it here.

### Boto3 Installation Requirement

To interact with AWS Bedrock, LiteLLM relies on the AWS SDK for Python, `boto3`. Ensure that `boto3` is installed in the Python environment where the Solace AI Connector is running:
```bash
pip install boto3
```

### Example Configuration

Below is an excerpt from an example YAML configuration ([`examples/llm/litellm_bedrock_chat.yaml`](../../examples/llm/litellm_bedrock_chat.yaml)) showing how to set up a Bedrock model:

```yaml
# ... (other parts of the config) ...
      - component_name: bedrock_llm_request
        component_module: litellm_chat_model
        component_config:
          llm_mode: none
          timeout: 180
          load_balancer:
            - model_name: "claude3-sonnet-bedrock" # User-defined alias
              litellm_params:
                model: "bedrock/anthropic.claude-3-sonnet-20240229-v1:0"
                # Option 1: Provide credentials directly (using env vars for values)
                aws_access_key_id: "${AWS_ACCESS_KEY_ID_BEDROCK}" 
                aws_secret_access_key: "${AWS_SECRET_ACCESS_KEY_BEDROCK}"
                aws_region_name: "${AWS_REGION_NAME:-us-east-1}" # Default if env var not set
                
                # Option 2: Rely on standard AWS environment variables (remove above aws_* keys)
                # Ensure AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME are set.

                temperature: 0.5
                max_tokens: 1024
# ... (rest of the config) ...
```
Refer to the full [`examples/llm/litellm_bedrock_chat.yaml`](../../examples/llm/litellm_bedrock_chat.yaml) for a complete, runnable example.

## Component Input Schema

```
{
  messages: [
    {
      role:       <string>,
      content:       <string>
    },
    ...
  ],
  stream:   <boolean>,
  clear_history_but_keep_depth:   <integer>
}
```
| Field | Required | Description |
| --- | --- | --- |
| messages | True |  |
| messages[].role | True |  |
| messages[].content | True |  |
| stream | False | Whether to stream the response - overwrites llm_mode |
| clear_history_but_keep_depth | False | Clear history but keep the last N messages. If 0, clear all history. If not set, do not clear history. |


## Component Output Schema

```
{
  content:   <string>,
  chunk:   <string>,
  response_uuid:   <string>,
  first_chunk:   <boolean>,
  last_chunk:   <boolean>,
  streaming:   <boolean>
}
```
| Field | Required | Description |
| --- | --- | --- |
| content | True | The generated response from the model |
| chunk | False | The current chunk of the response |
| response_uuid | False | The UUID of the response |
| first_chunk | False | Whether this is the first chunk of the response |
| last_chunk | False | Whether this is the last chunk of the response |
| streaming | False | Whether this is a streaming response |
