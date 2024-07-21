$subject = "assignments"
$translator = "$PSScriptRoot/src/semu/pysemu/translator.py"
$compiler = "$PSScriptRoot/src/semu/compile/compiler.py"
$emulator = "$PSScriptRoot/src/semu/runtime/emulator.py"

$source = "$PSScriptRoot/examples/pysemu/$subject.py"
$sasm = "$PSScriptRoot/.build/$subject.sasm"
$rom = "$PSScriptRoot/roms/$subject.bin"

python $translator $source -v $sasm

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

# TODO: disable macroprocessor
python $compiler $sasm $rom
python $emulator $rom
