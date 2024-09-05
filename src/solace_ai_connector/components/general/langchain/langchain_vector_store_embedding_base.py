# This is the base class for vector store embedding classes
import inspect
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

        # Get the expected parameter names of the vector store class
        class_init_signature = inspect.signature(vector_store_class.__init__)
        class_param_names = [
            param.name
            for param in class_init_signature.parameters.values()
            if param.name != "self"
        ]

        # index is optional - not using it if "index" or "index_name" is provided in the config
        if self.vector_store_info["index"] and (
            "index" not in self.vector_store_info["config"]
            or "index_name" not in self.vector_store_info["config"]
        ):
            # Checking if the class expects 'index' or 'index_name' as a parameter
            if "index" in class_param_names:
                self.vector_store_info["config"]["index"] = self.vector_store_info[
                    "index"
                ]
            elif "index_name" in class_param_names:
                self.vector_store_info["config"]["index_name"] = self.vector_store_info[
                    "index"
                ]
            else:
                # If not defined, used "index" as a parameter
                self.vector_store_info["config"]["index"] = self.vector_store_info[
                    "index"
                ]

        # Checking if the vector store uses "embedding_function" or "embeddings" as a parameter
        if "embedding_function" in class_param_names:
            self.vector_store_info["config"]["embedding_function"] = self.embedding
        elif "embeddings" in class_param_names:
            self.vector_store_info["config"]["embeddings"] = self.embedding
        else:
            # If not defined, used "embeddings" as a parameter
            self.vector_store_info["config"]["embeddings"] = self.embedding

        try:
            self.vector_store = self.create_component(
                self.vector_store_info["config"], vector_store_class
            )
        except Exception:  # pylint: disable=broad-except
            if "embeddings" in self.vector_store_info["config"]:
                del self.vector_store_info["config"]["embeddings"]
            if "embedding_function" in self.vector_store_info["config"]:
                del self.vector_store_info["config"]["embedding_function"]
            self.vector_store = vector_store_class.from_texts(
                [], self.embedding, **self.vector_store_info["config"]
            )
