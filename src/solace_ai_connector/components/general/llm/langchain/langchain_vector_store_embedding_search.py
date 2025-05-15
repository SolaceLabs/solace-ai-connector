""" This is a wrapper around all the LangChain Vector Store components for searching
NOTE that LangChain always associates vector stores with an embedding model
as well, so the configuration for this component will also include the
embedding model configuration
"""

from .....common.log import log
from .langchain_vector_store_embedding_base import (
    LangChainVectorStoreEmbeddingsBase,
)


info = {
    "class_name": "LangChainVectorStoreEmbeddingsSearch",
    "description": "Use LangChain Vector Stores to search a vector store with "
    "a semantic search. This will take text, run it through "
    "an embedding model with a query embedding and then find the closest matches in the store.",
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
        {
            "name": "max_results",
            "required": True,
            "description": "The maximum number of results to return",
            "default": 3,
        },
        {
            "name": "combine_context_from_same_source",
            "required": False,
            "description": "Set to False if you don't want to combine all the context from the same source. Default is True",
            "default": True,
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
        "description": "The aggregated messages",
        "items": {
            "type": "object",
        },
    },
}


class LangChainVectorStoreEmbeddingsSearch(LangChainVectorStoreEmbeddingsBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        text = data["text"]
        k = self.get_config("max_results", 3)
        combine_context_from_same_source = self.get_config(
            "combine_context_from_same_source"
        )
        try:
            result = self.vector_store.similarity_search(text, k=k)
        except Exception:
            log.error("Error while searching in the vector store")
            raise ValueError("Error while searching in the vector store.") from None
        log.debug("Searched and got result")
        # Clean up the result by looping through all the Documents and extracting the metadata and page_content
        # Loop through the results and extract the metadata and page_content
        clean = []
        for doc in result:
            metadata = doc.metadata
            # if the metadata has a 'pk' field, then delete it
            if "pk" in metadata:
                del metadata["pk"]
            clean.append(
                {
                    "text": doc.page_content,
                    "metadata": metadata,
                }
            )

        if combine_context_from_same_source:
            # Combine the context from the same source
            clean = self.combine_context(clean)

        # Limit the number of results to k
        clean = clean[:k]

        return {"result": clean}

    def combine_context(self, results):
        # Combine the context from the same source
        # Create a dictionary to hold the combined context
        combined = {}
        for result in results:
            # Get the text and metadata
            text = result["text"]
            metadata = result["metadata"]
            # Get the source
            source = metadata.get("source_link", "unknown")
            # If the source is not in the combined dictionary, then add it
            if source not in combined:
                combined[source] = {"text": text, "metadata": metadata}
            else:
                # If the source is in the combined dictionary, then append the text and metadata
                combined[source]["text"] += " " + text
                combined[source]["metadata"].update(metadata)
        # Convert the combined dictionary to a list
        combined_list = list(combined.values())
        return combined_list
