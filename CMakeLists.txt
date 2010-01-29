# use with cmake -DCMAKE_INSTALL_PREFIX=/usr srcdir

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
# cmake does not really support python projects...
#project(kajongg python) # FIXME this is currently a C++ project and requires a C++ compilier.
set(PROJECT_NAME kajongg)
set(PROGRAM_VERSION 0.4.0)

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
src/statesaver.py
src/util.py)


IF(QT4_FOUND AND PYQT4_FOUND AND PYKDE4_FOUND AND SQLITE_FOUND)
    SET(INSTALL_KAJONGG TRUE)
ENDIF(QT4_FOUND AND PYQT4_FOUND AND PYKDE4_FOUND AND SQLITE_FOUND)

IF(INSTALL_KAJONGG)
    PYKDE4_INSTALL_PYTHON_FILES(${SRCFILES})
    install(FILES src/tilesetselector.ui src/backgroundselector.ui DESTINATION ${DATA_INSTALL_DIR}/kajongg)
    PYKDE4_ADD_EXECUTABLE(kajongg.py kajongg)
    PYKDE4_ADD_EXECUTABLE(kajonggserver.py kajonggserver)
    kde4_create_handbook(../doc/kajongg/index.docbook)

# there must be a better way to strip the trailing LF
# and there must be a predefined macro for icon installation
    EXECUTE_PROCESS(COMMAND sh -c "set - `kde4-config --expandvars --install icon `&&echo  -n $1"
       OUTPUT_VARIABLE _icon)
    install(FILES src/kajongg.svg DESTINATION ${_icon}hicolor/scalable/apps)
    install(FILES src/games-kajongg-law.svg DESTINATION ${_icon}hicolor/scalable/actions)
ENDIF(INSTALL_KAJONGG)
