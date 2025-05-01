# This is a wrapper around all the LangChain Vector Store components
# NOTE that LangChain always associates vector stores with an embedding model
# as well, so the configuration for this component will also include the
# embedding model configuration

from .....common.log import log
from .langchain_vector_store_embedding_base import (
    LangChainVectorStoreEmbeddingsBase,
)


info = {
    "class_name": "LangChainVectorStoreDelete",
    "description": (
        "This component allows for entries in a LangChain Vector Store to be "
        "deleted. This is needed for the continued maintenance of the vector store. "
        "Due to the nature of langchain vector stores, you need to specify an embedding component "
        "even though it is not used in this component."
    ),
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
            "description": (
                "Model specific configuration for the embedding model. "
                "See documentation for valid parameter names."
            ),
        },
        {
            "name": "delete_ids",
            "required": False,
            "allow_source_expression": True,
            "description": ("List of ids to delete from the vector store."),
        },
        {
            "name": "delete_kwargs",
            "required": True,
            "allow_source_expression": True,
            "description": (
                "Keyword arguments to pass to the delete method of the vector store."
                "See documentation for valid parameter names."
            ),
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to embed",
            },
            "metadata": {
                "type": "object",
                "description": "Metadata to associate with the text in the vector store. ",
            },
        },
        "required": ["text"],
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}


class LangChainVectorStoreDelete(LangChainVectorStoreEmbeddingsBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        delete_ids = self.get_config("delete_ids", None)
        delete_kwargs = self.get_config("delete_kwargs", {}).copy()
        delete_kwargs = self.resolve_callable_config(delete_kwargs, message)

        # Some special behavior for Milvus
        if delete_ids is None and self.vector_store_info["name"] == "Milvus":
            # Milvus can't do a search and delete in one step, so we need to
            # do a search first and then delete the results
            expr = delete_kwargs.get("expr", None)
            if expr is None:
                raise ValueError(
                    "In LangChainVectorStoreDelete, expr not provided in delete_kwargs"
                ) from None
            try:
                delete_ids = self.vector_store.get_pks(expr)
            except Exception:  # pylint: disable=broad-except
                log.warning("%sFailed to get pks from Milvus.", self.log_identifier)
                delete_ids = []
            del delete_kwargs["expr"]

        try:
            result = self.vector_store.delete(delete_ids, **delete_kwargs)
        except Exception:  # pylint: disable=broad-except
            log.warning("%sFailed to delete from vector store.", self.log_identifier)
            result = False
        return {"result": result}
