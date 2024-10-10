# Getting Started

This guide will help you get started with the Solace AI Event Connector.

## Prerequisites

- Python 3.10 or later
- A Solace PubSub+ event broker
- A chat model to connect to (optional)

## Setting up a Solace PubSub+ Event Broker

To get started with creating a solace PubSub+ event broker follow the instructions on [Try PubSub+ Event Brokers](https://docs.solace.com/Get-Started/Getting-Started-Try-Broker.htm) page.

## Running With PyPi

### Install the connector

(Optional) Create a virtual environment:

```sh
python3 -m venv env
source env/bin/activate
```

Set up the connector package
```sh
pip install solace-ai-connector
```

### Run a 'pass-through' example

Download an example configuration file:

```sh
curl https://raw.githubusercontent.com/SolaceLabs/solace-ai-connector/main/config.yaml > config.yaml
```

Set the environment variables that the config file needs. In this example:

```sh
export SOLACE_BROKER_URL=tcp://<hostname>:<port>
export SOLACE_BROKER_USERNAME=<username>
export SOLACE_BROKER_PASSWORD=<password>
export SOLACE_BROKER_VPN=<vpn>
```

If running the local version of the broker with default values, the environment variables would be:

```sh
export SOLACE_BROKER_URL=ws://localhost:8008
export SOLACE_BROKER_USERNAME=default
export SOLACE_BROKER_PASSWORD=default
export SOLACE_BROKER_VPN=default
```

(Optional) Store the environment variables permanently in ~/.profile file and activate them by:

```sh
source ~/.profile
```

Run the connector:

```sh
solace-ai-connector config.yaml
```

This very basic connector simply creates a queue on the broker called `my_queue` and adds the subscription `my/topic1` to it. 
Any events published to the broker with a topic `my/topic1` will be delivered to the connector and then sent back to the 
broker on the topic `response/my/topic1`.

To test this, connect to the Solace Broker's browser management UI and select the "Try Me!". Subscribe to "my/>" and "response/>".
Publish a message with the topic `my/topic1` and you should see both the request and the reply message in the received messages
area in the Subscriber side of the "Try me!" page.

### Run an OpenAI example

Download the OpenAI connector example configuration file:

```sh
curl https://raw.githubusercontent.com/SolaceLabs/solace-ai-connector/refs/heads/main/examples/llm/langchain_openai_with_history_chat.yaml > langchain_openai_with_history_chat.yaml
```

For this one, you need to also define the following additional environment variables:

```sh
export OPENAI_API_KEY=<your OpenAI key>
export OPENAI_API_ENDPOINT=<base url of your OpenAI endpoint>
export MODEL_NAME=<model name>
```

Note that if you want to use the default OpenAI endpoint, just delete that line from the langchain_openai_with_history_chat.yaml file.

Install the langchain openai dependencies:
```sh
pip install langchain_openai openai 
```

Run the connector:

```sh
solace-ai-connector langchain_openai_with_history_chat.yaml
```

Use the "Try Me!" function on the broker's browser UI (or some other means) to publish an event like this:

Topic: `demo/joke/subject`

Payload: 
```json
{
  "joke": {
    "subject": "<subject for the joke>"
  }
}
```

In the "Try Me!" also subscribe to `demo/joke/subject/response` to see the response


## Running From Source Code


1. Clone the repository and enter its directory:

    ```sh
    git clone git@github.com:SolaceLabs/solace-ai-connector.git
    cd solace-ai-connector
    ```
    
2. (Optional) Create a virtual environment:

    ```sh
    python -m venv .venv
    source .venv/bin/activate
    ```

3. Install the required Python packages:

    ```sh
    pip install -r requirements.txt
    ```

### Configuration

1. (Optional) Edit the example configuration file at the root of the repository:

    ```sh
    config.yaml
    ```

2. Set up the environment variables that you need for the config.yaml file. The default one requires the following variables:

    ```sh
    export SOLACE_BROKER_URL=tcp://<hostname>:<port>
    export SOLACE_BROKER_USERNAME=<username>
    export SOLACE_BROKER_PASSWORD=<password>
    export SOLACE_BROKER_VPN=<vpn>
    ```


### Running the AI Event Connector

1. Start the AI Event Connector:

    ```sh
    cd src
    python3 -m solace_ai_connector.main ../config.yaml
    ```

2. Use the Solace PubSub+ event broker "Try Me" function to send a message to the AI Event Connector. Make sure that the topic matches the subscription in the configuration file.

3. The AI Event Connector will send the message to the chat model and return the response to the Solace PubSub+ event broker.


# Building a Docker Image

To build a Docker image, run the following command:

```sh
make build
```

---

Checkout [configuration](configuration.md) or [overview](overview.md) next