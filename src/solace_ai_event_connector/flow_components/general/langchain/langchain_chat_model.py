# This is a wrapper around all the LangChain chat models
# The configuration will control dynamic loading of the chat models

from solace_ai_event_connector.flow_components.general.langchain.langchain_chat_model_base import (
    LangChainChatModelBase,
    info_base,
)


info = info_base
info["class_name"] = "LangChainChatModel"


class LangChainChatModel(LangChainChatModelBase):

    def invoke_model(
        self, input_message, messages, session_id=None, clear_history=False
    ):
        return self.component.invoke(messages)
