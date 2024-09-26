"""This test fixture will test the get_data and set_data methods of the Message class"""

import sys
sys.path.append("src")
import json
import base64
import pytest

from solace_ai_connector.common.message import Message

# Create a few different messages to test with
# We need to make sure we populate them with interesting and complicated payloads, user_properties and topics
# The topic format is a string with a length of 1 to 255 characters with levels separated by a forward slash (/)
# The user_properties is a dictionary with keys and values that are strings with a length of 1 to 255 characters
# The payload is a heirarchical JSON object with nested objects, arrays, strings, numbers, and booleans

# First create some payloads, user_properties, and topics to use in the messages. We can
# later reference these in the tests
payloads = {
    "simple": "simple payload",
    "simple_dict": {"key1": "value1", "key2": 2},
    "complex": {
        "key1": "value1",
        "key2": 2,
        "key3": [1, 2, 3],
        "key4": {"subkey1": "subvalue1", "subkey2": 4},
    },
    "deeply_nested": {
        "key1": {
            "subkey1": {
                "subsubkey1": {
                    "subsubsubkey1": {
                        "subsubsubsubkey1": {
                            "subsubsubsubsubkey1": "value1",
                        },
                    },
                },
            },
        },
    },
}

user_properties = {
    "simple": {"key1": "value1", "key2": "value2"},
    "long": {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
        "key4": "value4",
        "key5": "value5",
        "key6": "value6",
        "key7": "value7",
    },
}

topics = {
    "simple": "a/valid/topic",
    "long": "a/valid/topic/with/a/very/long/length/that/has/many/levels/and/characters",
}

messages = {
    "simple": Message(payload=payloads["simple"]),
    "complex": Message(
        payload=payloads["complex"],
    ),
    "with_user_properties": Message(
        payload=payloads["simple"],
        user_properties=user_properties["simple"],
    ),
    "with_topic": Message(payload=payloads["simple"], topic=topics["simple"]),
    "with_all": Message(
        payload=payloads["complex"],
        user_properties=user_properties["simple"],
        topic=topics["simple"],
    ),
    "long_topic": Message(
        payload=payloads["simple"],
        topic=topics["long"],
    ),
    "deeply_nested": Message(
        payload=payloads["deeply_nested"],
    ),
}

# Message.get_data will return the object, list, or string by evaluating the
# passed in expression according to the following rules:
# This will return the specified data from the message. The expression is a string that
# specifies the data to return. Has the following format:
#   <data_type>:<data_name>
# Where:
#   <data_type> is one of the following:
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


# The following tests will test the get_data method of the Message class
def test_get_data_simple_payload():
    """Test getting the payload of a message with a simple payload"""
    assert messages["simple"].get_data("input.payload") == payloads["simple"]


def test_get_data_complex_payload():
    """Test getting the payload of a message with a complex payload"""
    assert messages["complex"].get_data("input.payload") == payloads["complex"]


def test_get_data_with_user_properties():
    """Test getting the user_properties of a message with user_properties"""
    assert (
        messages["with_user_properties"].get_data("input.user_properties")
        == user_properties["simple"]
    )


def test_get_data_with_topic():
    """Test getting the topic of a message with a topic"""
    assert messages["with_topic"].get_data("input.topic") == topics["simple"]


def test_get_data_with_all():
    """Test getting all the data of a message with a payload, user_properties, and topic"""
    assert messages["with_all"].get_data("input.payload") == payloads["complex"]
    assert (
        messages["with_all"].get_data("input.user_properties")
        == user_properties["simple"]
    )
    assert messages["with_all"].get_data("input.topic") == topics["simple"]


def test_get_data_long_topic():
    """Test getting the topic of a message with a long topic"""
    assert messages["long_topic"].get_data("input.topic") == topics["long"]


def test_get_data_deeply_nested_payload():
    """Test getting a deeply nested value from a message with a deeply nested payload"""
    assert (
        messages["deeply_nested"].get_data(
            "input.payload:key1.subkey1.subsubkey1."
            "subsubsubkey1.subsubsubsubkey1.subsubsubsubsubkey1"
        )
        == "value1"
    )


def test_get_data_invalid_expression():
    """Test getting data from a message with an invalid expression"""
    with pytest.raises(ValueError):
        messages["simple"].get_data("invalid_expression")


def test_get_data_invalid_data_type():
    """Test getting data from a message with an invalid data type"""
    with pytest.raises(ValueError):
        messages["simple"].get_data("invalid_type:invalid_name")


