#!/bin/bash

# 1. Clean up previous artifacts to ensure a fresh build
echo "🧹 Cleaning up previous builds..."
rm -rf build/ dist/ *.spec

# 2. Build Student Client
echo "🔨 Building Student Client..."
pyinstaller --onefile --clean --name knewit_student_linux --paths . \
    --hidden-import textual.widgets._tab_pane \
    --hidden-import textual.widgets._header \
    --hidden-import textual.widgets._footer \
    client/student_ui.py

# 3. Build Host Client
# Note: Host UI uses ListView, so we add _list_view just in case, 
# though often PyInstaller finds it automatically.
echo "🔨 Building Host Client..."
pyinstaller --onefile --clean --name knewit_host_linux --paths . \
    --hidden-import textual.widgets._tab_pane \
    --hidden-import textual.widgets._header \
    --hidden-import textual.widgets._footer \
    --hidden-import textual.widgets._list_view \
    client/host_ui.py

echo "✅ Build Complete! Executables are in dist/"
ls -lh dist/