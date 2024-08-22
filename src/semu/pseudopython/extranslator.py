import ast
from typing import List, cast

import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.builtins as bi
import semu.pseudopython.helpers as h
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls
import semu.pseudopython.classes as cls
import semu.pseudopython.methods as meth
import semu.pseudopython.arrays as arr
import semu.pseudopython.pointers as ptrs


class ExpressionTranslator:
    context: ns.Namespace

    def __init__(self, context: ns.Namespace):
        self.context = context

    def resolve_object(self, ast_name: ast.AST) -> ns.NameLookup:
        path = h.collect_path_from_attribute(ast_name)
        top_name = path.pop(0)
        lookup = self.context.lookup_name_upwards(top_name)

        if lookup is None:
            raise UserWarning(f'Unknown reference {top_name}')

        while path:
            next_name = path.pop(0)

            if not isinstance(lookup.known_name, ns.Namespace):
                raise UserWarning(f'Unsupported path lookup {lookup.known_name}')

            lookup = lookup.known_name.get_own_name(next_name)

        return lookup

    def tx_builtin_call(
        self, callable: bi.BuiltinInline, ast_args: List[ast.expr],
        target: regs.Register
    ):
        assert len(ast_args) <= len(regs.REGISTERS)
        args = []

        for i, ast_arg in enumerate(ast_args):
            args.append(self.tx_expression(ast_arg, regs.REGISTERS[i]))

        return h.create_inline(callable, args, target)

    def tx_call(self, ast_call: ast.Call, target: regs.Register):
        callable = self.tx_expression(ast_call.func)

        if isinstance(callable, bi.BuiltinInlineWrapper):
            return self.tx_builtin_call(callable.inline, ast_call.args, target)

        if not isinstance(callable.target_type, t.AbstractCallableType):
            raise UserWarning(f'Not callable type {callable}')

        args = [
            self.tx_expression(ast_arg)
            for ast_arg in ast_call.args
        ]

        if isinstance(callable, meth.BoundMethodRef):
            return h.make_bound_method_call(callable, args, target)

        if not isinstance(callable, el.PhyExpression):
            raise UserWarning(f'A callable {callable} is not a physical value')

        if isinstance(callable, calls.FunctionRef):
            call = h.make_direct_call(callable, args, target)
            return h.create_call_frame(call, args)

        elif isinstance(callable.target_type, meth.MethodPointerType):
            # Autofind this
            if len(args) == len(callable.target_type.arg_types) - 1:
                this_lookup = self.context.get_own_name('this')
                formal = this_lookup.known_name
                assert isinstance(formal, meth.InstanceFormalParameter)
                this = ptrs.PointerToLocal(formal)
                bound_ref = meth.BoundMethodRef(callable.target_type, callable, this)
                return h.make_bound_method_call(bound_ref, args, target)
            # Direct method binding
            else:
                if not isinstance(args[0].target_type, cls.InstancePointerType):
                    raise UserWarning(f'Unsupported instance {args[0]}')

                instance_load = cast(el.PhyExpression, args[0])

                bound_ref = meth.BoundMethodRef(
                    callable.target_type,
                    callable,
                    instance_load
                )

                rest_args = args[1:]
                return h.make_bound_method_call(bound_ref, rest_args, target)

        elif isinstance(callable.target_type, ptrs.FunctionPointerType):
            call = h.make_pointer_call(callable, args, target)
            return h.create_call_frame(call, args)

        else:
            raise UserWarning(f'Unsupported callable {callable}')

    def tx_boolop(self, source: ast.BoolOp, target: regs.Register):
        values = source.values
        args = [self.tx_expression(value) for value in values]
        return h.create_boolop(args, source.op, target)

    def tx_phy_expression(
        self, source: ast.AST, target: regs.Register = regs.DEFAULT_REGISTER
    ) -> el.PhyExpression:

        expression = self.tx_expression(source, target)

        if not isinstance(expression, el.PhyExpression):
            raise UserWarning(f'Physical value required {expression}')

        return expression

    def tx_subscript(self, source: ast.Subscript, target: regs.Register):
        available = regs.get_available([target])
        value_target = available.pop()
        slice_target = available.pop()

        value = self.tx_expression(source.value, value_target)
        slice = self.tx_expression(source.slice, slice_target)
        return h.create_subscript(value, slice, target)

    def tx_expression(
        self, source: ast.AST,
        target: regs.Register = regs.DEFAULT_REGISTER
    ) -> el.Expression:

        if isinstance(source, ast.Constant):
            target_type = h.get_constant_type(source)
            value = h.get_constant_value(target_type, source)
            return el.ConstantExpression(target_type, value, target)

        if isinstance(source, ast.Name) or isinstance(source, ast.Attribute):
            lookup = self.resolve_object(source)
            namespace = lookup.namespace
            known_name = lookup.known_name

            if isinstance(known_name, n.Constant):
                return namespace.load_const(known_name, target)

            if isinstance(known_name, el.GlobalVariable):
                load = namespace.load_variable(known_name, regs.DEFAULT_REGISTER)
                return el.ValueLoader(load, target)

            if isinstance(known_name, bi.BuiltinInline):
                return bi.BuiltinInlineWrapper(known_name)

            if isinstance(known_name, meth.Method):
                return meth.PointerToGlobalMethod(known_name, target)

            if isinstance(known_name, calls.Function):
                return calls.FunctionRef(known_name, target)

            if isinstance(known_name, el.StackVariable):
                assert isinstance(namespace, calls.Function)
                load = namespace.load_variable(known_name, regs.DEFAULT_REGISTER)
                return el.ValueLoader(load, target)

            if isinstance(known_name, t.DecoratorType):
                return el.DecoratorApplication(known_name)

            if isinstance(known_name, cls.Class):
                return el.TypeWrapper(cls.InstancePointerType(known_name))

            if isinstance(known_name, b.TargetType):
                return el.TypeWrapper(known_name)

            if isinstance(known_name, el.BuiltinMetaoperator):
                return known_name

            if isinstance(known_name, cls.GlobalInstance):
                return cls.GlobalInstanceLoad(known_name, target)

            if isinstance(known_name, meth.GlobalPointerMember):
                load = ptrs.PointerToGlobal(known_name.instance_pointer)
                deref = ptrs.Deref(load)
                member_load = cls.ClassMemberLoad(deref, known_name.variable)
                return el.ValueLoader(member_load, target)

            if isinstance(known_name, meth.StackPointerMember):
                load = ptrs.PointerToLocal(known_name.instance_parameter)
                deref = ptrs.Deref(load)
                member_load = cls.ClassMemberLoad(deref, known_name.variable)
                return el.ValueLoader(member_load, target)

            if isinstance(known_name, meth.GlobalInstanceMethod):
                return meth.BoundMethodRef.from_GIM(known_name)

            if isinstance(known_name, meth.GlobalPointerMethod):
                return meth.BoundMethodRef.from_GPM(known_name)

            if isinstance(known_name, meth.StackPointerMethod):
                return meth.BoundMethodRef.from_SPM(known_name)

            if isinstance(known_name, arr.GlobalArray):
                return ptrs.PointerToGlobal(known_name, target)

            raise UserWarning(f'Unsupported name {known_name} as expression')

        if isinstance(source, ast.BinOp):
            left = self.tx_expression(source.left, regs.REGISTERS[0])
            right = self.tx_expression(source.right, regs.REGISTERS[1])
            return h.create_binop(left, right, source.op, target)

        if isinstance(source, ast.Call):
            return self.tx_call(source, target)

        if isinstance(source, ast.UnaryOp):
            right = self.tx_expression(source.operand, regs.REGISTERS[0])
            return h.create_unary(right, source.op, target)

        if isinstance(source, ast.BoolOp):
            return self.tx_boolop(source, target)

        if isinstance(source, ast.Compare):
            left = self.tx_expression(source.left, regs.REGISTERS[0])
            ops = source.ops

            if len(source.comparators) != 1:
                raise UserWarning(
                    f'Unsupported number of comparators {len(source.comparators)}'
                )

            assert len(ops) == 1

            right = self.tx_expression(source.comparators[0], regs.REGISTERS[1])
            return h.create_compare(left, ops[0], right, target)

        if isinstance(source, ast.Subscript):
            return self.tx_subscript(source, target)

        if isinstance(source, (ast.Tuple, ast.List)):
            return el.MetaList(list(self.tx_expression(e) for e in source.elts))

        raise UserWarning(f'Unsupported expression {source}')
