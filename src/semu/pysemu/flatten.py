# type: ignore
from typing import List, Any

DeepList = List[Any]


def flatten(deeplist: DeepList) -> List[Any]:
    def _flatten(lst):
        for el in lst:
            if isinstance(el, list):
                yield from flatten(el)
            else:
                yield el

    return list(_flatten(deeplist))
