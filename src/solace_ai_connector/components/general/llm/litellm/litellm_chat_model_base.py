"""LiteLLM chat model component"""

import logging
import uuid
import time
from litellm import cost_per_token
from litellm import APIConnectionError
from .litellm_base import LiteLLMBase
from .litellm_base import litellm_info_base
from .....common.message import Message
from .....common.monitoring import Metrics
from .....common.observability import (
    MonitorLatency,
    GenAIMonitor,
    GenAITTFTMonitor,
    GenAITokenMonitor,
    GenAICostMonitor
)
from .....common.observability.registry import MetricRegistry

log = logging.getLogger(__name__)

litellm_chat_info_base = litellm_info_base.copy()
litellm_chat_info_base.update(
    {
        "class_name": "LiteLLMChatModelBase",
        "description": "LiteLLM chat model base component",
        "input_schema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {
                                "type": "string",
                                "enum": ["system", "user", "assistant"],
                            },
                            "content": {"type": "string"},
                        },
                        "required": ["role", "content"],
                    },
                },
                "stream": {
                    "type": "boolean",
                    "description": "Whether to stream the response - overwrites llm_mode",
                },
            },
            "required": ["messages"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The generated response from the model",
                },
                "chunk": {
                    "type": "string",
                    "description": "The current chunk of the response",
                },
                "response_uuid": {
                    "type": "string",
                    "description": "The UUID of the response",
                },
                "first_chunk": {
                    "type": "boolean",
                    "description": "Whether this is the first chunk of the response",
                },
                "last_chunk": {
                    "type": "boolean",
                    "description": "Whether this is the last chunk of the response",
                },
                "streaming": {
                    "type": "boolean",
                    "description": "Whether this is a streaming response",
                },
            },
            "required": ["content"],
        },
    },
)
litellm_chat_info_base["config_parameters"].extend(
    [
        {
            "name": "stream_to_flow",
            "required": False,
            "description": (
                "Name the flow to stream the output to - this must be configured for "
                "llm_mode='stream'. This is mutually exclusive with stream_to_next_component."
            ),
            "default": "",
        },
        {
            "name": "stream_to_next_component",
            "required": False,
            "description": (
                "Whether to stream the output to the next component in the flow. "
                "This is mutually exclusive with stream_to_flow."
            ),
            "default": False,
        },
        {
            "name": "llm_mode",
            "required": False,
            "description": (
                "The mode for streaming results: 'none' or 'stream'. 'stream' "
                "will just stream the results to the named flow. 'none' will "
                "wait for the full response."
            ),
            "default": "none",
        },
        {
            "name": "stream_batch_size",
            "required": False,
            "description": "The minimum number of words in a single streaming result. Default: 15.",
            "default": 15,
        },
    ]
)


