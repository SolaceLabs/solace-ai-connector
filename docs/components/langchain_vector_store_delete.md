# LangChainVectorStoreDelete

This component allows for entries in a LangChain Vector Store to be deleted. This is needed for the continued maintenance of the vector store. Due to the nature of langchain vector stores, you need to specify an embedding component even though it is not used in this component.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: langchain_vector_store_delete
component_config:
  vector_store_component_path: <string>
  vector_store_component_name: <string>
  vector_store_component_config: <string>
  vector_store_index_name: <string>
  embedding_component_path: <string>
  embedding_component_name: <string>
  embedding_component_config: <string>
  delete_ids: <string>
  delete_kwargs: <string>
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
| delete_ids | False |  | List of ids to delete from the vector store. |
| delete_kwargs | True |  | Keyword arguments to pass to the delete method of the vector store.See documentation for valid parameter names. |


## Component Input Schema

```
{
  text:   <string>,
  metadata:   {
    <freeform-object>
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| text | True | The text to embed |
| metadata | False | Metadata to associate with the text in the vector store.  |


## Component Output Schema

```
{
  <freeform-object>
}
```
