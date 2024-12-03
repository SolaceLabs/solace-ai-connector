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
            "items": {
                "type": "array",
                "description": "A single element or a list of elements to embed",
            },
            "type": {
                "type": "string",  # This is document, query, or image
                "description": "The type of embedding to use: 'document', 'query', or 'image' - default is 'document'",
            },
        },
        "required": ["items"],
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
        items = data["items"]
        embedding_type = data.get("type", "document")

        items = [items] if type(items) != list else items

        if embedding_type == "document":
            return self.embed_documents(items)
        elif embedding_type == "query":
            return self.embed_queries(items)
        elif embedding_type == "image":
            return self.embed_images(items)

    def embed_documents(self, documents):
        embeddings = self.component.embed_documents(documents)
        return {"embeddings": embeddings}
    
    def embed_queries(self, queries):
        embeddings = []
        for query in queries:
            embeddings.append(self.component.embed_query(query))
        return {"embeddings": embeddings}

    def embed_images(self, images):
        embeddings = self.component.embed_images(images)
        return {"embeddings": embeddings}
