import threading
import queue
import requests
import base64


from threading import Event
from copy import deepcopy
from solace_ai_event_connector.flow_components.component_base import ComponentBase
from solace_ai_event_connector.common.message import Message
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
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
            "name": "max_file_size",
            "type": "number",
            "description": "The maximum file size to download from Slack in MB. Default: 20MB",
            "default": 20,
            "required": False,
        },
        {
            "name": "max_total_file_size",
            "type": "number",
            "description": "The maximum total file size to download from Slack in MB. Default: 20MB",
            "default": 20,
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


class SlackInput(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.slack_bot_token = self.get_config("slack_bot_token")
        self.slack_app_token = self.get_config("slack_app_token")
        self.app = App(token=self.slack_bot_token)
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
            queue=self.slack_receiver_queue,
            stop_event=self.stop_receiver_event,
            max_file_size=self.get_config("max_file_size"),
            max_total_file_size=self.get_config("max_total_file_size"),
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

    def invoke(self, message, data):
        return deepcopy(message.get_payload())


class SlackReceiver(threading.Thread):
    def __init__(
        self,
        app,
        slack_app_token,
        slack_bot_token,
        queue,
        stop_event,
        max_file_size=20,
        max_total_file_size=20,
    ):
        threading.Thread.__init__(self)
        self.app = app
        self.slack_app_token = slack_app_token
        self.slack_bot_token = slack_bot_token
        self.queue = queue
        self.stop_event = stop_event
        self.max_file_size = max_file_size
        self.max_total_file_size = max_total_file_size
        self.register_handlers()

    def run(self):
        SocketModeHandler(self.app, self.slack_app_token).connect()
        self.stop_event.wait()

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
                b64_file = self.download_file_as_base64_string(file_url, file_name)
                files.append(
                    {
                        "name": file_name,
                        "content": b64_file,
                        "mime_type": file["mimetype"],
                        "filetype": file["filetype"],
                        "size": size,
                    }
                )

        user_email = self.get_user_email(event["user"])
        (text, mention_emails) = self.process_text_for_mentions(event["text"])
        obj = {
            "text": text,
            "files": files,
            "user_email": user_email,
            "mentions": mention_emails,
            "type": event.get("type"),
            "client_msg_id": event.get("client_msg_id"),
            "ts": event.get("ts"),
            "channel": event.get("channel"),
            "subtype": event.get("subtype"),
            "event_ts": event.get("event_ts"),
            "channel_type": event.get("channel_type"),
            "user_id": event.get("user"),
        }
        message = Message(payload=obj)
        self.queue.put(message)

    def download_file_as_base64_string(self, file_url, file_name):
        headers = {"Authorization": "Bearer " + self.slack_bot_token}
        response = requests.get(file_url, headers=headers, timeout=10)
        base64_string = base64.b64encode(response.content).decode("utf-8")
        return base64_string

    def get_user_email(self, user_id):
        response = self.app.client.users_info(user=user_id)
        return response["user"]["profile"]["email"]

    def process_text_for_mentions(self, text):
        mention_emails = []
        for mention in text.split("<@"):
            if mention.startswith("!"):
                mention = mention[1:]
            if mention.startswith("U"):
                user_id = mention.split(">")[0]
                response = self.app.client.users_info(user=user_id)
                mention_emails.append(
                    response.get("user", {}).get("profile", {}).get("email")
                )
                text = text.replace(
                    f"<@{user_id}>",
                    response.get("user", {}).get("profile", {}).get("email"),
                )
        return text, mention_emails

    def register_handlers(self):
        @self.app.event("message")
        def handle_chat_message(event):
            self.handle_event(event)

        @self.app.event("app_mention")
        def handle_app_mention(event):
            self.handle_event(event)
