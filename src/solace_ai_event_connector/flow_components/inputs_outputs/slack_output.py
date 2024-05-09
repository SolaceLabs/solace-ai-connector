import base64
from copy import deepcopy


from solace_ai_event_connector.flow_components.inputs_outputs.slack_base import (
    SlackBase,
)
from solace_ai_event_connector.common.message import Message
from solace_ai_event_connector.common.log import log


info = {
    "class_name": "SlackOutput",
    "description": (
        "Slack output component. The component sends messages to Slack channels using the Bolt API."
    ),
    "config_parameters": [
        {
            "name": "slack_bot_token",
            "type": "string",
            "description": "The Slack bot token to connect to Slack.",
        },
        {
            "name": "slack_app_token",
            "type": "string",
            "description": "The Slack app token to connect to Slack.",
        },
        {
            "name": "share_slack_connection",
            "type": "string",
            "description": "Share the Slack connection with other components in this instance.",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "message_info": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                    },
                    "type": {
                        "type": "string",
                    },
                    "user_email": {
                        "type": "string",
                    },
                    "client_msg_id": {
                        "type": "string",
                    },
                    "ts": {
                        "type": "string",
                    },
                    "subtype": {
                        "type": "string",
                    },
                    "event_ts": {
                        "type": "string",
                    },
                    "channel_type": {
                        "type": "string",
                    },
                    "user_id": {
                        "type": "string",
                    },
                    "session_id": {
                        "type": "string",
                    },
                },
                "required": ["channel", "session_id"],
            },
            "content": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                },
                                "content": {
                                    "type": "string",
                                },
                                "mime_type": {
                                    "type": "string",
                                },
                                "filetype": {
                                    "type": "string",
                                },
                                "size": {
                                    "type": "number",
                                },
                            },
                        },
                    },
                },
            },
        },
        "required": ["message_info", "content"],
    },
}


class SlackOutput(SlackBase):
    # def __init__(self, **kwargs):
    #     super().__init__(**kwargs)

    def invoke(self, message, data):
        message_info = data.get("message_info")
        content = data.get("content")
        text = content.get("text")
        channel = message_info.get("channel")
        thread_ts = message_info.get("ts")
        return {
            "channel": channel,
            "text": text,
            "files": content.get("files"),
            "thread_ts": thread_ts,
        }

    def send_message(self, message):
        channel = message.get_data("previous:channel")
        messages = message.get_data("previous:text")
        files = message.get_data("previous:files") or []
        thread_ts = message.get_data("previous:ts")

        if not isinstance(messages, list):
            if messages is not None:
                messages = [messages]
            else:
                messages = []

        for text in messages:
            self.app.client.chat_postMessage(
                channel=channel, text=text, thread_ts=thread_ts
            )

        for file in files:
            file_content = base64.b64decode(file["content"])
            self.app.client.files_upload_v2(
                channel=channel,
                file=file_content,
                thread_ts=thread_ts,
                filename=file["name"],
            )

        super().send_message(message)
