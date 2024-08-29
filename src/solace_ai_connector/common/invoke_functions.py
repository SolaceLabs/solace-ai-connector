"""Set of simple functions to take the place of operators in the config file"""

import uuid as uuid_module

add = lambda x, y: x + y
append = lambda x, y: x + [y]
subtract = lambda x, y: x - y
multiply = lambda x, y: x * y
divide = lambda x, y: x / y
modulus = lambda x, y: x % y
power = lambda x, y: x**y
equal = lambda x, y: x == y
not_equal = lambda x, y: x != y
greater_than = lambda x, y: x > y
less_than = lambda x, y: x < y
greater_than_or_equal = lambda x, y: x >= y
less_than_or_equal = lambda x, y: x <= y
and_op = lambda x, y: x and y
or_op = lambda x, y: x or y
not_op = lambda x: not x
in_op = lambda x, y: x in y
negate = lambda x: -x
empty_list = lambda: []
empty_dict = lambda: {}
empty_string = lambda: ""
empty_set = set
empty_tuple = tuple
empty_float = lambda: 0.0
empty_int = lambda: 0
if_else = lambda x, y, z: y if x else z
uuid = lambda: str(uuid_module.uuid4())

# A few test functions
def _test_positional_and_keyword_args(*args, **kwargs):
    return args, kwargs


def _test_positional_args(*args):
    return args


def _test_keyword_args(**kwargs):
    return kwargs
