$subject = "consts"
$translator = "$PSScriptRoot/src/semu/pysemu/translator.py"
$compiler = "$PSScriptRoot/src/semu/compile/compiler.py"
$emulator = "$PSScriptRoot/src/semu/runtime/emulator.py"

$source = "$PSScriptRoot/examples/pysemu/$subject.py"
$sasm = "$PSScriptRoot/.build/$subject.sasm"
$rom = "$PSScriptRoot/roms/function.bin"

python $translator $source -v $sasm

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Get-Content $sasm
python $compiler $sasm $rom
python $emulator $rom
