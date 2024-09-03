# Aggregate

Take multiple messages and aggregate them into one. The output of this component is a list of the exact structure of the input data.
This can be useful for batch processing or for aggregating events together before processing them. The Aggregate component will take a sequence of events and combine them into a single event before enqueuing it to the next component in the flow so that it can perform batch processing.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: aggregate
component_config:
  max_items: <integer>
  max_time_ms: <integer>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| max_items | False | 10 | Number of input messages to aggregate before sending an output message |
| max_time_ms | False | 1000 | Number of milliseconds to wait before sending an output message |


## Component Input Schema

```
{
  <freeform-object>
}
```


## Component Output Schema

```
[
  {
    <freeform-object>
  },
  ...
]
```


## Example Configuration


```yaml
   - component_name: aggretator_example
     component_module: aggregate
     component_config: 
       # The maximum number of items to aggregate before sending the data to the next component
       max_items: 3
        # The maximum time to wait before sending the data to the next component
       max_time_ms: 1000
     input_selection:
       # Take the text field from the message and use it as the input to the aggregator
       source_expression: input.payload:text
```