def test_get_data_invalid_data_name():
    """Test getting data from a message with an invalid data name"""
    with pytest.raises(ValueError):
        messages["simple"].get_data("input.invalid_name")


def test_get_data_invalid_payload_name():
    """Test getting data from a message with an invalid payload name"""
    with pytest.raises(ValueError):
        messages["simple"].get_data("input.payload.invalid_name")


def test_get_data_with_template():
    """Test getting data from a message with a template"""
    message = Message(payload=payloads["simple"])
    assert (
        message.get_data(
            "template:This is a template with '{{input.payload}}' as the payload"
        )
        == f"This is a template with '{payloads['simple']}' as the payload"
    )


def test_get_data_with_complicated_template():
    """Test getting data from a message with a complicated template"""
    message = Message(payload={"item": {"subitem": "value"}}, topic=topics["simple"])
    assert (
        message.get_data(
            "template:This is a template with '{{yaml://input.payload:item}}' as the payload and '{{input.topic}}' and '{{input.topic}}' as the topic twice"
        )
        == f"This is a template with 'subitem: value\n' as the payload and '{message.topic}' and '{message.topic}' as the topic twice"
    )


def test_get_data_with_template_json():
    """Test getting data from a message with a template with a json format for the payload"""
    message = Message(payload=payloads["simple_dict"])
    json_payload = json.dumps(payloads["simple_dict"])
    assert (
        message.get_data(
            "template:This is a template with '{{json://input.payload}}' as the payload"
        )
        == f"This is a template with '{json_payload}' as the payload"
    )


def test_get_data_with_template_datauri():
    """Test getting data from a message with a template with a datauri format for the payload"""
    message = Message(payload=payloads["simple"])
    # Get the payload as base64 encoded
    b_payload = bytes(payloads["simple"], "utf-8")
    b64_payload = base64.b64encode(b_payload).decode("utf-8")
    assert (
        message.get_data(
            "template:This is a template with '{{datauri:image/png://input.payload}}' as the payload"
        )
        == f"This is a template with 'data:image/png;base64,{b64_payload}' as the payload"
    )


def test_get_data_with_base64():
    """Test getting data from a message with a base64 format for the payload"""
    message = Message(payload=payloads["simple"])
    # Get the payload as base64 encoded
    b_payload = bytes(payloads["simple"], "utf-8")
    b64_payload = base64.b64encode(b_payload).decode("utf-8")
    assert (
        message.get_data("template:Test base64: '{{base64://input.payload}}'")
        == f"Test base64: '{b64_payload}'"
    )


def test_get_data_with_previous():
    """Test getting data from a message with the previous data"""
    message = Message(payload=payloads["simple"])
    message.set_data("previous", payloads["simple"])
    assert message.get_data("previous") == payloads["simple"]


def test_get_data_with_static_value():
    """Test getting data from a message with a static value"""
    message = Message(payload=payloads["simple"])
    assert message.get_data("static:static_value") == "static_value"


def test_get_data_dangling_colon():
    """Test getting data from a message with a dangling colon"""
    message = Message(payload=payloads["simple"])
    assert message.get_data("input.payload:") == payloads["simple"]


def test_index_into_list():
    """Test getting data from a message by indexing into a list"""
    assert messages["complex"].get_data("input.payload:key3.1") == 2


def test_index_into_list_out_of_bounds():
    """Test getting data from a message by indexing into a list with an out of bounds index"""
    with pytest.raises(IndexError):
        messages["complex"].get_data("input.payload:key3.3")


def test_get_topic_levels():
    """Test getting the topic of a message as a list of levels"""
    assert messages["long_topic"].get_data("input.topic_levels") == topics[
        "long"
    ].split("/")


# The following tests will test the set_data method of the Message class
def test_set_data_user_data_simple():
    """Test setting user data on a message with a simple payload"""
    message = Message(payload=payloads["simple"])
    message.set_data("user_data.data1", "value1")
    assert message.get_data("user_data.data1") == "value1"


def test_set_data_user_data_dict():
    """Test setting user data on a message to a dictionary"""
    message = Message(payload=payloads["simple"])
    message.set_data("user_data.data1", {"key1": "value1", "key2": "value2"})
    assert message.get_data("user_data.data1") == {
        "key1": "value1",
        "key2": "value2",
    }


def test_set_data_user_data_list():
    """Test setting user data on a message to a list"""
    message = Message(payload=payloads["simple"])
    message.set_data("user_data.data1", [1, 2, 3])
    assert message.get_data("user_data.data1") == [1, 2, 3]


