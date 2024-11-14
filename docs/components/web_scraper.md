# WebScraper

Scrape javascript based websites.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: web_scraper
component_config:
  timeout: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| timeout | False | 30000 | The timeout for the browser in milliseconds. |


## Component Input Schema

```
{
  url:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| url | False | The URL of the website to scrape. |


## Component Output Schema

```
{
  title:   <string>,
  content:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| title | False | The title of the website. |
| content | False | The content of the website. |
