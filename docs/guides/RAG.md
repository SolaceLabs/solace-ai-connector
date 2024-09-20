
- [Building AI-Powered Applications with Solace AI Connector: A Deep Dive into RAG, LLMs, and Embeddings](#building-ai-powered-applications-with-solace-ai-connector-a-deep-dive-into-rag-llms-and-embeddings)
  - [What is Solace AI Connector?](#what-is-solace-ai-connector)
  - [Key Concepts Behind the Configuration](#key-concepts-behind-the-configuration)
    - [1. Large Language Models (LLMs)](#1-large-language-models-llms)
    - [2. Retrieval-Augmented Generation (RAG)](#2-retrieval-augmented-generation-rag)
    - [3. Embeddings](#3-embeddings)
    - [4. Solace PubSub+ Platform](#4-solace-pubsub-platform)
  - [Real-Time Data Consumption with Solace AI Connector](#real-time-data-consumption-with-solace-ai-connector)
    - [Real-Time Data Embedding and Storage Flow](#real-time-data-embedding-and-storage-flow)
  - [YAML Configuration Breakdown](#yaml-configuration-breakdown)
    - [Logging Configuration](#logging-configuration)
    - [Shared Configuration for Solace Broker](#shared-configuration-for-solace-broker)
    - [Data Ingestion to ChromaDB (Embedding Flow)](#data-ingestion-to-chromadb-embedding-flow)
      - [1. Solace Data Input Component](#1-solace-data-input-component)
      - [2. Embedding and Storage in ChromaDB](#2-embedding-and-storage-in-chromadb)
    - [RAG Inference Flow (Query and Response)](#rag-inference-flow-query-and-response)
      - [1. Query Ingestion from Solace Topic](#1-query-ingestion-from-solace-topic)
      - [2. ChromaDB Search for Relevant Documents](#2-chromadb-search-for-relevant-documents)
      - [3. Response Generation Using OpenAI](#3-response-generation-using-openai)
      - [4. Sending the Response Back to Solace](#4-sending-the-response-back-to-solace)
  - [Flexibility in Components](#flexibility-in-components)
  - [Conclusion](#conclusion)

# Building AI-Powered Applications with Solace AI Connector: A Deep Dive into RAG, LLMs, and Embeddings

In the fast-evolving world of AI, businesses are increasingly looking for ways to harness advanced technologies like **Retrieval-Augmented Generation (RAG)** and **Large Language Models (LLMs)** to provide smarter, more interactive applications. **Solace AI Connector** is one such CLI tool that allows you to create AI-powered applications interconnected to Solace's PubSub+ brokers. In this guide, we will explore the configuration of Solace AI Connector, how it can be used with technologies like **RAG**, **LLMs**, and **Embeddings**, and provide a deep understanding of these concepts.

## What is Solace AI Connector?

Solace AI Connector is a tool that enables AI-powered applications to interface with Solace PubSub+ brokers. By integrating Solace’s event-driven architecture with AI services (such as OpenAI’s models), you can create applications that interact with real-time data, perform knowledge retrieval, and generate intelligent responses.

In this guide, we will walk through [a sample YAML configuration](../../examples/llm/openai_chroma_rag.yaml) that sets up two essential flows:
- **Data ingestion into a vector database** using Solace topics, embedding the data into **ChromaDB**.
- **Querying the ingested data** using **RAG**, where queries are sent to OpenAI for intelligent completion and response generation.

## Key Concepts Behind the Configuration

Before diving into the configuration, let’s explore the key concepts that power this setup.

### 1. Large Language Models (LLMs)
LLMs are AI models trained on vast amounts of textual data, capable of generating human-like text. They are used in various tasks like text generation, summarization, translation, and answering complex questions. Models such as OpenAI's GPT-4o or Anthropic's Claude 3.5 Sonnet are examples of LLMs. These models can generate meaningful responses based on the context they are provided, but they also have limitations, such as the risk of hallucinations (generating incorrect or fabricated facts).

### 2. Retrieval-Augmented Generation (RAG)
RAG is a framework that enhances the performance of LLMs by combining them with external knowledge retrieval. Instead of relying solely on the LLM’s internal knowledge, RAG retrieves relevant documents from an external database (such as ChromaDB) before generating a response. This approach enhances the accuracy of responses, as the generation process is “grounded” in factual information retrieved at the time of the query.

### 3. Embeddings
Embeddings are numerical representations of text that capture its semantic meaning. They are crucial for many NLP tasks, as they allow models to measure similarity between different pieces of text. In the context of RAG, embedding models (such as **OpenAI Embeddings**) convert input data into vector representations that can be stored in a vector database like **ChromaDB**. When a query is issued, it is also converted into a vector, and similar documents can be retrieved based on their proximity in the vector space.

### 4. Solace PubSub+ Platform
Solace’s PubSub+ platform provides event-driven messaging and streaming services, enabling applications to publish and subscribe to topics in real-time. In the context of AI applications, Solace acts as the message broker that facilitates the flow of data between different components (e.g., input data, queries, and responses).

## Real-Time Data Consumption with Solace AI Connector

One of the standout features of the Solace AI Connector is its ability to seamlessly handle real-time data. As data passes through the Solace broker, it can be consumed, embedded, and stored for future retrieval and analysis.

### Real-Time Data Embedding and Storage Flow

Using Solace topics, the connector can subscribe to real-time data streams. This data is processed in near real-time, where each message is embedded using an embedding model like **OpenAI Embeddings**. These embeddings are then stored in vector database like **ChromaDB** making them retrievable for future queries.

For example, imagine a system that ingests live customer support chat messages. As each message is published to the Solace broker, the system embeds the message, stores the vector in a database, and makes it available for retrieval during future interactions or analyses. This architecture is particularly useful for applications that need to build dynamic, up-to-date knowledge bases based on streaming data.

By leveraging the real-time messaging capabilities of Solace, the system ensures that data is continuously processed and stored in a structured, retrievable way, allowing for efficient and scalable AI-driven applications.

## YAML Configuration Breakdown

Let’s break down the YAML configuration provided in the example, which demonstrates how to implement RAG with Solace AI Connector and ChromaDB.

### Logging Configuration
```yaml
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: solace_ai_connector.log
```
This section sets the logging level for the connector, ensuring that logs are captured both to the console and to a file.

### Shared Configuration for Solace Broker
```yaml
shared_config:
  - broker_config: &broker_connection
      broker_type: solace
      broker_url: ${SOLACE_BROKER_URL}
      broker_username: ${SOLACE_BROKER_USERNAME}
      broker_password: ${SOLACE_BROKER_PASSWORD}
      broker_vpn: ${SOLACE_BROKER_VPN}
```
Here, we define the connection settings for the Solace broker. These environment variables (`SOLACE_BROKER_URL`, etc.) are essential for establishing communication with the Solace messaging infrastructure. Shared configs can be reused throughout the configuration to maintain consistency. In this example, we're using it for the input and output Solace broker connections.

### Data Ingestion to ChromaDB (Embedding Flow)

This flow ingests data into **ChromaDB**, which is a vector database that will store embeddings of the input text. You could have used any other vector database, but for this example, we are using ChromaDB.

#### 1. Solace Data Input Component
```yaml
- component_name: solace_data_input
  component_module: broker_input
  component_config:
    <<: *broker_connection
    broker_queue_name: demo_rag_data
    broker_subscriptions:
      - topic: demo/rag/data
      qos: 1
    payload_encoding: utf-8
    payload_format: json
```
This component listens to the **Solace topic** `demo/rag/data` for incoming data that needs to be embedded. It subscribes to the topic and expects the payload in JSON format with UTF-8 encoding. This is could be the real-time data stream that you want to process and embed.

#### 2. Embedding and Storage in ChromaDB
```yaml
- component_name: chroma_embed
  component_module: langchain_vector_store_embedding_index
  component_config:
    vector_store_component_path: langchain_chroma
    vector_store_component_name: Chroma
    vector_store_component_config:
      persist_directory: ./chroma_data
      collection_name: rag
    embedding_component_path: langchain_openai
    embedding_component_name: OpenAIEmbeddings
    embedding_component_config:
      api_key: ${OPENAI_API_KEY}
      base_url: ${OPENAI_API_ENDPOINT}
      model: ${OPENAI_EMBEDDING_MODEL_NAME}
  input_transforms:
    - type: copy
      source_value: topic:demo/rag/data
      dest_expression: user_data.vector_input:metadatas.source
    - type: copy
      source_expression: input.payload:texts
      dest_expression: user_data.vector_input:texts
  input_selection:
    source_expression: user_data.vector_input
```
This component uses `langchain_vector_store_embedding_index` to handle embedding logic which is a built-in component for adding and deleting embeddings to a vector database. It takes the input texts, converts them into embeddings using the OpenAI embedding model, and stores the embeddings in **ChromaDB**. ChromaDB is set to persist data in the `./chroma_data` directory.

The data from the solace input broker is first transformed into the shape that we expect in `input_transforms`. The `input_selection` section then selects the transformed data to be used as input for the embedding process.


### RAG Inference Flow (Query and Response)

This flow handles the **Retrieval-Augmented Generation (RAG)** process where a query is sent, relevant documents are retrieved, and a response is generated using OpenAI's models.

#### 1. Query Ingestion from Solace Topic
```yaml
- component_name: solace_completion_broker
  component_module: broker_input
  component_config:
    <<: *broker_connection
    broker_queue_name: demo_rag_query
    broker_subscriptions:
      - topic: demo/rag/query
```
This component listens for queries on the `demo/rag/query` Solace topic. The query is received as JSON data, and the Solace broker delivers it to the next step.

#### 2. ChromaDB Search for Relevant Documents
```yaml
- component_name: chroma_search
  component_module: langchain_vector_store_embedding_search
  component_config:
    vector_store_component_path: langchain_chroma
    vector_store_component_name: Chroma
    vector_store_component_config:
      persist_directory: ./chroma_data
      collection_name: rag
    max_results: 5
```
This component searches ChromaDB for documents that are most similar to the query using the built-in `langchain_vector_store_embedding_search` component. It retrieves the top 5 results based on proximity in the vector space.

#### 3. Response Generation Using OpenAI
```yaml
- component_name: llm_request
  component_module: openai_chat_model
  component_config:
      api_key: ${OPENAI_API_KEY}
      base_url: ${OPENAI_API_ENDPOINT}
      model: ${OPENAI_MODEL_NAME}
      temperature: 0.01
    input_transforms:
      # Extract and format the retrieved data
      - type: map
        source_list_expression: previous:result
        source_expression: |
          template:{{text://item:text}}\n\n
        dest_list_expression: user_data.retrieved_data

      - type: copy
        source_expression: |
          template:You are a helpful AI assistant. Using the provided context, help with the user's request below. Refrain to use any knowledge outside from the provided context. If the user query can not be answered using the provided context, reject user's query.

          <context>
          {{text://user_data.retrieved_data}}
          </context>
          
          <user-question>
          {{text://input.payload:query}}
          </user-question>
        dest_expression: user_data.llm_input:messages.0.content
      - type: copy
        source_expression: static:user
        dest_expression: user_data.llm_input:messages.0.role
    input_selection:
      source_expression: user_data.llm_input
```
Once relevant documents are retrieved, we build the prompt with retrieved context. To prevent the model from hallucination, we ask it to refuse to answer if the answer is not provided in the given context. Then the **LLM (e.g., GPT-4o)** is used to generate a response. The temperature is set to `0.01`, meaning the response will be deterministic and focused on factual accuracy. The retrieved documents provide context for the LLM, which then generates a response based solely on this context.

#### 4. Sending the Response Back to Solace


```yaml
- component_name: send_response
  component_module: broker_output
  component_config:
    <<: *broker_connection
    payload_encoding: utf-8
    payload_format: json
```
The final component sends the generated response back to the Solace broker, specifically to the topic `demo/rag/query/response`, where the response can be consumed by the requesting application.

## Flexibility in Components

One of the key strengths of this architecture is its flexibility. Components like the **OpenAI connector** or **ChromaDB** can easily be swapped out for other AI service providers or vector databases. For example:
- Instead of OpenAI, you can use another LLM provider like **Cohere** or **Anthropic**.
- Instead of **ChromaDB**, you could use a different vector database like **Pinecone**, **Weaviate**, or **Milvus**.

This modularity allows developers to adapt the system to different business requirements, AI services, and database solutions, providing greater flexibility and scalability.

## Conclusion

The Solace AI Connector, when combined with technologies like RAG, LLMs, and embeddings, enables a powerful AI-driven ecosystem for real-time applications. By ingesting data, embedding it into vector databases, and performing retrieval-augmented generation with LLMs, developers can build applications that provide accurate, context-aware responses to user queries fast.

This YAML configuration serves as a template for setting up such an application, you can find the complete example in the [examples directory](../../examples/llm/openai_chroma_rag.yaml). 

## Want to Learn More About Solace AI Connector?

Check out the [Solace AI Connector Overview](../overview.md) to explore its features in depth, or dive right in by following the [Getting Started Guide](../getting_started.md) to begin working with Solace AI Connector today!