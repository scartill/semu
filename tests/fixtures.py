# type: ignore
import pytest
from pathlib import Path

import semu.sasm.hwc as hwc
import semu.sasm.masm as masm


@pytest.fixture
def with_hardware():
    yield hwc.generate_compilation_item()


@pytest.fixture
def with_kernel(with_hardware):
    base_dir = Path(__file__).parent.parent
    kernel_lib = base_dir / 'lib' / 'kernel'
    items = [with_hardware]
    items.extend(masm.collect_library(kernel_lib))
    yield items
