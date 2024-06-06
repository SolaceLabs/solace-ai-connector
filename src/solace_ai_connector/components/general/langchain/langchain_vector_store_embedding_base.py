# This is the base class for vector store embedding classes

from .langchain_base import (
    LangChainBase,
)


class LangChainVectorStoreEmbeddingsBase(
    LangChainBase
):  # pylint: disable=abstract-method

    def init(self):
        self.vector_store_info = {
            "name": self.get_config("vector_store_component_name"),
            "path": self.get_config("vector_store_component_path"),
            "config": self.get_config("vector_store_component_config", {}),
            "index": self.get_config("vector_store_index_name"),
        }

        self.embedding_info = {
            "name": self.get_config("embedding_component_name"),
            "path": self.get_config("embedding_component_path"),
            "config": self.get_config("embedding_component_config"),
        }

        # Create the embedding model
        embedding_class = self.load_component(
            self.embedding_info["path"], self.embedding_info["name"]
        )
        self.embedding = self.create_component(
            self.embedding_info["config"], embedding_class
        )

        # Create the vector store
        vector_store_class = self.load_component(
            self.vector_store_info["path"], self.vector_store_info["name"]
        )

        if "index" not in self.vector_store_info["config"]:
            self.vector_store_info["config"]["index"] = self.vector_store_info["index"]
        self.vector_store_info["config"]["embeddings"] = self.embedding
        self.vector_store_info["config"]["embedding_function"] = self.embedding

        # index is optional - remove it from the config if it is None
        if self.vector_store_info["config"]["index"] is None:
            del self.vector_store_info["config"]["index"]

        try:
            self.vector_store = self.create_component(
                self.vector_store_info["config"], vector_store_class
            )
        except Exception:  # pylint: disable=broad-except
            del self.vector_store_info["config"]["embeddings"]
            del self.vector_store_info["config"]["embedding_function"]
            self.vector_store = vector_store_class.from_texts(
                [], self.embedding, **self.vector_store_info["config"]
            )
