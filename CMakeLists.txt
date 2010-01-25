# search packages used by KDE
find_package(KDE4 REQUIRED)
include(KDE4Defaults)
include(MacroLibrary)
include(FindQt4)
include(FindPythonLibrary)
include(FindPyQt4)
include(FindPyKDE4)
include(FindSqlite)

# The name of the project
#project(kajongg python) # FIXME this is currently a C++ project and requires a C++ compilier.
set(PROJECT_NAME kajongg)
set(PROGRAM_VERSION 0.4.0)
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH}  ${CMAKE_CURRENT_SOURCE_DIR}/cmake-modules )

#macro_optional_find_package(SIP)
include(DistMacros)

set(SRCFILES 
src/about.py
src/background.py
src/backgroundselector.py
src/board.py
src/client.py
src/config.py
src/game.py
src/games.py
src/genericdelegates.py
src/guiutil.py
src/kajongg.py
src/kajonggserver.py
src/move.py
src/playerlist.py
src/playfield.py
src/predefined.py
src/qt4reactor.py
src/query.py
src/rulesetselector.py
src/scoringengine.py
src/scoring.py
src/scoringtest.py
src/tables.py
src/tile.py
src/tileset.py
src/tilesetselector.py
src/util.py)

IF(QT4_FOUND AND PYQT4_FOUND AND PYKDE4_FOUND AND SQLITE_FOUND)
    SET(INSTALL_KAJONGG TRUE)
ENDIF(QT4_FOUND AND PYQT4_FOUND AND PYKDE4_FOUND AND SQLITE_FOUND)

IF(INSTALL_KAJONGG)
    # Python files to be installed and byte compiled are specified with
    # PYKDE4_INSTALL_PYTHON_FILES().
    PYKDE4_INSTALL_PYTHON_FILES(${SRCFILES})
    # macro missing: PYKDE4_ADD_UI_FILES(src/tilesetselector.ui src/backgroundselector.ui)
    install(FILES src/tilesetselector.ui src/backgroundselector.ui DESTINATION ${KDE4_DATA_INSTALL_DIR}/kajongg)
    PYKDE4_ADD_EXECUTABLE(kajongg.py kajongg)
    PYKDE4_ADD_EXECUTABLE(kajonggserver.py kajonggserver)
    kde4_create_handbook(../doc/kajongg/index.docbook)

ENDIF(INSTALL_KAJONGG)



#find_package(GettextMsgfmt REQUIRED)

# Do not setup message translations - that is another package. You
# can install a translation manually, example: german: Get
# http://websvn.kde.org/trunk/l10n-kde4/de/messages/playground-games/kajongg.po
# and do something like
#	msgfmt -o /usr/share/locale/de/LC_MESSAGES/kajongg.mo kajongg.po

# Support for creating simple distribution tarball of the project.
# List of files for the 'dist' make target.
SOURCE_DIST(${CMAKE_SOURCE_DIR}
    Changelog
    CMakeLists.txt
    src/COPYING
    README
    kajongg.desktop
    src/kajonggui.rc
    src/*.py
    src/*.ui
    src/*.svg
    cmake-modules/*
    compile.sh
    make_debian_package
    MANIFEST.in
    Messages.sh
    setup.cfg
    setup.py
    vg.supp
)

