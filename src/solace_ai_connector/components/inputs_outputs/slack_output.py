import base64


from .slack_base import SlackBase
from ...common.log import log


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
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        message_info = data.get("message_info")
        content = data.get("content")
        text = content.get("text")
        stream = content.get("stream")
        channel = message_info.get("channel")
        thread_ts = message_info.get("ts")
        ack_msg_ts = message_info.get("ack_msg_ts")

        return {
            "channel": channel,
            "text": text,
            "files": content.get("files"),
            "thread_ts": thread_ts,
            "ack_msg_ts": ack_msg_ts,
            "stream": stream,
        }

    def send_message(self, message):
        try:
            channel = message.get_data("previous:channel")
            messages = message.get_data("previous:text")
            stream = message.get_data("previous:stream")
            files = message.get_data("previous:files") or []
            thread_ts = message.get_data("previous:ts")
            ack_msg_ts = message.get_data("previous:ack_msg_ts")

            if not isinstance(messages, list):
                if messages is not None:
                    messages = [messages]
                else:
                    messages = []

            for text in messages:
                if stream:
                    if ack_msg_ts:
                        try:
                            self.app.client.chat_update(
                                channel=channel, ts=ack_msg_ts, text=text
                            )
                        except Exception:
                            # It is normal to possibly get an update after the final message has already
                            # arrived and deleted the ack message
                            pass
                else:
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
        except Exception as e:
            log.error("Error sending slack message: %s", e)

        super().send_message(message)

        try:
            if ack_msg_ts and not stream:
                self.app.client.chat_delete(channel=channel, ts=ack_msg_ts)
        except Exception:
            pass
