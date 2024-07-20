from pathlib import Path
import logging as lg
from typing import List, Dict, Callable, cast
from dataclasses import dataclass
import ast

import click

from semu.pysemu.flatten import flatten
import semu.pysemu.stdlib as std


REGISTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
NUMBER_OF_REGISTERS = len(REGISTERS)


class Element:
    def emit(self) -> List[str]:
        raise NotImplementedError()


class Expression(Element):
    pass


@dataclass
class CallStdLib(Expression):
    what: Callable[[], str]

    def emit(self) -> List[str]:
        return [self.what()]


@dataclass
class Function:
    name: str
    args: List[str]
    body: List[Expression]

    def _emit_args(self, inx: int):
        arg = self.args[inx]
        reg = REGISTERS[inx]

        return [
            f'// {arg}',
            f'push {reg}'
        ]

    def emit(self) -> List[str]:
        return flatten([
            f'// function {self.name}',
            [self._emit_args(i) for i in range(len(self.args))],
            [expr.emit() for expr in self.body]
        ])


def uint32arg(ast_arg: ast.AST):
    if isinstance(ast_arg, ast.Constant) and isinstance(ast_arg.value, int):
        value = ast_arg.value

        if value < 0 or value > 0xFFFFFFFF:
            raise UserWarning(f'Int argument {ast_arg} out of range')

        return value
    else:
        raise UserWarning(f'Unsupported int argument {ast_arg}')


STD_LIB_CALLS = {
    'checkpoint': (std.checkpoint, [uint32arg])
}


class BaseTranslator:
    pass


class BodyTranslator(BaseTranslator):
    def __init__(self, parent: BaseTranslator):
        self.parent = parent

    def translate_std_call(self, std_name: str, ast_args: List[ast.expr]):
        if std_name not in STD_LIB_CALLS:
            raise UserWarning(f'Unknown stdlib call {std_name}')

        std_func, std_args = STD_LIB_CALLS[std_name]

        if len(ast_args) != len(std_args):
            raise UserWarning(f'Wrong number of arguments for {std_name}')

        args = [translator(ast_arg) for (ast_arg, translator) in zip(ast_args, std_args)]
        return CallStdLib(lambda: std_func(*args))   # type: ignore

    def translate_call(self, ast_call: ast.Call):
        ast_name = ast_call.func

        if not isinstance(ast_name, ast.Attribute):
            raise UserWarning(f'Unsupported call {ast_call} {ast_name}')

        ast_name_name = cast(ast.Name, ast_name.value)

        if ast_name_name.id == 'stdlib':
            return self.translate_std_call(ast_name.attr, ast_call.args)
        else:
            raise UserWarning(f'Unsupported call {ast_call} {ast_name}')

    def translate_expr(self, ast_expr: ast.Expr):
        if isinstance(ast_expr.value, ast.Call):
            return self.translate_call(ast_expr.value)

        raise UserWarning(f'Unsupported expression {ast_expr}')

    def translate(self, ast_body: List[ast.stmt]) -> List[Expression]:
        def body_el(ast_element: ast.stmt):
            if isinstance(ast_element, ast.Expr):
                return self.translate_expr(ast_element)
            else:
                raise UserWarning(f'Unsupported element {ast_element}')

        return list(map(body_el, ast_body))


class FunctionTranslator(BaseTranslator):
    def __init__(self, parent: BaseTranslator):
        self.parent = parent

    def translate(self, ast_function: ast.FunctionDef) -> Function:
        name = ast_function.name
        lg.debug(f'Function {name} found')

        if len(ast_function.args.args) > NUMBER_OF_REGISTERS:
            raise UserWarning(f'Function {name} has too many arguments')

        def make_arg(ast_arg: ast.arg):
            return ast_arg.arg

        args = [make_arg(ast_arg) for ast_arg in ast_function.args.args]
        body = BodyTranslator(self).translate(ast_function.body)
        return Function(name, args, body)


class Translator(BaseTranslator):
    def __init__(self):
        self.functions: Dict[str, Function] = dict()

    def translate_source(self, input: str):
        ast_tree = ast.parse(input)
        result: List[str] = []

        for ast_element in ast_tree.body:
            if isinstance(ast_element, ast.FunctionDef):
                function = FunctionTranslator(self).translate(ast_element)
                self.functions[function.name] = function

        for function in self.functions.values():
            result.extend(function.emit())

        result.append('hlt')

        return '\n'.join(result)


@click.command()
@click.option('-v', '--verbose', is_flag=True, help='sets logging level to debug')
@click.argument('input', type=Path)
@click.argument('output', type=Path)
def translate(verbose: bool, input: Path, output: Path):
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO)
    lg.info(f'Translating {input} to {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(Translator().translate_source(input.read_text()))


if __name__ == '__main__':
    translate()
