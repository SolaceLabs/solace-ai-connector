# This is a wrapper around all the LangChain Vector Store components
# NOTE that LangChain always associates vector stores with an embedding model
# as well, so the configuration for this component will also include the
# embedding model configuration

from .langchain_vector_store_embedding_base import (
    LangChainVectorStoreEmbeddingsBase,
)


info = {
    "class_name": "LangChainVectorStoreEmbeddingsIndex",
    "description": "Use LangChain Vector Stores to index text for "
    "later semantic searches. This will take text, run it through "
    "an embedding model and then store it in a vector database.",
    "config_parameters": [
        {
            "name": "vector_store_component_path",
            "required": True,
            "description": "The vector store library path - e.g. "
            "'langchain_community.vectorstores'",
        },
        {
            "name": "vector_store_component_name",
            "required": True,
            "description": "The vector store to use - e.g. 'Pinecone'",
        },
        {
            "name": "vector_store_component_config",
            "required": True,
            "description": "Model specific configuration for the vector store. See "
            "LangChain documentation for valid parameter names for this specific component "
            "(e.g. https://python.langchain.com/docs/integrations/vectorstores/pinecone).",
        },
        {
            "name": "vector_store_index_name",
            "required": False,
            "description": "The name of the index to use",
        },
        {
            "name": "embedding_component_path",
            "required": True,
            "description": "The embedding library path - e.g. 'langchain_community.embeddings'",
        },
        {
            "name": "embedding_component_name",
            "required": True,
            "description": "The embedding model to use - e.g. BedrockEmbeddings",
        },
        {
            "name": "embedding_component_config",
            "required": True,
            "description": "Model specific configuration for the embedding model. "
            "See documentation for valid parameter names.",
        },
        # {
        #     "name": "max_results",
        #     "required": True,
        #     "description": "The maximum number of results to return",
        # },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "texts": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
            "metadatas": {
                "type": "array",
                "items": {
                    "type": "object",
                },
            },
            "ids": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "description": "The ID of the text to add to the index. required for 'delete' action",
            },
            "action": {
                "type": "string",
                "default": "add",
                "description": "The action to perform on the index from one of 'add', 'delete'",
            },
        },
        "required": ["texts"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            #     "results": {
            #         "type": "object",
            #         "properties": {
            #             "matches": {
            #                 "type": "array",
            #                 "items": {
            #                     "type": "object",
            #                     "properties": {
            #                         "text": {"type": "string"},
            #                         "metadata": {"type": "object"},
            #                         "score": {"type": "float"},
            #                     },
            #                     "required": ["text"],
            #                 },
            #             },
            #         },
            #     }
        },
        "required": ["results"],
    },
}


class LangChainVectorStoreEmbeddingsIndex(LangChainVectorStoreEmbeddingsBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        # Get the texts and normalize them
        texts = data["texts"]

        if not isinstance(texts, list):
            texts = [texts]

        # Get the metadatas if they exist
        metadatas = data.get("metadatas", None)
        if metadatas is not None:
            if not isinstance(metadatas, list):
                # repeat metadata for each text
                metadatas = [metadatas for _ in range(len(texts))]

        # Get the ids if they exist
        ids = data.get("ids", None)
        if ids is not None:
            if not isinstance(ids, list):
                # repeat metadata for each text
                ids = [ids for _ in range(len(texts))]

        action = data.get("action", "add")
        match action:
            case "add":
                return self.add_data(texts, metadatas, ids)
            case "delete":
                return self.delete_data(ids)
            case _:
                raise ValueError("Invalid action: {}".format(action)) from None

    def add_data(self, texts, metadatas=None, ids=None):
        # Add the texts to the vector store
        args = [texts]
        if metadatas is not None:
            args.append(metadatas)

        self.vector_store.add_texts(*args, ids=ids)
        return {"result": "OK"}

    def delete_data(self, ids):
        if not ids:
            raise ValueError("No IDs provided to delete") from None
        self.vector_store.delete(ids)
        return {"result": "OK"}
