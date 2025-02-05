# Built-in Components

| Component | Description |
| --- | --- |
| [aggregate](aggregate.md) | Aggregate messages into one message. |
| [assembly](assembly.md) | Assembles messages till criteria is met, the output will be the assembled message |
| [broker_input](broker_input.md) | Connect to a messaging broker and receive messages from it. The component will output the payload, topic, and user properties of the message. |
| [broker_output](broker_output.md) | Connect to a messaging broker and send messages to it. Note that this component requires that the data is transformed into the input schema. |
| [broker_request_response](broker_request_response.md) | Connect to a messaging broker, send request messages, and receive responses. This component combines the functionality of broker_input and broker_output with additional request-response handling. |
| [delay](delay.md) | A simple component that simply passes the input to the output, but with a configurable delay. |
| [error_input](error_input.md) | Receive processing errors from the Solace AI Event Connector. Note that the input_selection configuration is ignored. This component should be used to create a flow that handles errors from other flows.  |
| [file_output](file_output.md) | File output component |
| [iterate](iterate.md) | Take a single message that is a list and output each item in that list as a separate message |
| [langchain_chat_model](langchain_chat_model.md) | Provide access to all the LangChain chat models via configuration |
| [langchain_chat_model_with_history](langchain_chat_model_with_history.md) | A chat model based on LangChain that includes keeping per-session history of the conversation. Note that this component will only take the first system message and the first human message in the messages array. |
| [langchain_embeddings](langchain_embeddings.md) | Provide access to all the LangChain Text Embeddings components via configuration |
| [langchain_split_text](langchain_split_text.md) | Split a long text into smaller parts using the LangChain text splitter module |
| [langchain_vector_store_delete](langchain_vector_store_delete.md) | This component allows for entries in a LangChain Vector Store to be deleted. This is needed for the continued maintenance of the vector store. Due to the nature of langchain vector stores, you need to specify an embedding component even though it is not used in this component. |
| [langchain_vector_store_embedding_index](langchain_vector_store_embedding_index.md) | Use LangChain Vector Stores to index text for later semantic searches. This will take text, run it through an embedding model and then store it in a vector database. |
| [langchain_vector_store_embedding_search](langchain_vector_store_embedding_search.md) | Use LangChain Vector Stores to search a vector store with a semantic search. This will take text, run it through an embedding model with a query embedding and then find the closest matches in the store. |
| [litellm_chat_model](litellm_chat_model.md) | LiteLLM chat component |
| [litellm_chat_model_with_history](litellm_chat_model_with_history.md) | LiteLLM model handler component with conversation history |
| [litellm_embeddings](litellm_embeddings.md) | Embed text using a LiteLLM model |
| [message_filter](message_filter.md) | A filtering component. This will apply a user configurable expression. If the expression evaluates to True, the message will be passed on. If the expression evaluates to False, the message will be discarded. If the message is discarded, any previous components that require an acknowledgement will be acknowledged. |
| [mongo_base](mongo_base.md) | Base MongoDB database component |
| [mongo_insert](mongo_insert.md) | Inserts data into a MongoDB database. |
| [mongo_search](mongo_search.md) | Searches a MongoDB database. |
| [openai_chat_model](openai_chat_model.md) | OpenAI chat model component |
| [openai_chat_model_with_history](openai_chat_model_with_history.md) | OpenAI chat model component with conversation history |
| [parser](parser.md) | Parse input from the given type to output type. |
| [pass_through](pass_through.md) | What goes in comes out |
| [stdin_input](stdin_input.md) | STDIN input component. The component will prompt for input, which will then be placed in the message payload using the output schema below. The component will wait for its output message to be acknowledged before prompting for the next input. |
| [stdout_output](stdout_output.md) | STDOUT output component |
| [timer_input](timer_input.md) | An input that will generate a message at a specified interval. |
| [user_processor](user_processor.md) | A component that allows the processing stage to be defined in the configuration file. |
| [web_scraper](web_scraper.md) | Scrape javascript based websites. |
| [websearch_bing](websearch_bing.md) | Perform a search query on Bing. |
| [websearch_duckduckgo](websearch_duckduckgo.md) | Perform a search query on DuckDuckGo. |
| [websearch_google](websearch_google.md) | Perform a search query on Google. |
| [websocket_input](websocket_input.md) | Listen for incoming messages on a websocket connection. |
| [websocket_output](websocket_output.md) | Send messages to a websocket connection. |
