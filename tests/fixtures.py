# type: ignore
import pytest
from pathlib import Path

import semu.compile.hwc as hwc
import semu.compile.compiler as compiler


@pytest.fixture
def with_hardware():
    yield hwc.generate_compilation_item()


@pytest.fixture
def with_kernel(with_hardware):
    base_dir = Path(__file__).parent.parent
    kernel_lib = base_dir / 'lib' / 'kernel'
    items = [with_hardware]
    items.extend(compiler.collect_library(kernel_lib))
    yield items
