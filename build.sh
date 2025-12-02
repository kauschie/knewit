#!/bin/bash

pyinstaller --onefile --clean --name knewit_student_linux --paths . --hidden-import textual.widgets._tab_pane --hidden-import textual.widgets._header --hidden-import textual.widgets._footer client/student_ui.py
pyinstaller --onefile --clean --name knewit_host_linux --paths . --hidden-import textual.widgets._tab_pane --hidden-import textual.widgets._header --hidden-import textual.widgets._footer client/host_ui.py