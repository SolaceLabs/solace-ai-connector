# OpenAIChatModelWithHistory

OpenAI chat model component with conversation history

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: openai_chat_model_with_history
component_config:
  api_key: <string>
  model: <string>
  temperature: <string>
  base_url: <string>
  stream_to_flow: <string>
  stream_to_next_component: <string>
  llm_mode: <string>
  stream_batch_size: <string>
  set_response_uuid_in_user_properties: <boolean>
  history_max_turns: <string>
  history_max_time: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| api_key | True |  | OpenAI API key |
| model | True |  | OpenAI model to use (e.g., 'gpt-3.5-turbo') |
| temperature | False | 0.7 | Sampling temperature to use |
| base_url | False | None | Base URL for OpenAI API |
| stream_to_flow | False |  | Name the flow to stream the output to - this must be configured for llm_mode='stream'. This is mutually exclusive with stream_to_next_component. |
| stream_to_next_component | False | False | Whether to stream the output to the next component in the flow. This is mutually exclusive with stream_to_flow. |
| llm_mode | False | none | The mode for streaming results: 'none' or 'stream'. 'stream' will just stream the results to the named flow. 'none' will wait for the full response. |
| stream_batch_size | False | 15 | The minimum number of words in a single streaming result. Default: 15. |
| set_response_uuid_in_user_properties | False | False | Whether to set the response_uuid in the user_properties of the input_message. This will allow other components to correlate streaming chunks with the full response. |
| history_max_turns | False | 10 | Maximum number of conversation turns to keep in history |
| history_max_time | False | 3600 | Maximum time to keep conversation history (in seconds) |


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
| stream | False | Whether to stream the response. It is is not provided, it will default to the value of llm_mode. |
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