class LiteLLMChatModelBase(LiteLLMBase):

    def __init__(self, info, **kwargs):
        super().__init__(info, **kwargs)
        self.stream_to_flow = self.get_config("stream_to_flow")
        self.stream_to_next_component = self.get_config("stream_to_next_component")
        self.llm_mode = self.get_config("llm_mode")
        self.stream_batch_size = self.get_config("stream_batch_size")

        if self.stream_to_flow and self.stream_to_next_component:
            raise ValueError(
                "stream_to_flow and stream_to_next_component are mutually exclusive. Please set only one of these options"
            )

    def invoke(self, message, data):
        """invoke the model"""
        messages = data.get("messages", [])
        stream = data.get("stream", self.llm_mode == "stream")

        if stream:
            return self.invoke_stream(message, messages)
        else:
            return self.invoke_non_stream(messages)

    def invoke_non_stream(self, messages):
        """invoke the model without streaming"""
        # Get model name for observability
        model_name = self.load_balancer_config[0]["model_name"]

        # Create monitor instance
        monitor = GenAIMonitor.create(model=model_name)

        # Track start time for backward compatibility
        start_time = time.perf_counter()

        try:
            # Track: gen_ai.client.operation.duration
            with MonitorLatency(monitor):
                response = self.load_balance(messages, stream=False)

                # Extract token usage from API response (ground truth)
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens

                # Update histogram label with actual prompt_tokens via typed method
                monitor.set_prompt_tokens(prompt_tokens)

            # Record token and cost counters
            self._record_token_and_cost_metrics(
                model_name,
                prompt_tokens,
                completion_tokens
            )

            # Calculate elapsed time for backward compatibility
            processing_time = round(time.perf_counter() - start_time, 3)
            self.send_metrics(
                prompt_tokens,
                completion_tokens,
                total_tokens,
                processing_time,
            )
            return {"content": response.choices[0].message.content}
        except APIConnectionError as e:
            error_str = str(e)
            log.exception("Error invoking LiteLLM")
            return {"content": error_str, "handle_error": True}
        except Exception:
            log.exception("Error invoking LiteLLM")
            raise

    def invoke_stream(self, message, messages):
        """invoke the model with streaming"""
        response_uuid = str(uuid.uuid4())
        if self.set_response_uuid_in_user_properties:
            message.set_data("input.user_properties:response_uuid", response_uuid)

        aggregate_result = ""
        current_batch = ""
        first_chunk = True

        # Get model name for observability
        model_name = self.load_balancer_config[0]["model_name"]
        gen_ai_monitor = GenAIMonitor.create(model=model_name)

        ttft_latency = MonitorLatency(GenAITTFTMonitor.create(model=model_name))
        ttft_recorded = False

        # Keep original timing for backward compatibility        
        start_time = time.time()
        try:
            # Track: gen_ai.client.operation.duration (for streaming)
            with MonitorLatency(gen_ai_monitor):
                ttft_latency.start()
                response = self.load_balance(messages, stream=True)

                for chunk in response:
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content

                        # Record TTFT on first content token
                        if not ttft_recorded:
                            ttft_latency.stop()  # Records gen_ai.client.operation.ttft.duration with error.type='none'
                            ttft_recorded = True

                        aggregate_result += content
                        current_batch += content
                        if len(current_batch.split()) >= self.stream_batch_size:
                            if self.stream_to_flow:
                                self.send_streaming_message(
                                    message,
                                    current_batch,
                                    aggregate_result,
                                    response_uuid,
                                    first_chunk,
                                    False,
                                )
                            elif self.stream_to_next_component:
                                self.send_to_next_component(
                                    message,
                                    current_batch,
                                    aggregate_result,
                                    response_uuid,
                                    first_chunk,
                                    False,
                                )
                            current_batch = ""
                            first_chunk = False
                    if hasattr(chunk, "usage"):
                        end_time = time.time()
                        processing_time = round(end_time - start_time, 3)

                        # Extract token usage details
                        prompt_tokens = chunk.usage.prompt_tokens
                        completion_tokens = chunk.usage.completion_tokens
                        total_tokens = chunk.usage.total_tokens

                        # update token labels
                        gen_ai_monitor.set_prompt_tokens(prompt_tokens)

                        # Record token and cost counters
                        self._record_token_and_cost_metrics(
                            model_name,
                            prompt_tokens,
                            completion_tokens
                        )

                        # Keep old monitoring for backward compatibility
                        self.send_metrics(
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                            processing_time,
                        )

        except APIConnectionError as e:
            if not ttft_recorded:
                # Record TTFT with error if first token never arrived
                ttft_latency.error(e)

            error_str = str(e)
            log.exception("Error invoking LiteLLM")
            return {
                "content": error_str,
                "response_uuid": response_uuid,
                "handle_error": True,
            }
        except Exception as e:
            if not ttft_recorded:
                # Record TTFT with error if first token never arrived
                ttft_latency.error(e)

            log.exception("Error invoking LiteLLM")
            raise

        if self.stream_to_next_component:
            # Just return the last chunk
            return {
                "content": aggregate_result,
                "chunk": current_batch,
                "response_uuid": response_uuid,
                "first_chunk": first_chunk,
                "last_chunk": True,
                "streaming": True,
            }

        if self.stream_to_flow:
            self.send_streaming_message(
                message,
                current_batch,
                aggregate_result,
                response_uuid,
                first_chunk,
                True,
            )

        return {"content": aggregate_result, "response_uuid": response_uuid}

    def send_streaming_message(
        self,
        input_message,
        chunk,
        aggregate_result,
        response_uuid,
        first_chunk=False,
        last_chunk=False,
    ):
        message = Message(
            payload={
                "chunk": chunk,
                "content": aggregate_result,
                "response_uuid": response_uuid,
                "first_chunk": first_chunk,
                "last_chunk": last_chunk,
                "streaming": True,
            },
            user_properties=input_message.get_user_properties(),
        )
        self.send_to_flow(self.stream_to_flow, message)

    def send_to_next_component(
        self,
        input_message,
        chunk,
        aggregate_result,
        response_uuid,
        first_chunk=False,
        last_chunk=False,
    ):
        message = Message(
            payload={
                "chunk": chunk,
                "content": aggregate_result,
                "response_uuid": response_uuid,
                "first_chunk": first_chunk,
                "last_chunk": last_chunk,
                "streaming": True,
            },
            user_properties=input_message.get_user_properties(),
        )

        result = {
            "chunk": chunk,
            "content": aggregate_result,
            "response_uuid": response_uuid,
            "first_chunk": first_chunk,
            "last_chunk": last_chunk,
            "streaming": True,
        }

        self.process_post_invoke(result, message)

    def send_metrics(
        self, prompt_tokens, completion_tokens, total_tokens, processing_time
    ):
        """
        Sends metrics related to the LLM's performance.

        Args:
            prompt_tokens (int): Number of tokens in the prompt.
            completion_tokens (int): Number of tokens in the completion.
            total_tokens (int): Total number of tokens (prompt + completion).
            processing_time (float): Time taken to process the request.
        """
        prompt_tokens_cost_usd_dollar, completion_tokens_cost_usd_dollar = (
            cost_per_token(
                model=self.load_balancer_config[0]["model_name"],
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        )
        cost = prompt_tokens_cost_usd_dollar + completion_tokens_cost_usd_dollar
        current_time = int(time.time())
        with self._lock_stats:
            self.stats[Metrics.LITELLM_STATS_PROMPT_TOKENS].append(
                {
                    "value": prompt_tokens,
                    "timestamp": current_time,
                }
            )
            self.stats[Metrics.LITELLM_STATS_RESPONSE_TOKENS].append(
                {
                    "value": completion_tokens,
                    "timestamp": current_time,
                }
            )
            self.stats[Metrics.LITELLM_STATS_TOTAL_TOKENS].append(
                {
                    "value": total_tokens,
                    "timestamp": current_time,
                }
            )
            self.stats[Metrics.LITELLM_STATS_RESPONSE_TIME].append(
                {
                    "value": processing_time,
                    "timestamp": current_time,
                }
            )
            self.stats[Metrics.LITELLM_STATS_COST].append(
                {
                    "value": cost,
                    "timestamp": current_time,
                }
            )
        log.debug(
            "Completion tokens: %s, Prompt tokens: %s, Total tokens: %s, Cost: %s",
            completion_tokens,
            prompt_tokens,
            total_tokens,
            cost,
        )

    def _record_token_and_cost_metrics(
        self, model_name: str, prompt_tokens: int, completion_tokens: int
    ):
        """
        Record token usage and cost counters to observability system.

        Private method to avoid code duplication between streaming and non-streaming modes.

        Args:
            model_name: LLM model name
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
        """
        try:
            # Get component and owner identifiers
            # For connector flows: component.name = flow_name (or instance_name as fallback)
            # owner.id = user_properties.userId if available, otherwise "none"
            component_name = self.flow_name or self.instance_name
            owner_id = "none"
            if self.current_message:
                user_properties = self.current_message.get_user_properties()
                if user_properties:
                    owner_id = user_properties.get("userId", "none")

            # Get registry
            registry = MetricRegistry.get_instance()

            # Record input tokens
            input_monitor = GenAITokenMonitor.create(
                model=model_name,
                component_name=component_name,
                owner_id=owner_id,
                token_type="input"
            )
            registry.record_counter_from_monitor(input_monitor, prompt_tokens)

            # Record output tokens
            output_monitor = GenAITokenMonitor.create(
                model=model_name,
                component_name=component_name,
                owner_id=owner_id,
                token_type="output"
            )
            registry.record_counter_from_monitor(output_monitor, completion_tokens)

            # Calculate and record cost
            prompt_cost, completion_cost = cost_per_token(
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens
            )
            total_cost = prompt_cost + completion_cost

            cost_monitor = GenAICostMonitor.create(
                model=model_name,
                component_name=component_name,
                owner_id=owner_id
            )
            registry.record_counter_from_monitor(cost_monitor, total_cost)

        except Exception as e:
            # Don't fail LLM calls if observability fails
            log.warning(f"Failed to record token/cost metrics: {e}")
