# WebSearchGoogle

Perform a search query on Google.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: websearch_google
component_config:
  api_key: <string>
  search_engine_id: <string>
  count: <string>
  detail: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| api_key | True |  | Google API Key. |
| search_engine_id | False | 1 | The custom search engine id. |
| count | False | 10 | Max Number of search results to return. |
| detail | False | False | Return the detail. |


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
