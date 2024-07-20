$translator = "$PSScriptRoot/src/semu/pysemu/translator.py"
$compiler = "$PSScriptRoot/src/semu/compile/compiler.py"
$emulator = "$PSScriptRoot/src/semu/runtime/emulator.py"
$example = "$PSScriptRoot/examples/pysemu/function.py"
$sasm = "$PSScriptRoot/.build/function.sasm"
$rom = "$PSScriptRoot/roms/function.bin"

python $translator $example -v $sasm
Get-Content .build/function.sasm
python $compiler $sasm $rom
python $emulator $rom
