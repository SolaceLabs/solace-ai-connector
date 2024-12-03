# LangChainEmbeddings

Provide access to all the LangChain Text Embeddings components via configuration

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: langchain_embeddings
component_config:
  langchain_module: <string>
  langchain_class: <string>
  langchain_component_config: <object>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| langchain_module | True |  | The chat model module - e.g. 'langchain_openai.chat_models' |
| langchain_class | True |  | The chat model class to use - e.g. ChatOpenAI |
| langchain_component_config | True |  | Model specific configuration for the chat model. See documentation for valid parameter names. |


## Component Input Schema

```
{
  items: [
,
    ...
  ],
  type:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| items | True | A single element or a list of elements to embed |
| type | False | The type of embedding to use: 'document', 'query', or 'image' - default is 'document' |


## Component Output Schema

```
{
  embedding: [
    <float>,
    ...
  ]
}
```
| Field | Required | Description |
| --- | --- | --- |
| embedding | True | A list of floating point numbers representing the embedding. Its length is the size of vector that the embedding model produces |
