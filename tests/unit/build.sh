#!/bin/bash
# Build C++ unit tests
set -e

UNIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$UNIT_DIR/build"

# Clean stale cache if CMakeLists.txt is newer than the cache
if [ -f "$BUILD_DIR/CMakeCache.txt" ] && [ "$UNIT_DIR/CMakeLists.txt" -nt "$BUILD_DIR/CMakeCache.txt" ]; then
    echo "CMakeLists.txt changed — clearing build cache..."
    rm -rf "$BUILD_DIR"
fi

cmake -B "$BUILD_DIR" -S "$UNIT_DIR" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR" --config Release
