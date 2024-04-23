# LangChainChatModel

Provide access to all the LangChain chat models via configuration

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: langchain_chat_model
component_config:
  langchain_module: <string>
  langchain_class: <string>
  langchain_component_config: <string>
  llm_response_format: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| langchain_module | True |  | The chat model module - e.g. 'langchain_openai.chat_models' |
| langchain_class | True |  | The chat model class to use - e.g. ChatOpenAI |
| langchain_component_config | True |  | Model specific configuration for the chat model. See documentation for valid parameter names. |
| llm_response_format | False |  | The response format for this LLM request. This can be 'json', 'yaml', or 'text'. If set to 'json' or 'yaml', the response will be parsed by the appropriate parser and the fields will be available in the response object. If set to 'text', the response will be returned as a string. |


## Component Input Schema

```
{
  messages: [
    {
      role:       <string>,
      content:       <string>
    },
    ...
  ]
}
```
| Field | Required | Description |
| --- | --- | --- |
| messages | True |  |
| messages[].role | False | The role of the LLM message (user, assistant, system) |
| messages[].content | True | The content of the LLM message |


## Component Output Schema

```
{
  result:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| result | True |  |
