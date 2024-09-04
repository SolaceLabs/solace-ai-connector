# LangChainVectorStoreEmbeddingsIndex

Use LangChain Vector Stores to index text for later semantic searches. This will take text, run it through an embedding model and then store it in a vector database.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: langchain_vector_store_embedding_index
component_config:
  vector_store_component_path: <string>
  vector_store_component_name: <string>
  vector_store_component_config: <string>
  vector_store_index_name: <string>
  embedding_component_path: <string>
  embedding_component_name: <string>
  embedding_component_config: <string>
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


## Component Input Schema

```
{
  texts: [
    <string>,
    ...
  ],
  metadatas: [
    {
      <freeform-object>
    },
    ...
  ],
  ids: [
    <string>,
    ...
  ],
  action:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| texts | True |  |
| metadatas | False |  |
| ids | False | The ID of the text to add to the index. required for 'delete' action |
| action | False | The action to perform on the index from one of 'add', 'delete' |


## Component Output Schema

```
{
  <freeform-object>
}
```
