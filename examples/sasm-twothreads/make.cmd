set SEMU_ROOT=../..
set ASM=%SEMU_ROOT%/src/semuasm.py
set ROM=%SEMU_ROOT%/roms/twothreads.bin

py %ASM% startup.sasm kernel.sasm api.sasm twothreads.sasm %ROM%
