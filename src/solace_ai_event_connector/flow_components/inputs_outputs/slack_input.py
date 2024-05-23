import threading
import queue
import base64
import requests


from slack_bolt.adapter.socket_mode import SocketModeHandler
from solace_ai_event_connector.flow_components.inputs_outputs.slack_base import (
    SlackBase,
)
from solace_ai_event_connector.common.message import Message
from solace_ai_event_connector.common.log import log


info = {
    "class_name": "SlackInput",
    "description": (
        "Slack input component. The component connects to Slack using the Bolt API "
        "and receives messages from Slack channels."
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
        {
            "name": "max_file_size",
            "type": "number",
            "description": "The maximum file size to download from Slack in MB. Default: 20MB",
            "default": 20,
            "required": False,
        },
        {
            "name": "max_total_file_size",
            "type": "number",
            "description": "The maximum total file size to download "
            "from Slack in MB. Default: 20MB",
            "default": 20,
            "required": False,
        },
        {
            "name": "listen_to_channels",
            "type": "boolean",
            "description": "Whether to listen to channels or not. Default: False",
            "default": False,
            "required": False,
        },
        {
            "name": "send_history_on_join",
            "type": "boolean",
            "description": "Send history on join. Default: False",
            "default": False,
            "required": False,
        },
        {
            "name": "acknowledgement_message",
            "type": "string",
            "description": "The message to send to acknowledge the user's message has been received.",
            "required": False,
        },
    ],
    "output_schema": {
        "type": "object",
        "properties": {
            "event": {
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
                    "user_email": {
                        "type": "string",
                    },
                    "mentions": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "type": {
                        "type": "string",
                    },
                    "user_id": {
                        "type": "string",
                    },
                    "client_msg_id": {
                        "type": "string",
                    },
                    "ts": {
                        "type": "string",
                    },
                    "channel": {
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
                },
            },
        },
        "required": ["event"],
    },
}


