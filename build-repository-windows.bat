mkdir ..\build\windows-msvc2022-x64
mkdir ..\install\windows-msvc2022-x64

cd ..\build\windows-msvc2022-x64

..\..\qt6\configure.bat -prefix ..\..\install\windows-msvc2022-x64

cmake --build .
cmake --install .
