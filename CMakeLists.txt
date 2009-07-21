# search packages used by KDE
find_package(KDE4 REQUIRED)
include(KDE4Defaults)
include(MacroLibrary)

# The name of the project
#project(kmj python) # FIXME this is currently a C++ project and requires a C++ compilier.
set(PROJECT_NAME kmj)
set(PROGRAM_VERSION 0.3.1)
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH}  ${CMAKE_CURRENT_SOURCE_DIR}/cmake-modules )

include(KmjLib)
include(DistMacros)


MACRO(PYKDE4_ADD_EXECUTABLE _pyname _exename)
    INSTALL(CODE "EXECUTE_PROCESS(COMMAND ${CMAKE_COMMAND} -DTARGET=${DATA_INSTALL_DIR}/kmj/${_pyname} -DLINK_NAME=${BIN_INSTALL_DIR}/${_exename} -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake-modules/create_exe_symlink.cmake)" )
ENDMACRO(PYKDE4_ADD_EXECUTABLE)

macro_optional_find_package(PythonLibrary)
macro_optional_find_package(SIP)

find_package(PyQt4)
IF(NOT PYQT4_FOUND)
    macro_log_feature(PYQT4_FOUND "PyQt4" "PyQt4 was not found.  It is needed by kmj to run. (Use -DINSTALL_KMJ=TRUE to install anyway)" "http://www.riverbankcomputing.co.uk/pyqt/" FALSE)
ENDIF(NOT PYQT4_FOUND)

find_package(PyKDE4)
IF(NOT PYKDE4_FOUND)
    macro_log_feature(PYKDE4_FOUND "PyKDE4" "PyKDE4 was not found.  It is needed by kmj to run.  (Use -DINSTALL_KMJ=TRUE to install anyway)" "http://www.riverbankcomputing.co.uk" FALSE)
ENDIF(NOT PYKDE4_FOUND)

find_package(Sqlite)
IF(NOT SQLITE_FOUND)
    macro_log_feature(SQLITE_FOUND "Sqlite3" "Sqlite3 was not found.  It is needed by kmj to run.  (Use -DINSTALL_KMJ=TRUE to install anyway)" "http://www.sqlite.org" FALSE)
ENDIF(NOT SQLITE_FOUND)

IF(PYQT4_FOUND AND PYKDE4_FOUND AND SQLITE_FOUND)
    SET(INSTALL_KMJ TRUE)
ENDIF(PYQT4_FOUND AND PYKDE4_FOUND AND SQLITE_FOUND)

IF(INSTALL_KMJ)
    # Python files to be installed and byte compiled are specified with
    # PYKDE4_INSTALL_PYTHON_FILES().
    PYKDE4_INSTALL_PYTHON_FILES(src/*.py)
#    install( FILES
#        guidance-power-manager.py
#        guidance-power-manager.ui
#        powermanage.py
#        DESTINATION ${DATA_INSTALL_DIR}/guidance-power-manager )
    PYKDE4_ADD_EXECUTABLE(src/kmj.py kmj)
    # Designer Qt files to be compiled, installed and also byte compiled are
    # specified with pykde4_add_ui_files().
    PYKDE4_ADD_UI_FILES(src/*.ui)
#    install(FILES kmj.desktop DESTINATION ${AUTOSTART_INSTALL_DIR})
    kde4_create_handbook(doc/en/index.docbook)

ENDIF(INSTALL_KMJ)



#find_package(GettextMsgfmt REQUIRED)

#PYKDE_INSTALL_PYTHON_FILES(src/kmj.py)
#PYKDE_INSTALL_PYTHON_FILES(src/background.py)
#PYKDE_INSTALL_PYTHON_FILES(src/backgroundselector.py)
#PYKDE_INSTALL_PYTHON_FILES(src/board.py)
#PYKDE_INSTALL_PYTHON_FILES(src/config.py)
#PYKDE_INSTALL_PYTHON_FILES(src/games.py)
#PYKDE_INSTALL_PYTHON_FILES(src/genericdelegates.py)
#PYKDE_INSTALL_PYTHON_FILES(src/playerlist.py)
#PYKDE_INSTALL_PYTHON_FILES(src/scoring.py)
#PYKDE_INSTALL_PYTHON_FILES(src/scoringtest.py)
#PYKDE_INSTALL_PYTHON_FILES(src/tileset.py)
#PYKDE_INSTALL_PYTHON_FILES(src/tilesetselector.py)
#PYKDE_INSTALL_PYTHON_FILES(src/util.py)

# Designer Qt files to be compiled, installed and also byte compiled are
# specified with pykde4_add_ui_files().
#PYKDE4_ADD_UI_FILES(src/backgroundselector.ui)
#PYKDE4_ADD_UI_FILES(src/tilesetselector.ui)
#PYKDE4_ADD_UI_FILES(src/playerlist.ui)
#PYKDE4_ADD_UI_FILES(src/general.ui)

# Do not setup message translations - that is another package. You
# can install a translation manually, example: german: Get
# http://websvn.kde.org/trunk/l10n-kde4/de/messages/playground-games/kmj.po
# and do something like
#	msgfmt -o /usr/share/locale/de/LC_MESSAGES/kmj.mo kmj.po

# Support for creating simple distribution tarball of the project.
# List of files for the 'dist' make target.
SOURCE_DIST(${CMAKE_SOURCE_DIR}
#    AUTHORS
#    ChangeLog
    CMakeLists.txt
#    COPYING
#    INSTALL
#    README
#    TODO
    src/kmjui.rc
    src/*.py
    src/*.ui
    src/*.svg
    src/*.desktop
    doc/*.png
    doc/*
    cmake-modules/*
)

