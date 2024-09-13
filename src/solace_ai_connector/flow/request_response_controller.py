"""
This file will handle sending a message to a named flow and then 
receiving the output message from that flow. It will also support the result
message being a streamed message that comes in multiple parts. 

Each component can optionally create multiple of these using the configuration:

```yaml
- name: example_flow
  components:
    - component_name: example_component
      component_module: custom_component
      request_response_controllers:
        - name: example_controller
          flow_name: llm_flow
          streaming: true
          streaming_last_message_expression: input.payload:streaming.last_message
          timeout_ms: 300000
```

"""

# <inst>
# - Create the request response flow manager class that will hold all the request response flows
# - Create the request response controller class that will hold the request response controller
#   config and manage sending messages to the flow and getting the output messages.
# </inst>
