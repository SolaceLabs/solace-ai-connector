# LangChainVectorStoreEmbeddingsSearch

Use LangChain Vector Stores to search a vector store with a semantic search. This will take text, run it through an embedding model with a query embedding and then find the closest matches in the store.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: langchain_vector_store_embedding_search
component_config:
  vector_store_component_path: <string>
  vector_store_component_name: <string>
  vector_store_component_config: <string>
  vector_store_index_name: <string>
  embedding_component_path: <string>
  embedding_component_name: <string>
  embedding_component_config: <string>
  max_results: <string>
  combine_context_from_same_source: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| vector_store_component_path | True |  | The vector store library path - e.g. 'langchain_community.vectorstores' |
| vector_store_component_name | True |  | The vector store to use - e.g. 'Pinecone' |
| vector_store_component_config | True |  | Model specific configuration for the vector store. See LangChain documentation for valid parameter names for this specific component (e.g. https://python.langchain.com/docs/integrations/vectorstores/pinecone). |
| vector_store_index_name | False |  | The name of the index to use |
| embedding_component_path | True |  | The embedding library path - e.g. 'langchain_community.embeddings' |
| embedding_component_name | True |  | The embedding model to use - e.g. BedrockEmbeddings |
| embedding_component_config | True |  | Model specific configuration for the embedding model. See documentation for valid parameter names. |
| max_results | True | 3 | The maximum number of results to return |
| combine_context_from_same_source | False | True | Set to False if you don't want to combine all the context from the same source. Default is True |


## Component Input Schema

```
{
  text:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| text | True |  |


## Component Output Schema

```
[
  {
    <freeform-object>
  },
  ...
]
```
