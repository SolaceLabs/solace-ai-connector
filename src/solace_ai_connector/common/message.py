# Message class. This is the type of object that is passed between components in the flow.
import re
import base64
import json
import yaml
import pprint

from .log import log
from .trace_message import TraceMessage
from .utils import set_data_value, get_data_value
from ..common import Message_NACK_Outcome


class Message:

    def __init__(self, payload=None, topic=None, user_properties=None):
        self.payload = payload
        self.topic = topic
        self.user_properties = user_properties or {}
        self.ack_callbacks = []
        self.nack_callbacks = []
        self.topic_delimiter = "/"
        self.private_data = {}
        self.iteration_data = {}
        self.keyword_args = {}
        self.invoke_data = None
        self.previous = None

    # This will return the specified data from the message. The expression is a string that
    # specifies the data to return. Has the following format:
    #   <data_type>:<data_name>
    # Where:
    #   <data_type> is one of the following:
    #     input                   - Object containing the payload, topic, and user_properties
    #     input.payload           - The payload of the message
    #     input.topic             - The topic of the message as a string
    #     input.topic_levels      - The topic of the message as a list of each level of the topic
    #     input.user_properities  - A user property of the message
    #     static:<value>          - A static value
    #     template:<template>     - A template that will be rendered using the message data
    #     previous                - The result from the previous component
    #     user_data.<name>        - User specified data that was the output of some previous
    #                               transform or component
    #   <data_name> is the name of the data to return. It can have the format:
    #     <name>[.<name>[.<...>]] - Names can be chained together to specify nested data
    #     <name>[.<number>]       - If the data is an array, the number specifies the index of the
    #                               array to return
    # For example:
    #   payload:my_array.3.name   - Returns the name of the 4th element of the array called my_array
    #
    # The type of the data returned will depend on the data type specified. It could be an object,
    # array, string, etc.
    def get_data(self, expression, calling_object=None, data_type=None):
        # If the expression is callable, call it
        if callable(expression):
            return expression(self)
        if isinstance(expression, (dict, list)):
            return expression
        # If the expression starts with 'template:', render the template
        if expression.startswith("template:"):
            return self.fill_template(expression.split(":", 1)[1])
        if expression.startswith("static:"):
            return expression.split(":", 1)[1]
        data_object = self.get_data_object(expression, calling_object=calling_object)
        data = get_data_value(data_object, expression)

        if data_type:
            data = self.convert_data_type(data, data_type)

        return data

    def convert_data_type(self, data, data_type):
        type_map = {
            "string": str,
            "int": int,
            "float": float,
            "bool": bool,
        }
        if isinstance(data, (dict, list)):
            # Can't convert a dict or list to a primitive type
            return data
        return type_map.get(data_type, str)(data)

    def set_data(self, expression, value):
        if ":" not in expression:
            self.set_data_object(expression, value)
        else:
            data_name = expression.split(":")[1]
            first_part = data_name.split(".")[0]
            data_object = self.get_data_object(
                expression,
                create_if_not_exists=True,
                create_value={} if not first_part.isdigit() else [],
            )
            set_data_value(data_object, expression, value)

    def get_data_object(
        self,
        expression,
        create_if_not_exists=False,
        create_value=None,
        calling_object=None,
    ):
        data_type = expression.split(":")[0]

        if data_type == "input":
            return {
                "payload": self.payload,
                "topic": self.topic,
                "user_properties": self.user_properties,
            }
        if data_type == "input.payload":
            return self.payload
        if data_type == "input.topic":
            return self.topic
        if data_type == "input.topic_levels":
            return self.topic.split(self.topic_delimiter)
        if data_type == "input.user_properties":
            return self.user_properties
        if data_type == "invoke_data":
            return self.invoke_data
        if data_type == "previous":
            return getattr(self, "previous", {})
        if data_type == "item":
            return self.iteration_data["item"]
        if data_type == "index":
            return self.iteration_data["index"]
        if data_type == "keyword_args":
            return self.keyword_args
        if data_type == "self":
            return calling_object
        if data_type.startswith("user_data."):
            user_data_name = data_type.split(".")[1]
            obj = self.private_data.get(user_data_name, create_value)
            if create_if_not_exists:
                self.private_data[user_data_name] = obj
            return obj

        raise ValueError(
            f"Unknown data type '{data_type}' in expression '{expression}'"
        ) from None

    def set_data_object(self, expression, value):
        data_type = expression.split(":")[0]

        if data_type == "input.payload":
            self.payload = value
        elif data_type == "input.topic":
            self.topic = value
        elif data_type == "input.user_properties":
            self.user_properties = value
        elif data_type == "invoke_data":
            self.invoke_data = value
        elif data_type == "previous":
            self.previous = value
        elif data_type.startswith("user_data."):
            user_data_name = data_type.split(".")[1]
            self.private_data[user_data_name] = value
        else:
            raise ValueError(
                f"Unknown data type '{data_type}' in expression '{expression}'"
            ) from None

    def set_iteration_data(self, item, index):
        self.iteration_data["item"] = item
        self.iteration_data["index"] = index

    def clear_iteration_data(self):
        self.iteration_data = {}

    def set_keyword_args(self, keyword_args):
        self.keyword_args = keyword_args

    def clear_keyword_args(self):
        self.keyword_args = {}

    def get_keyword_arg(self, expression):
        if ":" not in expression:
            return self.keyword_args
        keyword_arg_name = expression.split(":")[1]
        return self.keyword_args.get(keyword_arg_name)

    # This will return a string that is the result of rendering the template with the message data
    # The template is a string that can contain embedded expressions. Has the following format:
    # "text text {{ <encoding>://<expression> }} text text"
    # The encoding is optional and defaults to 'json'. It can be one of the following:
    #   json    - The data retrieved from the expression will be converted to JSON
    #   yaml    - The data retrieved from the expression will be converted to YAML
    #   text    - The data retrieved from the expression will be converted to a string
    #   base64  - The data retrieved from the expression will be converted to a base64 string
    #   dataurl:<mimetype> - The data retrieved from the expression will
    #             be converted to a base64 encoded data URL
    #
    # The expression is the same form as the <data_type>:<data_name> expression in get_data
    def fill_template(self, template):
        # Loop through the template and find all the expressions
        result = re.sub(
            r"\{\{(.+?)\}\}",
            lambda match: self.replace_expression(match.group(1)),
            template,
        )
        return result

    def replace_expression(self, encoding_expression):
        # Split the encoding and expression
        encoding_expression_parts = encoding_expression.split("://")
        if len(encoding_expression_parts) == 1:
            log.info(
                "Format not specified in template '%s' - defaulting to 'text://%s'",
                encoding_expression,
                encoding_expression,
            )
            encoding_expression_parts.insert(0, "text")
        encoding, expression = encoding_expression_parts

        # Get the data
        data = self.get_data(expression)

        # Convert the data to the specified encoding
        if encoding == "json":
            data = json.dumps(data)
        elif encoding == "yaml":
            data = yaml.dump(data)
        elif encoding == "text":
            data = str(data)
        elif encoding == "base64":
            data = base64.b64encode(bytes(data, "utf-8")).decode("utf-8")
        elif encoding.startswith("datauri:"):
            mime_type = encoding.split(":")[1]
            data = f"data:{mime_type};base64,{base64.b64encode(bytes(data, 'utf-8')).decode('utf-8')}"
        else:
            raise ValueError(
                f"Unknown encoding '{encoding}' in expression '{encoding_expression}'"
            ) from None

        return data

    def set_private_data(self, key, value):
        self.private_data[key] = value

    def get_private_data(self, key):
        return self.private_data.get(key)

    def set_payload(self, payload):
        self.payload = payload

    def get_payload(self):
        return self.payload

    def set_invoke_data(self, invoke_data):
        self.invoke_data = invoke_data

    def get_invoke_data(self):
        return self.invoke_data

    def set_topic(self, topic):
        self.topic = topic

    def get_topic(self):
        return self.topic

    def set_user_properties(self, user_properties):
        self.user_properties = user_properties

    def get_user_properties(self):
        return self.user_properties

    def get_user_data(self):
        return self.private_data

    def set_previous(self, previous):
        self.previous = previous

    def get_previous(self):
        return self.previous

    def add_acknowledgement(self, callback):
        self.ack_callbacks.append(callback)

    def add_negative_acknowledgements(self, callback):
        self.nack_callbacks.append(callback)

    def call_acknowledgements(self):
        """Call all the ack callbacks. This is used to notify the previous components that the
        message has been acknowledged."""
        ack_callbacks = self.ack_callbacks
        self.ack_callbacks = []
        for callback in ack_callbacks:
            callback()

    def call_negative_acknowledgements(self, nack=Message_NACK_Outcome.REJECTED):
        """Call all the ack callbacks. This is used to notify the previous components that the
        message has been acknowledged."""
        nack_callbacks = self.nack_callbacks
        self.nack_callbacks = []
        for callback in nack_callbacks:
            callback(nack)

    def set_topic_delimiter(self, topic_delimiter):
        self.topic_delimiter = topic_delimiter

    def combine_with_message(self, message):
        # All we need is the list of ack callbacks
        message.ack_callbacks.extend(self.ack_callbacks)

    def trace(self, trace_queue, location, trace_type):
        trace_string = ""
        if (self.payload is not None) and (len(self.payload) > 0):
            trace_string = (
                trace_string
                + "Input Payload: \n"
                + pprint.pformat(self.payload, indent=4)
            )
        if (self.topic is not None) and (len(self.topic) > 0):
            trace_string = trace_string + "\nInput Topic: \n" + self.topic
        if (self.user_properties is not None) and (len(self.user_properties) > 0):
            trace_string = (
                trace_string
                + "Input User Properties: \n"
                + pprint.pformat(self.user_properties, indent=4)
            )
        if (self.private_data is not None) and (len(self.private_data) > 0):
            trace_string = (
                trace_string
                + "User Data: \n"
                + pprint.pformat(self.private_data, indent=4)
            )
        if self.previous is not None:
            trace_string = (
                trace_string
                + "\nOutput from previous stage: \n"
                + pprint.pformat(self.previous, indent=4)
            )
        trace_message = TraceMessage(
            location=location,
            message=trace_string,
            trace_type=trace_type,
        )
        trace_queue.put(trace_message)

    def __str__(self):
        return (
            f"Message(payload={self.payload}, topic={self.topic}, "
            f"user_properties={self.user_properties}, previous={self.previous}, "
            f"private_data={self.private_data}), ack_callbacks={len(self.ack_callbacks)}"
        )