class SlackInput(SlackBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.slack_receiver_queue = None
        self.slack_receiver = None
        self.init_slack_receiver()

    def init_slack_receiver(self):
        # Create a queue to get messages from the Slack receiver
        self.slack_receiver_queue = queue.Queue()
        self.stop_receiver_event = threading.Event()
        self.slack_receiver = SlackReceiver(
            app=self.app,
            slack_app_token=self.slack_app_token,
            slack_bot_token=self.slack_bot_token,
            input_queue=self.slack_receiver_queue,
            stop_event=self.stop_receiver_event,
            max_file_size=self.get_config("max_file_size"),
            max_total_file_size=self.get_config("max_total_file_size"),
            listen_to_channels=self.get_config("listen_to_channels"),
            send_history_on_join=self.get_config("send_history_on_join"),
            acknowledgement_message=self.get_config("acknowledgement_message"),
        )
        self.slack_receiver.start()

    def stop_component(self):
        self.stop_slack_receiver()

    def stop_slack_receiver(self):
        self.stop_receiver_event.set()
        self.slack_receiver.join()

    def get_next_message(self):
        # Get the next message from the Slack receiver queue
        message = self.slack_receiver_queue.get()
        return message

    def invoke(self, _message, data):
        return data


class SlackReceiver(threading.Thread):
    def __init__(
        self,
        app,
        slack_app_token,
        slack_bot_token,
        input_queue,
        stop_event,
        max_file_size=20,
        max_total_file_size=20,
        listen_to_channels=False,
        send_history_on_join=False,
        acknowledgement_message=None,
    ):
        threading.Thread.__init__(self)
        self.app = app
        self.slack_app_token = slack_app_token
        self.slack_bot_token = slack_bot_token
        self.input_queue = input_queue
        self.stop_event = stop_event
        self.max_file_size = max_file_size
        self.max_total_file_size = max_total_file_size
        self.listen_to_channels = listen_to_channels
        self.send_history_on_join = send_history_on_join
        self.acknowledgement_message = acknowledgement_message
        self.register_handlers()

    def run(self):
        SocketModeHandler(self.app, self.slack_app_token).connect()
        self.stop_event.wait()

    def handle_channel_event(self, event):
        # For now, just do the normal handling
        channel_name = self.get_channel_name(event.get("channel"))
        event["channel_name"] = channel_name

        self.handle_event(event)

    def handle_group_event(self, event):
        log.info("Received a private group event. Ignoring.")

    def handle_event(self, event):
        files = []
        total_file_size = 0
        if "files" in event:
            for file in event["files"]:
                file_url = file["url_private"]
                file_name = file["name"]
                size = file["size"]
                total_file_size += size
                if size > self.max_file_size * 1024 * 1024:
                    log.warning(
                        "File %s is too large to download. Skipping download.",
                        file_name,
                    )
                    continue
                if total_file_size > self.max_total_file_size * 1024 * 1024:
                    log.warning(
                        "Total file size exceeds the maximum limit. Skipping download."
                    )
                    break
                b64_file = self.download_file_as_base64_string(file_url)
                files.append(
                    {
                        "name": file_name,
                        "content": b64_file,
                        "mime_type": file["mimetype"],
                        "filetype": file["filetype"],
                        "size": size,
                    }
                )

        team_domain = None
        try:
            permalink = self.app.client.chat_getPermalink(
                channel=event["channel"], message_ts=event["event_ts"]
            )
            team_domain = permalink.get("permalink", "").split("//")[1]
            team_domain = team_domain.split(".")[0]
        except Exception as e:
            log.error("Error getting team domain: %s", e)

        user_email = self.get_user_email(event["user"])
        (text, mention_emails) = self.process_text_for_mentions(event["text"])
        payload = {
            "text": text,
            "files": files,
            "user_email": user_email,
            "team_id": event.get("team"),
            "team_domain": team_domain,
            "mentions": mention_emails,
            "type": event.get("type"),
            "client_msg_id": event.get("client_msg_id"),
            "ts": event.get("thread_ts"),
            "channel": event.get("channel"),
            "channel_name": event.get("channel_name", ""),
            "subtype": event.get("subtype"),
            "event_ts": event.get("event_ts"),
            "channel_type": event.get("channel_type"),
            "user_id": event.get("user"),
        }
        user_properties = {
            "user_email": user_email,
            "team_id": event.get("team"),
            "type": event.get("type"),
            "client_msg_id": event.get("client_msg_id"),
            "ts": event.get("thread_ts"),
            "channel": event.get("channel"),
            "subtype": event.get("subtype"),
            "event_ts": event.get("event_ts"),
            "channel_type": event.get("channel_type"),
            "user_id": event.get("user"),
        }

        if self.acknowledgement_message:
            ack_msg_ts = self.app.client.chat_postMessage(
                channel=event["channel"],
                text=self.acknowledgement_message,
                thread_ts=event.get("thread_ts"),
            ).get("ts")
            user_properties["ack_msg_ts"] = ack_msg_ts

        message = Message(payload=payload, user_properties=user_properties)
        message.set_previous(payload)
        self.input_queue.put(message)

    def download_file_as_base64_string(self, file_url):
        headers = {"Authorization": "Bearer " + self.slack_bot_token}
        response = requests.get(file_url, headers=headers, timeout=10)
        base64_string = base64.b64encode(response.content).decode("utf-8")
        return base64_string

    def get_user_email(self, user_id):
        response = self.app.client.users_info(user=user_id)
        return response["user"]["profile"].get("email", user_id)

    def process_text_for_mentions(self, text):
        mention_emails = []
        for mention in text.split("<@"):
            if mention.startswith("!"):
                mention = mention[1:]
            if mention.startswith("U"):
                user_id = mention.split(">")[0]
                response = self.app.client.users_info(user=user_id)
                profile = response.get("user", {}).get("profile")
                if profile:
                    replacement = profile.get(
                        "email", "<@" + profile.get("real_name_normalized") + ">"
                    )
                    mention_emails.append(replacement)
                    text = text.replace(
                        f"<@{user_id}>",
                        replacement,
                    )
        return text, mention_emails

    def get_channel_name(self, channel_id):
        response = self.app.client.conversations_info(channel=channel_id)
        return response["channel"].get("name")

    def get_channel_history(self, channel_id, team_id):
        response = self.app.client.conversations_history(channel=channel_id)

        # First search through messages to get all their replies
        messages_to_add = []
        for message in response["messages"]:
            if "subtype" not in message and "text" in message:
                if "reply_count" in message:
                    # Get the replies
                    replies = self.app.client.conversations_replies(
                        channel=channel_id, ts=message.get("ts")
                    )
                    messages_to_add.extend(replies["messages"])

        response["messages"].extend(messages_to_add)

        # Go through the messages and remove any that have a sub_type
        messages = []
        emails = {}
        for message in response["messages"]:
            if "subtype" not in message and "text" in message:
                if message.get("user") not in emails:
                    emails[message.get("user")] = self.get_user_email(
                        message.get("user")
                    )
                payload = {
                    "text": message.get("text"),
                    "team_id": team_id,
                    "user_email": emails[message.get("user")],
                    "mentions": [],
                    "type": message.get("type"),
                    "client_msg_id": message.get("client_msg_id") or message.get("ts"),
                    "ts": message.get("ts"),
                    "event_ts": message.get("event_ts") or message.get("ts"),
                    "channel": channel_id,
                    "subtype": message.get("subtype"),
                    "user_id": message.get("user"),
                    "message_id": message.get("client_msg_id"),
                }
                messages.append(payload)

        return messages

    def handle_new_channel_join(self, event):
        """We have been added to a new channel. This will get all the history and send it to the input queue."""
        history = self.get_channel_history(event.get("channel"), event.get("team"))
        payload = {
            "text": "New channel joined",
            "user_email": "",
            "mentions": [],
            "type": "channel_join",
            "client_msg_id": "",
            "ts": "",
            "channel": event.get("channel"),
            "subtype": "channel_join",
            "event_ts": "",
            "channel_type": "channel",
            "channel_name": self.get_channel_name(event.get("channel")),
            "user_id": "",
            "history": history,
        }
        user_properties = {
            "type": "channel_join",
            "channel": event.get("channel"),
            "subtype": "channel_join",
            "channel_type": "channel",
        }
        message = Message(payload=payload, user_properties=user_properties)
        message.set_previous(payload)
        self.input_queue.put(message)

    def register_handlers(self):
        @self.app.event("message")
        def handle_chat_message(event):
            print("Got message event: ", event, event.get("channel_type"))
            if event.get("channel_type") == "im":
                self.handle_event(event)
            elif event.get("channel_type") == "channel":
                self.handle_channel_event(event)
            elif event.get("channel_type") == "group":
                self.handle_group_event(event)

        @self.app.event("app_mention")
        def handle_app_mention(event):
            print("Got app_mention event: ", event)
            event["channel_type"] = "im"
            event["channel_name"] = self.get_channel_name(event.get("channel"))
            self.handle_event(event)

        @self.app.event("member_joined_channel")
        def handle_member_joined_channel(event, say, context):
            if (
                self.send_history_on_join
                and event.get("user") == context["bot_user_id"]
            ):
                self.handle_new_channel_join(event)
