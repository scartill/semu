import ast
from typing import List, cast
import logging as lg

import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.expressions as ex
import semu.pseudopython.builtins as bi
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls
import semu.pseudopython.classes as cls
import semu.pseudopython.arrays as arr
import semu.pseudopython.pointers as ptrs
import semu.pseudopython.helpers as h
import semu.pseudopython.factories as f


class ExpressionTranslator:
    context: ns.Namespace

    def __init__(self, context: ns.Namespace):
        self.context = context

    def tx_builtin_call(
        self, callable: bi.BuiltinInline, ast_args: List[ast.expr],
        target: regs.Register
    ):
        assert len(ast_args) <= len(regs.REGISTERS)
        args = []

        for i, ast_arg in enumerate(ast_args):
            args.append(self.tx_expression(ast_arg, regs.REGISTERS[i]))

        return f.create_inline(callable, args, target)

    def tx_call(self, ast_call: ast.Call, target: regs.Register):
        '''
            NB: First, we try built-in functions, then we try to resolve a physical value
        '''

        callable = self.tx_expression(ast_call.func)

        if isinstance(callable, bi.BuiltinInlineWrapper):
            lg.debug(f'Call: inline {callable.inline.name}')
            return self.tx_builtin_call(callable.inline, ast_call.args, target)

        args = [self.tx_phy_value(ast_arg) for ast_arg in ast_call.args]

        if isinstance(callable, cls.BoundMethodRef):
            lg.debug(f'Call: bound method {callable}')
            return f.make_bound_method_call(callable, args, target)

        if not isinstance(callable, ex.PhyExpression):
            raise UserWarning(
                f'Unsupported callable {callable} (not built-in, bound, or physical)'
            )

        # Stripping 'assignable', in required
        if isinstance(callable, ex.Assignable):
            callable = ptrs.Deref(callable, target)

        if isinstance(callable.pp_type, ptrs.FunctionPointerType):
            lg.debug(f'Call: direct {callable}')
            call = f.make_direct_call(callable, args, target)
            return f.create_call_frame(call, args)

        if isinstance(callable.pp_type, cls.MethodPointerType):
            # Autofind this
            if len(args) == len(callable.pp_type.arg_types) - 1:
                lg.debug(f'Call: method pointer {callable} (auto-this)')
                this_lookup = self.context.get_own_name('this')
                formal = this_lookup.known_name
                assert isinstance(formal, calls.FormalParameter)
                this = ptrs.Deref(ptrs.PointerToLocal(formal))
                bound_ref = cls.BoundMethodRef(this, callable)
                return f.make_bound_method_call(bound_ref, args, target)
            # Direct method binding
            else:
                lg.debug(f'Call: method pointer {callable} (direct)')
                if not isinstance(args[0].pp_type, cls.InstancePointerType):
                    raise UserWarning(
                        f'Unsupported instance {args[0]} (type {args[0].pp_type})'
                    )

                instance_load = cast(ex.PhyExpression, args[0])
                bound_ref = cls.BoundMethodRef(instance_load, callable)
                rest_args = args[1:]
                return f.make_bound_method_call(bound_ref, rest_args, target)

        if isinstance(callable.pp_type, ptrs.FunctionPointerType):
            lg.debug(f'Call: function pointer {callable}')
            call = f.make_pointer_call(callable, args, target)
            return f.create_call_frame(call, args)

        raise UserWarning(f'Unsupported callable {callable}: {callable.pp_type}')

    def tx_boolop(self, source: ast.BoolOp, target: regs.Register):
        values = source.values
        args = [self.tx_phy_value(value) for value in values]
        return f.create_boolop(args, source.op, target)

    def tx_phy_expression(
        self, source: ast.AST, target: regs.Register = regs.DEFAULT_REGISTER
    ) -> ex.PhyExpression:

        expression = self.tx_expression(source, target)

        if not isinstance(expression, ex.PhyExpression):
            raise UserWarning(f'Physical value required {expression}')

        return expression

    def tx_phy_value(
        self, source: ast.AST, target: regs.Register = regs.DEFAULT_REGISTER
    ):
        load = self.tx_phy_expression(source, target)

        if isinstance(load, ex.Assignable):
            return ptrs.Deref(load, target)

        return load

    def tx_subscript(self, source: ast.Subscript, target: regs.Register):
        available = regs.get_available([target])
        value_target = available.pop()
        slice_target = available.pop()

        value = self.tx_expression(source.value, value_target)
        slice = self.tx_expression(source.slice, slice_target)
        return f.create_subscript(value, slice, target)

    def tx_known_name(
        self, namespace: ns.Namespace, known_name: b.KnownName,
        target: regs.Register
    ) -> ex.Expression:

        if isinstance(known_name, b.Constant):
            lg.debug(f'KnownName: Constant {known_name}')
            return namespace.load_const(known_name, target)

        if isinstance(known_name, ex.GenericVariable):
            lg.debug(f'KnownName: Generic variable {known_name.name}')
            load = namespace.load_variable(known_name, regs.DEFAULT_REGISTER)
            return ex.Assignable(load, target, name=known_name.name)

        if isinstance(known_name, bi.BuiltinInline):
            lg.debug(f'KnownName: Builtin inline {known_name.name}')
            return bi.BuiltinInlineWrapper(known_name)

        if isinstance(known_name, cls.Method):
            lg.debug(f'KnownName: Method {known_name.name}')
            return calls.PointerToFunction(known_name, target)

        if isinstance(known_name, calls.Function):
            lg.debug(f'KnownName: Function {known_name.name}')
            return calls.PointerToFunction(known_name, target)

        if isinstance(known_name, t.DecoratorType):
            lg.debug(f'KnownName: Decorator type {known_name.name}')
            return ex.DecoratorApplication(known_name)

        if isinstance(known_name, b.PPType):
            lg.debug(f'KnownName: Known type {known_name}')
            return ex.TypeWrapper(known_name)

        if isinstance(known_name, ex.BuiltinMetaoperator):
            lg.debug(f'KnownName: Builtin metaoperator {known_name.name}')
            return known_name

        if isinstance(known_name, cls.GlobalInstance):
            lg.debug(f'KnownName: Global instance {known_name.name}')
            load = cls.PointerToGlobalInstance(known_name, target)
            return load

        if isinstance(known_name, arr.GlobalArray):
            lg.debug(f'KnownName: Global array {known_name.name}')
            return ptrs.PointerToGlobal(known_name, target)

        # NB: this should be the last check
        if isinstance(known_name, ns.Namespace):
            return ns.NamespaceWrapper(known_name)

        raise UserWarning(f'Unsupported name {known_name} as expression')

    def tx_expression(
        self,
        source: ast.AST,
        target: regs.Register = regs.DEFAULT_REGISTER,
        namespace: ns.Namespace | None = None
    ) -> ex.Expression:

        if isinstance(source, ast.Constant):
            pp_type = h.get_constant_type(source)
            value = h.get_constant_value(pp_type, source)
            lg.debug(f'Literal {value} ({pp_type})')
            return ex.ConstantExpression(pp_type, value, target)

        if isinstance(source, ast.Name):
            lg.debug(f'Expression: Name {source.id}')
            name = source.id

            if not namespace:
                lookup = self.context.lookup_name_upwards(name)
                return self.tx_expression(source, target, namespace=lookup.namespace)
            else:
                lookup = namespace.get_own_name(source.id)
                return self.tx_known_name(lookup.namespace, lookup.known_name, target)

        if isinstance(source, ast.Attribute):
            lg.debug(f'Expression: Attribute {source.attr}')
            value = self.tx_expression(source.value, namespace=namespace)

            if isinstance(value, ex.Assignable):
                lg.debug('Attribute: Stripping assignable')
                value = ptrs.Deref(value, regs.DEFAULT_REGISTER)

            if isinstance(value, ns.NamespaceWrapper):
                lg.debug('Attribute: Namespace')
                child_kn = value.namespace.get_own_name(source.attr).known_name
                return self.tx_known_name(value.namespace, child_kn, target)

            if isinstance(value.pp_type, ex.ICompoundType):
                lg.debug('Attribute: Compound type')
                load = value.pp_type.load_member(value, source.attr, target)
                return load

            raise UserWarning(f'Unsupported attribute {value} ({value.pp_type})')

        if isinstance(source, ast.BinOp):
            lg.debug('Expression: BinOp')
            left = self.tx_phy_value(source.left, regs.REGISTERS[0])
            right = self.tx_phy_value(source.right, regs.REGISTERS[1])
            return f.create_binop(left, right, source.op, target)

        if isinstance(source, ast.Call):
            lg.debug('Expression: Call')
            return self.tx_call(source, target)

        if isinstance(source, ast.UnaryOp):
            lg.debug('Expression: UnaryOp')
            right = self.tx_phy_value(source.operand, regs.REGISTERS[0])
            return f.create_unary(right, source.op, target)

        if isinstance(source, ast.BoolOp):
            lg.debug('Expression: BoolOp')
            return self.tx_boolop(source, target)

        if isinstance(source, ast.Compare):
            lg.debug('Expression: Compare')
            left = self.tx_phy_value(source.left, regs.REGISTERS[0])
            ops = source.ops

            if len(source.comparators) != 1:
                raise UserWarning(
                    f'Unsupported number of comparators {len(source.comparators)}'
                )

            assert len(ops) == 1

            right = self.tx_phy_value(source.comparators[0], regs.REGISTERS[1])
            return f.create_compare(left, ops[0], right, target)

        if isinstance(source, ast.Subscript):
            lg.debug('Expression: Subscript')
            return self.tx_subscript(source, target)

        if isinstance(source, (ast.Tuple, ast.List)):
            lg.debug('Expression: Tuple/List')
            return ex.MetaList(list(self.tx_expression(e) for e in source.elts))

        raise UserWarning(f'Unsupported expression {source}')
