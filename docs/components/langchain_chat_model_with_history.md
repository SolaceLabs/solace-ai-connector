# LangChainChatModelWithHistory

A chat model based on LangChain that includes keeping per-session history of the conversation. Note that this component will only take the first system message and the first human message in the messages array.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: langchain_chat_model_with_history
component_config:
  langchain_module: <string>
  langchain_class: <string>
  langchain_component_config: <string>
  llm_mode: <string>
  stream_to_flow: <string>
  stream_batch_size: <string>
  llm_response_format: <string>
  history_max_turns: <string>
  history_max_message_size: <string>
  history_max_tokens: <string>
  history_max_time: <string>
  history_module: <string>
  history_class: <string>
  history_config: <object>
  set_response_uuid_in_user_properties: <boolean>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| langchain_module | True |  | The chat model module - e.g. 'langchain_openai.chat_models' |
| langchain_class | True |  | The chat model class to use - e.g. ChatOpenAI |
| langchain_component_config | True |  | Model specific configuration for the chat model. See documentation for valid parameter names. |
| llm_mode | False |  | The mode for streaming results: 'none' or 'stream'. 'stream' will just stream the results to the named flow. 'none' will wait for the full response. |
| stream_to_flow | False |  | Name the flow to stream the output to - this must be configured for llm_mode='stream'. |
| stream_batch_size | False | 15 | The minimum number of words in a single streaming result. Default: 15. |
| llm_response_format | False |  | The response format for this LLM request. This can be 'json', 'yaml', or 'text'. If set to 'json' or 'yaml', the response will be parsed by the appropriate parser and the fields will be available in the response object. If set to 'text', the response will be returned as a string. |
| history_max_turns | False | 20 | The maximum number of turns to keep in the history. If not set, the history will be limited to 20 turns. |
| history_max_message_size | False | 1000 | The maximum amount of characters to keep in a single message in the history.  |
| history_max_tokens | False | 8000 | The maximum number of tokens to keep in the history. If not set, the history will be limited to 8000 tokens. |
| history_max_time | False | None | The maximum time (in seconds) to keep messages in the history. If not set, messages will not expire based on time. |
| history_module | False | langchain_community.chat_message_histories | The module that contains the history class. Default: 'langchain_community.chat_message_histories' |
| history_class | False | ChatMessageHistory | The class to use for the history. Default: 'ChatMessageHistory' |
| history_config | False |  | The configuration for the history class. |
| set_response_uuid_in_user_properties | False | False | Whether to set the response_uuid in the user_properties of the input_message. This will allow other components to correlate streaming chunks with the full response. |


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
  session_id:   <string>,
  clear_history:   <boolean>
}
```
| Field | Required | Description |
| --- | --- | --- |
| messages | True |  |
| messages[].role | False | The role of the LLM message (user, assistant, system) |
| messages[].content | True | The content of the LLM message |
| session_id | True | The session ID for the conversation. |
| clear_history | False | Whether to clear the history for the session. |


## Component Output Schema

```
{
  result:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| result | True |  |
