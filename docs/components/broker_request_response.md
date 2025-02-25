# BrokerRequestResponse

Connect to a messaging broker, send request messages, and receive responses. This component combines the functionality of broker_input and broker_output with additional request-response handling.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: broker_request_response
component_config:
  broker_type: <string>
  dev_mode: <string>
  broker_url: <string>
  broker_username: <string>
  broker_password: <string>
  broker_vpn: <string>
  payload_encoding: <string>
  payload_format: <string>
  response_topic_prefix: <string>
  response_topic_suffix: <string>
  response_topic_insertion_expression: <string>
  response_queue_prefix: <string>
  user_properties_reply_topic_key: <string>
  user_properties_reply_metadata_key: <string>
  request_expiry_ms: <integer>
  streaming: <string>
  streaming_complete_expression: <string>
  streaming: <string>
  streaming_complete_expression: <string>
  streaming: <string>
  streaming_complete_expression: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| broker_type | False | solace | Type of broker (Solace, MQTT, etc.) |
| dev_mode | False | false | Operate in development mode, which just uses local queues |
| broker_url | True |  | Broker URL (e.g. tcp://localhost:55555) |
| broker_username | True |  | Client username for broker |
| broker_password | True |  | Client password for broker |
| broker_vpn | True |  | Client VPN for broker |
| payload_encoding | False | utf-8 | Encoding for the payload (utf-8, base64, gzip, none) |
| payload_format | False | json | Format for the payload (json, yaml, text) |
| response_topic_prefix | False | reply | Prefix for reply topics |
| response_topic_suffix | False |  | Suffix for reply topics |
| response_topic_insertion_expression | False |  | Expression to insert the reply topic into the request message. If not set, the reply topic will only be added to the request_response_metadata. The expression uses the same format as other data expressions: (e.g input.payload:myObj.replyTopic). If there is no object type in the expression, it will default to 'input.payload'. |
| response_queue_prefix | False | reply-queue | Prefix for reply queues |
| user_properties_reply_topic_key | False | __solace_ai_connector_broker_request_response_topic__ | Key to store the reply topic in the user properties. Start with : for nested object |
| user_properties_reply_metadata_key | False | __solace_ai_connector_broker_request_reply_metadata__ | Key to store the reply metadata in the user properties. Start with : for nested object |
| request_expiry_ms | False | 60000 | Expiry time for cached requests in milliseconds |
| streaming | False |  | The response will arrive in multiple pieces. If True, the streaming_complete_expression must be set and will be used to determine when the last piece has arrived. |
| streaming_complete_expression | False |  | The source expression to determine when the last piece of a streaming response has arrived. |
| streaming | False |  | The response will arrive in multiple pieces. If True, the streaming_complete_expression must be set and will be used to determine when the last piece has arrived. |
| streaming_complete_expression | False |  | The source expression to determine when the last piece of a streaming response has arrived. |
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
