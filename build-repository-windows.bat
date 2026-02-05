echo on

mkdir ..\build\windows-msvc2022-x64\qt6
mkdir ..\install\windows-msvc2022-x64\qt6

cd ..\build\windows-msvc2022-x64\qt6

call ..\..\..\qt6\configure.bat -prefix ..\..\install\windows-msvc2022-x64\qt6\

cmake --build .
cmake --install .
