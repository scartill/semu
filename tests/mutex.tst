KERNEL="../examples/lib/kernel"

SRC="hw.sasm"
SRC+=" $KERNEL/startup.sasm $KERNEL/sync.sasm $KERNEL/threads.sasm $KERNEL/kernel.sasm $KERNEL/api.sasm"
SRC+=" mutex/app.sasm"

CMP=mutex/output.log
