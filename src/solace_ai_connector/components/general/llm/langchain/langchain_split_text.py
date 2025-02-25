# This component splits a long text into smaller parts using the LangChain text splitter module

from .....common.log import log

from .langchain_base import (
    LangChainBase,
)


info = {
    "class_name": "LangChainTextSplitter",
    "description": "Split a long text into smaller parts using the LangChain text splitter module",
    "config_parameters": [
        {
            "name": "enabled",
            "required": False,
            "description": "Disable/Enable the splitter",
        },
        {
            "name": "langchain_module",
            "required": True,
            "description": "The text split module - e.g. 'langchain_text_splitters'",
        },
        {
            "name": "langchain_class",
            "required": True,
            "description": "The text split class to use - e.g. TokenTextSplitter",
        },
        {
            "name": "langchain_component_config",
            "required": True,
            "description": "Model specific configuration for the text splitting. "
            "See documentation for valid parameter names."
            "https://python.langchain.com/docs/how_to/split_by_token/#nltk",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
            },
        },
        "required": ["text"],
    },
    "output_schema": {
        "type": "array",
        "items": {
            "type": "string",
        },
        "description": ("A list of the split text"),
    },
}


class LangChainTextSplitter(LangChainBase):
    """
    A class to split a long text into smaller parts using the LangChain text splitter module.

    This class inherits from LangChainBase and utilizes the LangChain text splitter module
    to divide a given text into smaller segments based on the specified configuration.
    """

    def __init__(self, **kwargs):
        """
        Initialize the LangChainTextSplitter with the provided configuration.

        Args:
            **kwargs: Arbitrary keyword arguments containing configuration parameters.
        """
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        """
        Split the provided text into smaller parts using the LangChain text splitter module.

        Args:
            message (Message): The message object containing metadata.
            data (dict): A dictionary containing the input text to be split.

        Returns:
            list: A list of strings representing the split text segments.
        """
        try:
            is_active = self.get_config("enabled", True)
            if not is_active:
                log.info("Text splitter is disabled.")
                return data

            chunks = self.component.split_text(data)
            log.debug(f"Chunk: {chunks}")
            return chunks
        except Exception as e:
            log.error(f"Error splitting text: {str(e)}")
            return []
