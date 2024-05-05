"""Base class for all Slack components"""

from abc import ABC, abstractmethod
from slack_bolt import App  # pylint: disable=import-error
from solace_ai_event_connector.flow_components.component_base import ComponentBase


class SlackBase(ComponentBase, ABC):
    _slack_apps = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.slack_bot_token = self.get_config("slack_bot_token")
        self.slack_app_token = self.get_config("slack_app_token")
        self.max_file_size = self.get_config("max_file_size", 20)
        self.max_total_file_size = self.get_config("max_total_file_size", 20)
        self.share_slack_connection = self.get_config("share_slack_connection")

        if self.share_slack_connection:
            if self.slack_bot_token not in SlackBase._slack_apps:
                self.app = App(token=self.slack_bot_token)
                SlackBase._slack_apps[self.slack_bot_token] = self.app
            else:
                self.app = SlackBase._slack_apps[self.slack_bot_token]
        else:
            self.app = App(token=self.slack_bot_token)

    @abstractmethod
    def invoke(self, message, data):
        pass

    def __str__(self):
        return self.__class__.__name__ + " " + str(self.config)

    def __repr__(self):
        return self.__str__()
