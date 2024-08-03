from dataclasses import dataclass

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Expression
import semu.pseudopython.namespaces as ns


@dataclass
class FunctionCall(Expression):
    func: ns.Function

    def emit(self) -> ns.Sequence[str]:
        address = self._get_temp([self.target])

        return flatten([
            f'// Call {self.func.name}',
            f'push {address}',
            f'ldr &{self.func.label_name()} {address}',
            f'cll {address}',
            f'pop {address}',
            f'// End call {self.func.name}'
        ])
