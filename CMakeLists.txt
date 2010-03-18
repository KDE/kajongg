# search packages used by KDE
IF(NOT KDE4_FOUND)
     find_package(KDE4 REQUIRED)
ENDIF(NOT KDE4_FOUND)
include(FindPythonLibrary)
include(FindPyQt4)
include(FindPyKDE4)
include(FindSqlite)

set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH}  ${CMAKE_CURRENT_SOURCE_DIR}/cmake-modules )
find_package(Twisted REQUIRED)

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
src/message.py
src/client.py
src/common.py
src/config.py
src/differ.py
src/game.py
src/games.py
src/genericdelegates.py
src/guiutil.py
src/humanclient.py
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
src/sound.py
src/tables.py
src/tile.py
src/tileset.py
src/tilesetselector.py
src/statesaver.py
src/util.py)


IF(NOT TWISTED_FOUND)
    MESSAGE("Twisted was not found.  It is needed by kajongg to run.")
    macro_log_feature(TWISTED_FOUND "Twisted" "Twisted was not found.  It is needed by kajongg to run." "http://www.twistedmatrix.com" FALSE)
ENDIF(NOT TWISTED_FOUND)


IF(PYQT4_FOUND AND PYKDE4_FOUND AND SQLITE_FOUND)
    SET(INSTALL_KAJONGG TRUE)
ENDIF(PYQT4_FOUND AND PYKDE4_FOUND AND SQLITE_FOUND)

IF(INSTALL_KAJONGG)
    PYKDE4_INSTALL_PYTHON_FILES(${SRCFILES})
    install(FILES src/tilesetselector.ui src/backgroundselector.ui DESTINATION ${DATA_INSTALL_DIR}/kajongg)
    install(FILES src/kajonggui.rc DESTINATION ${DATA_INSTALL_DIR}/kajongg)
    PYKDE4_ADD_EXECUTABLE(kajongg.py kajongg)
    PYKDE4_ADD_EXECUTABLE(kajonggserver.py kajonggserver)
    kde4_install_icons(${ICON_INSTALL_DIR})
    install(FILES kajongg.desktop DESTINATION ${XDG_APPS_INSTALL_DIR})
ENDIF(INSTALL_KAJONGG)
