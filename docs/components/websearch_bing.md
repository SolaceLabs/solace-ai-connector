# WebSearchBing

Perform a search query on Bing.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: websearch_bing
component_config:
  api_key: <string>
  count: <string>
  safesearch: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| api_key | True |  | Bing API Key. |
| count | False | 10 | Max number of search results to return. |
| safesearch | False | Moderate | Safe search setting: Off, Moderate, or Strict. |


## Component Input Schema

```
<string>
```


## Component Output Schema

```
[
  {
    title:     <string>,
    snippet:     <string>,
    url:     <string>
  },
  ...
]
```
| Field | Required | Description |
| --- | --- | --- |
| [].title | False |  |
| [].snippet | False |  |
| [].url | False |  |
