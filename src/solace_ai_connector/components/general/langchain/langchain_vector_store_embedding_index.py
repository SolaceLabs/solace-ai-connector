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
        args = [texts]
        if metadatas is not None:
            if not isinstance(metadatas, list):
                metadatas = [metadatas]
            args.append(metadatas)

        # Add the texts to the vector store
        self.vector_store.add_texts(*args)
        return {"result": "OK"}
