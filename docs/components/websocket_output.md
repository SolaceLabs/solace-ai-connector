# WebsocketOutput

Send messages to a websocket connection.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: websocket_output
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


## Component Input Schema

```
{
  payload:   {
    <freeform-object>
  },
  socket_id:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| payload | True | The payload to be sent via WebSocket |
| socket_id | False | Identifier for the WebSocket connection |
