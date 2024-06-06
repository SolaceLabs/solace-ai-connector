# This is a wrapper around all the LangChain Text Embedding models
# The configuration will control dynamic loading of the specific model

from .langchain_base import (
    LangChainBase,
)

info = {
    "class_name": "LangChainEmbeddings",
    "short_description": "Provide access to all the LangChain Text Embeddings components via configuration",
    "description": "Provide access to all the LangChain Text Embeddings components via configuration",
    "config_parameters": [
        {
            "name": "langchain_module",
            "required": True,
            "type": "string",
            "description": "The chat model module - e.g. 'langchain_openai.chat_models'",
        },
        {
            "name": "langchain_class",
            "required": True,
            "type": "string",
            "description": "The chat model class to use - e.g. ChatOpenAI",
        },
        {
            "name": "langchain_component_config",
            "required": True,
            "type": "object",
            "description": "Model specific configuration for the chat model. "
            "See documentation for valid parameter names.",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to embed",
            },
            "type": {
                "type": "string",  # This is document or query
                "description": "The type of embedding to use: 'document' or 'query' - default is 'document'",
            },
        },
        "required": ["text"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "embedding": {
                "type": "array",
                "description": (
                    "A list of floating point numbers representing the embedding. "
                    "Its length is the size of vector that the embedding model produces"
                ),
                "items": {"type": "float"},
            }
        },
        "required": ["embedding"],
    },
}


class LangChainEmbeddings(LangChainBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        text = data["text"]
        embedding_type = data.get("type", "document")

        embeddings = None
        if embedding_type == "document":
            embeddings = self.component.embed_documents([text])
        elif embedding_type == "query":
            embeddings = [self.component.embed_query(text)]

        return {"embedding": embeddings[0]}
