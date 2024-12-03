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
  response_topic_prefix: <string>
  response_topic_suffix: <string>
  response_queue_prefix: <string>
  request_expiry_ms: <integer>
  streaming: <string>
  streaming_complete_expression: <string>
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
| response_topic_prefix | False | reply | Prefix for reply topics |
| response_topic_suffix | False |  | Suffix for reply topics |
| response_queue_prefix | False | reply-queue | Prefix for reply queues |
| request_expiry_ms | False | 60000 | Expiry time for cached requests in milliseconds |
| streaming | False |  | The response will arrive in multiple pieces. If True, the streaming_complete_expression must be set and will be used to determine when the last piece has arrived. |
| streaming_complete_expression | False |  | The source expression to determine when the last piece of a streaming response has arrived. |


## Component Input Schema

```
{
  payload:   <any>,
  topic:   <string>,
  user_properties:   {
    <freeform-object>
  },
  response_topic_suffix:   <string>,
  stream:   <boolean>,
  streaming_complete_expression:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| payload | True | Payload of the request message to be sent to the broker |
| topic | True | Topic to send the request message to |
| user_properties | False | User properties to send with the request message |
| response_topic_suffix | False | Suffix for the reply topic |
| stream | False | Whether this will have a streaming response |
| streaming_complete_expression | False | Expression to determine when the last piece of a streaming response has arrived. Required if stream is True. |


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
