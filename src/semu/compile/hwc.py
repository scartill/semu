import semu.common.hwconf as hw
from semu.compile.compiler import CompilationItem


def configure_param(param: str) -> str:
    value = hw.__dict__[param]
    return f'CONST {param} {value}'


def generate_compilation_item() -> CompilationItem:
    item = CompilationItem()
    item.namespace = 'hw'

    item.contents = '\n'.join([
        configure_param('INT_VECT_BASE'),
        configure_param('SERIAL_MM_BASE'),
        configure_param('LOOPBACK_LINE'),
        configure_param('SYSTIMER_LINE'),
        configure_param('SERIAL_LINE'),
    ])

    return item
