. $PSScriptRoot/.venv/Scripts/Activate.ps1
$PPATH_SOURCE="$PSScriptRoot/examples/pseudopython"
$PPATH_LIB="$PSScriptRoot/lib/pseudopython"
$env:SEMU_PPATH="${PPATH_LIB};${PPATH_SOURCE}"
