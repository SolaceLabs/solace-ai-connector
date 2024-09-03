"""A flow component that aggregates messages"""

# from ...common.log import log
from ..component_base import ComponentBase
from ...common.message import Message

info = {
    "class_name": "Aggregate",
    "description": "Take multiple messages and aggregate them into one. "
    "The output of this component is a list of the exact structure "
    "of the input data.\n"
    "This can be useful for batch processing or for aggregating events "
    "together before processing them. The Aggregate component will take a "
    "sequence of events and combine them into a single event before enqueuing "
    "it to the next component in the flow so that it can perform batch processing.",
    "short_description": "Aggregate messages into one message.",
    "config_parameters": [
        {
            "name": "max_items",
            "required": False,
            "default": 10,
            "type": "integer",
            "description": "Number of input messages to aggregate before sending an output message",
        },
        {
            "name": "max_time_ms",
            "required": False,
            "description": "Number of milliseconds to wait before sending an output message",
            "default": 1000,
            "type": "integer",
        },
    ],
    "input_schema": {
        "type": "object",
        "description": "The input message to be aggregated",
        "properties": {},
    },
    "output_schema": {
        "type": "array",
        "description": "The aggregated messages",
        "items": {
            "type": "object",
        },
    },
    "example_config": """
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

""",
}


class Aggregate(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.current_aggregation = None
        self.aggregate_dest = self.get_config("aggregate_dest")
        self.max_time_ms = self.get_config("max_time_ms")
        self.max_items = self.get_config("max_items")

    def invoke(self, message, data):
        # The passed in data is the date specified by input_selection
        # from the config file
        if self.current_aggregation is None:
            self.current_aggregation = self.start_new_aggregation()

        self.current_aggregation["list"].append(data)
        message.combine_with_message(self.current_aggregation["message"])

        if len(self.current_aggregation["list"]) >= self.max_items:
            self.cancel_timer("aggregate_timeout")
            result = self.get_aggregation()
            self.current_aggregation = None
            return result

    def handle_timer_event(self, timer_data):
        if (
            timer_data["timer_id"] == "aggregate_timeout"
            and self.current_aggregation is not None
        ):
            aggregated_data = self.get_aggregation()
            message = self.current_aggregation["message"]
            self.current_aggregation = None
            self.process_post_invoke(aggregated_data, message)

    def start_new_aggregation(self):
        self.add_timer(self.max_time_ms, "aggregate_timeout")
        return {
            "list": [],
            "message": Message(),
        }

    def get_aggregation(self):
        aggregation = self.current_aggregation
        return aggregation["list"]
