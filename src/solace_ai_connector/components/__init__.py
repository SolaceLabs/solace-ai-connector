# Consolidate all components in one place

from .inputs_outputs import (
    error_input,
    timer_input,
    broker_input,
    broker_output,
    stdout_output,
    stdin_input,
)

from .general import (
    user_processor,
    aggregate,
    pass_through,
    delay,
    iterate,
    message_filter,
)

from .general.for_testing import (
    need_ack_input,
    fail,
    give_ack_output,
    need_nack_input,
    give_nack_output,
)

from .general.websearch import (websearch_duckduckgo, websearch_google, websearch_bing)

# Also import the components from the submodules
from .inputs_outputs.error_input import ErrorInput
from .inputs_outputs.timer_input import TimerInput
from .inputs_outputs.broker_input import BrokerInput
from .inputs_outputs.broker_output import BrokerOutput
from .inputs_outputs.stdout_output import Stdout
from .inputs_outputs.stdin_input import Stdin
from .general.user_processor import UserProcessor
from .general.aggregate import Aggregate
from .general.for_testing.need_ack_input import NeedAckInput
from .general.for_testing.fail import Fail
from .general.for_testing.give_ack_output import GiveAckOutput
from .general.for_testing.need_nack_input import NeedNackInput
from .general.for_testing.give_nack_output import GiveNackOutput
from .general.pass_through import PassThrough
from .general.delay import Delay
from .general.iterate import Iterate
from .general.message_filter import MessageFilter
from .general.websearch.websearch_duckduckgo import WebSearchDuckDuckGo
from .general.websearch.websearch_google import WebSearchGoogle
from .general.websearch.websearch_bing import WebSearchBing
