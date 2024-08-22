# BrokerRequestResponse

Connect to a messaging broker, send request messages, and receive responses. This component combines the functionality of broker_input and broker_output with additional request-response handling.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: broker_request_response
component_config:
  broker_type: <string>
  broker_url: <string>
  broker_username: <string>
  broker_password: <string>
  broker_vpn: <string>
  payload_encoding: <string>
  payload_format: <string>
  request_expiry_ms: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| broker_type | True |  | Type of broker (Solace, MQTT, etc.) |
| broker_url | True |  | Broker URL (e.g. tcp://localhost:55555) |
| broker_username | True |  | Client username for broker |
| broker_password | True |  | Client password for broker |
| broker_vpn | True |  | Client VPN for broker |
| payload_encoding | False | utf-8 | Encoding for the payload (utf-8, base64, gzip, none) |
| payload_format | False | json | Format for the payload (json, yaml, text) |
| request_expiry_ms | False | 60000 | Expiry time for cached requests in milliseconds |


## Component Input Schema

```
{
  payload:   <any>,
  topic:   <string>,
  user_properties:   {
    <freeform-object>
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| payload | True | Payload of the request message to be sent to the broker |
| topic | True | Topic to send the request message to |
| user_properties | False | User properties to send with the request message |


## Component Output Schema

```
{
  request:   {
    payload:     <any>,
    topic:     <string>,
    user_properties:     {
      <freeform-object>
    }
  },
  response:   {
    payload:     <any>,
    topic:     <string>,
    user_properties:     {
      <freeform-object>
    }
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| request | True |  |
| request.payload | False |  |
| request.topic | False |  |
| request.user_properties | False |  |
| response | True |  |
| response.payload | False |  |
| response.topic | False |  |
| response.user_properties | False |  |
