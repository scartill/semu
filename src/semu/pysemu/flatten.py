# type: ignore
from typing import Sequence, Any

DeepList = Sequence[Any]


def flatten(deeplist: DeepList) -> Sequence[Any]:
    def _flatten(lst):
        for el in lst:
            if isinstance(el, list):
                yield from flatten(el)
            else:
                yield el

    return list(_flatten(deeplist))
