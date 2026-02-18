#!/bin/bash

mkdir -p ../build/linux-gcc/qt6/
mkdir -p ../install/linux-gcc/qt6/

cd ../build/linux-gcc/qt6/

../../../qt6/configure -prefix ../../../install/linux-gcc/qt6/

cmake --build . --parallel 4
cmake --install .
