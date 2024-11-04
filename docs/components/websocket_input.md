# WebsocketInput

Listen for incoming messages on a websocket connection.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: websocket_input
component_config:
  listen_port: <int>
  serve_html: <bool>
  html_path: <string>
  payload_encoding: <string>
  payload_format: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| listen_port | False |  | Port to listen on (optional) |
| serve_html | False | False | Serve the example HTML file |
| html_path | False | examples/websocket/websocket_example_app.html | Path to the HTML file to serve |
| payload_encoding | False | none | Encoding for the payload (utf-8, base64, gzip, none) |
| payload_format | False | json | Format for the payload (json, yaml, text) |



## Component Output Schema

```
{
  payload:   {
    <freeform-object>
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| payload | True | The decoded JSON payload received from the WebSocket |
