# ErrorInput

Receive processing errors from the Solace AI Event Connector. Note that the input_selection configuration is ignored. This component should be used to create a flow that handles errors from other flows. 

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: error_input
component_config:
  max_rate: <string>
  max_queue_depth: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| max_rate | False | None | Maximum rate of errors to process per second. Any errors above this rate will be dropped. If not set, all errors will be processed. |
| max_queue_depth | False | 1000 | Maximum number of messages that can be queued in the input queue.If the queue is full, the new message is dropped. |



## Component Output Schema

```
{
  error:   {
    message:     <string>,
    exception:     <string>
  },
  message:   {
    payload:     <string>,
    topic:     <string>,
    user_properties:     {
      <freeform-object>
    },
    user_data:     {
      <freeform-object>
    },
    previous:     {
      <freeform-object>
    }
  },
  location:   {
    instance:     <integer>,
    flow:     <string>,
    component:     <string>
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| error | True | Information about the error |
| error.message | True | The error message |
| error.exception | True | The exception message |
| message | True | The message that caused the error |
| message.payload | False | The payload of the message |
| message.topic | False | The topic of the message |
| message.user_properties | False | The user properties of the message |
| message.user_data | False | The user data of the message that was created during the flow |
| message.previous | False | The output from the previous stage that was processed before the error |
| location | True | The location where the error occurred |
| location.instance | False | The instance number of the component that generated the error |
| location.flow | True | The flow name of the component that generated the error |
| location.component | True | The component name that generated the error |
