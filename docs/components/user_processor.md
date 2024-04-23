# UserProcessor

A component that allows the processing stage to be defined in the configuration file using 'invoke' statements. The configuration must be specified with the 'component_processing:' property alongside the 'component_module:' property in the component's configuration. The input and output schemas are free-form. The user-defined processing must line up with the input 

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: user_processor
component_config:
```

No configuration parameters


## Component Input Schema

```
{
  <freeform-object>
}
```


## Component Output Schema

```
{
  <freeform-object>
}
```
