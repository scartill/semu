$root = "$PSScriptRoot/../.."
$compiler = "$root/src/semu/sasm/compiler.py"
$rom = "$root/roms/twothreads.bin"
$kernel = "$root/lib/kernel"
$app = "$PSScriptRoot/app.sasm"

python $compiler --library $kernel $app $rom
