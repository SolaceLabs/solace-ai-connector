# Iterate

Take a single message that is a list and output each item in that list as a separate message

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: iterate
component_config:
```

No configuration parameters


## Component Input Schema

```
[
  {
    <freeform-object>
  },
  ...
]
```


## Component Output Schema

```
{
  <freeform-object>
}
```


## Example Configuration


```yaml
   - component_name: iterate_example
     component_module: iterate
     component_config: 
     input_selection:
       # Take the list field from the message and use it as the input to the iterator
       source_expression: input.payload:embeddings
```
