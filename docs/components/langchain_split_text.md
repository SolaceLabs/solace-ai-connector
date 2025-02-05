# LangChainTextSplitter

Split a long text into smaller parts using the LangChain text splitter module

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: langchain_split_text
component_config:
  langchain_module: <string>
  langchain_class: <string>
  langchain_component_config: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| langchain_module | True |  | The text split module - e.g. 'langchain_text_splitters' |
| langchain_class | True |  | The text split class to use - e.g. TokenTextSplitter |
| langchain_component_config | True |  | Model specific configuration for the text splitting. See documentation for valid parameter names.https://python.langchain.com/docs/how_to/split_by_token/#nltk |


## Component Input Schema

```
{
  text:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| text | True |  |


## Component Output Schema

```
[
  <string>,
  ...
]
```
