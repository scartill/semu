$root = "$PSScriptRoot/../.."
$assembler = "$root/src/semu/sasm/masm.py"

$rom = "$root/roms/twothreads.bin"
$kernel = "$root/lib/pseudopython/kernel"
$app = "$PSScriptRoot/app.sasm"

python $assembler --library $kernel $app $rom
