# Getting Started

This guide will help you get started with the Solace AI Event Connector.

## Prerequisites

- Python 3.6 or later
- A Solace PubSub+ event broker
- A chat model to connect to (optional)

## Installation

1. Clone the repository and enter its directory:

    ```sh
    git clone git@github.com:SolaceLabs/solace-ai-connector.git
    cd solace-ai-connector
    ```
    
2. Optionally create a virtual environment:

    ```sh
    python -m venv .venv
    source .venv/bin/activate
    ```

3. Install the required Python packages:

    ```sh
    pip install -r requirements.txt
    ```

## Configuration

1. Edit the example configuration file at the root of the repository:

    config.yaml

2. Create a .env file. You can use the example file as a template:

    ```sh
    cp .env_template .env
    ```
    
3. Edit the .env file to set the environment variables.

## Running the AI Event Connector

1. Start the AI Event Connector:

    ```sh
    python ai_event_connector.py config.yaml
    ```

2. Use the Solace PubSub+ event broker "Try Me" function to send a message to the AI Event Connector. Make sure that the topic matches the subscription in the configuration file.

3. The AI Event Connector will send the message to the chat model and return the response to the Solace PubSub+ event broker.


# Building a Docker Image

To build a Docker image, run the following command:

```sh
make build
```

Please now visit the [Documentation Page](index.md) for more information
