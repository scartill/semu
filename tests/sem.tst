KERNEL="../examples/lib/kernel"

SRC="hw.sasm"
SRC+=" $KERNEL/startup.sasm $KERNEL/threads.sasm $KERNEL/kernel.sasm $KERNEL/api.sasm"
SRC+=" sem/app.sasm"

CMP=sem/output.log