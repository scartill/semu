from pathlib import Path
import logging as lg
from typing import List, Dict, cast
from dataclasses import dataclass
import ast

import click

from semu.pysemu.flatten import flatten


REGISTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
NUMBER_OF_REGISTERS = len(REGISTERS)


class Expression:
    def emit(self) -> List[str]:
        raise NotImplementedError()


class VoidElement(Expression):
    def emit(self):
        return ['nop']


@dataclass
class Checkpoint(Expression):
    arg: int

    def emit(self) -> List[str]:
        return [f'.check {self.arg}']


@dataclass
class Function(Expression):
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


@dataclass
class Module:
    functions: Dict[str, Function]
    body: List[Expression]

    def emit(self):
        result: List[str] = []

        for function in self.functions.values():
            result.extend(function.emit())

        for expr in self.body:
            result.extend(expr.emit())

        result.append('hlt')
        return result


def uint32const(ast_arg: ast.AST):
    if isinstance(ast_arg, ast.Constant) and isinstance(ast_arg.value, int):
        value = ast_arg.value

        if value < 0 or value > 0xFFFFFFFF:
            raise UserWarning(f'Int argument {ast_arg} out of range')

        return value
    else:
        raise UserWarning(f'Unsupported const int argument {ast_arg}')


def std_checkpoint(ast_args: List[ast.expr]):
    if len(ast_args) != 1:
        raise UserWarning(f'checkpoint expects 1 argument, got {len(ast_args)}')

    arg = uint32const(ast_args[0])
    return Checkpoint(arg)


STD_LIB_CALLS = {
    'checkpoint': std_checkpoint
}


class Translator:
    def __init__(self):
        self.functions: Dict[str, Function] = dict()

    def translate_std_call(self, std_name: str, ast_args: List[ast.expr]):
        if std_name not in STD_LIB_CALLS:
            raise UserWarning(f'Unknown stdlib call {std_name}')

        return STD_LIB_CALLS[std_name](ast_args)

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

    def translate_stmt(self, ast_element: ast.stmt):
        if isinstance(ast_element, ast.Expr):
            return self.translate_expr(ast_element)
        elif isinstance(ast_element, ast.Pass):
            return VoidElement()
        else:
            lg.warning(f'Unsupported element {ast_element}')
            return VoidElement()

    def translate_body(self, ast_body: List[ast.stmt]) -> List[Expression]:
        return list(map(self.translate_stmt, ast_body))

    def translate_function(self, ast_function: ast.FunctionDef) -> Function:
        name = ast_function.name
        lg.debug(f'Function {name} found')

        if len(ast_function.args.args) > NUMBER_OF_REGISTERS:
            raise UserWarning(f'Function {name} has too many arguments')

        def make_arg(ast_arg: ast.arg):
            return ast_arg.arg

        args = [make_arg(ast_arg) for ast_arg in ast_function.args.args]
        body = self.translate_body(ast_function.body)
        return Function(name, args, body)

    def translate_module(self, ast_module: ast.Module):
        ast_module_body: List[ast.stmt] = []

        for ast_element in ast_module.body:
            if isinstance(ast_element, ast.FunctionDef):
                function = self.translate_function(ast_element)
                self.functions[function.name] = function
            else:
                ast_module_body.append(ast_element)

        global_body = self.translate_body(ast_module_body)
        return Module(self.functions, global_body)


def translate_string(input: str):
    ast_module = ast.parse(input)
    module = Translator().translate_module(ast_module)
    result = module.emit()
    return '\n'.join(result)


@click.command()
@click.option('-v', '--verbose', is_flag=True, help='sets logging level to debug')
@click.argument('input', type=Path)
@click.argument('output', type=Path)
def translate(verbose: bool, input: Path, output: Path):
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO)
    lg.info(f'Translating {input} to {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(translate_string(input.read_text()))


if __name__ == '__main__':
    translate()
