#!/bin/bash

mkdir -p ../build/linux-gcc/
mkdir -p ../install/linux-gcc/

cd ../build/linux-gcc/

../../qt6/configure -prefix ../../install/linux-gcc/

cmake --build . --parallel 4
cmake --install .
