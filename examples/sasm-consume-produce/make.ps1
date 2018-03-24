$SEMU_ROOT = "..\.."
$ASM = $SEMU_ROOT + "\src\semuasm.py"
$ROM = $SEMU_ROOT + "\roms\cons-prod.bin"
$LIB = "..\lib\sasm-kernel"

py $ASM $LIB\startup.sasm $LIB\kernel.sasm $LIB\api.sasm app.sasm $ROM
