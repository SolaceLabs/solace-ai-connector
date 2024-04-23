

### Selecting Data

Within the configuration, it is necessary to select data for processing. For example, this happens
in the `component_input` section of the configuration or for the source data for input transforms.
The selection of data uses a simple expression language that allows you to select data from the
input message. 

The details of the expression language can be found in the [Configuration](configuration.md) page in the Expression Syntax section. The expression language allows for the detailed selection of data from the input message or for the
creation of new data. It even supports filling a template with data from the input message as described in detail in the next section.

### Selecting Data by Filling Templates

As part of the data selection expressions, it is possible to provide a full template string that will be filled with data from the input message. This is very useful for components that are interacting with Large Language Models (LLMs) or other AI models that typically take large amounts of text with some additional metadata sprinkled in. 

Here is an example configuration that uses a template to provide data for a component:

```yaml
   - component_name: template_example
     component_module: some_llm_component
     component_input:
       # Take the text field from the message and use it as the input to the component
       source_expression: |
          template:You are a helpful assistant who is an expert in animal husbandry. I would like you to answer this
          question by using the information following the question. Make sure to include the links to the data sources 
          that you used to answer the question.

          Question: {{input.payload:question}}

          Context: {{user_data.vector_store_results:results}}

```

In this example, a previous component did a vector store lookup on the question to get some context data.
Those results in addition to the original question are used to fill in the template for the LLM component.

Since this application usings `pyyaml`, it is possible to use the `!include` directive to include the template from 
a file. This can be useful for very large templates or for templates that are shared across multiple components.







### Aggregating Messages

The AI Event Connector has a special component called the `Aggregate` component that can be used to combine multiple events into a single event. This can be useful for batch processing or for aggregating events together before processing them. The `Aggregate` component will take a sequence of events and combine them into a single event before enqueuing it to the next component in the flow so that it can perform batch processing.

The `Aggregate` component has the following configuration options:
 - max_items: The maximum number of items to aggregate before sending the data to the next component
 - max_time_ms: The maximum time to wait (in milliseconds) before sending the data to the next component


Example Configuration:

```yaml
   - component_name: aggretator_example
     component_module: aggregate
     component_config: 
       # The maximum number of items to aggregate before sending the data to the next component
       max_items: 3
        # The maximum time to wait before sending the data to the next component
       max_time_ms: 1000
     component_input:
       # Take the text field from the message and use it as the input to the aggregator
       source_expression: input.payload:text
```


### Iterating Over Messages

The AI Event Connector has a special component called the `Iterate` component that can be used to iterate over a list within one message to create many messages for the next component. 

There is no specific configuration for the Iterate component other than the normal component_input configuration. That source must select a list of items to iterate over. 

Example Configuration:

```yaml
   - component_name: iterate_example
     component_module: iterate
     component_config: 
     component_input:
       # Take the list field from the message and use it as the input to the iterator
       source_expression: input.payload:embeddings
```