def test_set_data_user_data_add_more_to_existing():
    """Test setting user data with additional data"""
    message = Message(payload=payloads["simple"])
    message.set_data("user_data.data1", {"key1": "value1", "key2": "value2"})
    message.set_data("user_data.data1:key3", "value3")
    assert message.get_data("user_data.data1") == {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }


def test_set_data_user_data_overwrite_existing_property():
    """Test setting user data and overwriting a property to an existing object"""
    message = Message(payload=payloads["simple"])
    message.set_data("user_data.data1", {"key1": "value1", "key2": "value2"})
    message.set_data("user_data.data1:key2", "new_value")
    assert message.get_data("user_data.data1") == {
        "key1": "value1",
        "key2": "new_value",
    }


def test_set_data_user_data_overwrite_entire_object():
    """Test setting user data to replace an entire object"""
    message = Message(payload=payloads["simple"])
    message.set_data("user_data.data1", {"key1": "value1", "key2": "value2"})
    message.set_data("user_data.data1", {"key3": "new_value"})
    assert message.get_data("user_data.data1") == {"key3": "new_value"}


def test_set_data_user_data_overwrite_scalar():
    """Test setting user data to overwrite a scalar value"""
    message = Message(payload=payloads["simple"])
    message.set_data("user_data.data1", "value1")
    message.set_data("user_data.data1", "new_value")
    assert message.get_data("user_data.data1") == "new_value"


def test_set_data_user_data_create_new_list():
    """Test setting user data to create a new list"""
    message = Message(payload=payloads["simple"])
    message.set_data("user_data.data1", [1, 2, 3])
    message.set_data("user_data.data2", [4, 5, 6])
    assert message.get_data("user_data.data1") == [1, 2, 3]
    assert message.get_data("user_data.data2") == [4, 5, 6]


def test_set_data_user_data_overwrite_list():
    """Test setting user data to overwrite a list"""
    message = Message(payload=payloads["simple"])
    message.set_data("user_data.data1", [1, 2, 3])
    message.set_data("user_data.data1", [4, 5, 6])
    assert message.get_data("user_data.data1") == [4, 5, 6]


def test_set_data_input_payload():
    """Test setting the payload of a message"""
    message = Message(payload=payloads["simple"])
    message.set_data("input.payload", payloads["complex"])
    assert message.get_data("input.payload") == payloads["complex"]


def test_set_data_input_topic():
    """Test setting the topic of a message"""
    message = Message(payload=payloads["simple"])
    message.set_data("input.topic", topics["simple"])
    assert message.get_data("input.topic") == topics["simple"]


def test_set_data_input_user_properties():
    """Test setting the user_properties of a message"""
    message = Message(payload=payloads["simple"])
    message.set_data("input.user_properties", user_properties["simple"])
    assert message.get_data("input.user_properties") == user_properties["simple"]


def test_set_data_list_middle_failure():
    """Test setting a value in the middle of a list - but can't because the list entry is a scalar"""
    message = Message(payload=payloads["complex"])
    message.set_data("input.payload:key3.1.1", 5)
    assert message.get_data("input.payload:key3") == [1, 2, 3]


def test_set_data_list_middle_success():
    """Test setting a value in the middle of a list"""
    message = Message(payload=payloads["simple_dict"])
    message.set_data("input.payload:key7.1", 5)
    message.set_data("input.payload:key7.3.1", 6)
    assert message.get_data("input.payload:key7") == [None, 5, None, [None, 6]]


# Test all the getters and setters for the Message class
def test_get_set_payload():
    """Test getting and setting the payload of a message"""
    message = Message(payload=payloads["simple"])
    assert message.get_payload() == payloads["simple"]
    message.set_payload(payloads["complex"])
    assert message.get_payload() == payloads["complex"]


def test_get_set_topic():
    """Test getting and setting the topic of a message"""
    message = Message(payload=payloads["simple"], topic=topics["long"])
    assert message.get_topic() == topics["long"]
    message.set_topic(topics["simple"])
    assert message.get_topic() == topics["simple"]


def test_get_set_user_properties():
    """Test getting and setting the user_properties of a message"""
    message = Message(
        payload=payloads["simple"], user_properties=user_properties["long"]
    )
    assert message.get_user_properties() == user_properties["long"]
    message.set_user_properties(user_properties["simple"])
    assert message.get_user_properties() == user_properties["simple"]


def test_get_set_previous():
    """Test getting and setting the previous data of a message"""
    message = Message(payload=payloads["simple"])
    assert message.get_previous() is None
    message.set_previous(payloads["complex"])
    assert message.get_previous() == payloads["complex"]
