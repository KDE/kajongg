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
set(PROGRAM_VERSION 4.6.0)

add_subdirectory( voices )
add_subdirectory( doc )

set(SRCFILES 
src/about.py
src/animation.py
src/background.py
src/backgroundselector.py
src/board.py
src/chat.py
src/handboard.py
src/message.py
src/client.py
src/intelligence.py
src/altint.py
src/common.py
src/config.py
src/deferredutil.py
src/differ.py
src/meld.py
src/player.py
src/game.py
src/games.py
src/genericdelegates.py
src/guiutil.py
src/humanclient.py
src/login.py
src/kde.py
src/move.py
src/modeltest.py
src/playerlist.py
src/playfield.py
src/predefined.py
src/qt4reactor.py
src/query.py
src/rulesetselector.py
src/hand.py
src/rule.py
src/rulecode.py
src/scoring.py
src/server.py
src/sound.py
src/tables.py
src/tile.py
src/uitile.py
src/tileset.py
src/tilesetselector.py
src/tree.py
src/statesaver.py
src/wall.py
src/uiwall.py
src/util.py)

IF(NOT PYQT4_FOUND)
    macro_log_feature(PYQT4_FOUND "PyQt4" "PyQt4 was not found. It is needed by kajongg to run. (Use -DINSTALL_KAJONGG=TRUE to install anyway)" "http://www.riverbankcomputing.co.uk/software/pyqt/intro" FALSE "" "")
ENDIF(NOT PYQT4_FOUND)

IF(NOT PYKDE4_FOUND)
    macro_log_feature(PYKDE4_FOUND "PyKDE4" "PyKDE4 was not found. It is needed by kajongg to run. (Use -DINSTALL_KAJONGG=TRUE to install anyway)" "http://websvn.kde.org/trunk/KDE/kdebindings/python/pykde4/" FALSE "" "")
ENDIF(NOT PYKDE4_FOUND)

IF(NOT SQLITE_FOUND)
    macro_log_feature(SQLITE_FOUND "SQLite" "SQLite was not found. It is needed by kajongg to run. (Use -DINSTALL_KAJONGG=TRUE to install anyway)" "http://www.sqlite.org/" FALSE "" "")
ENDIF(NOT SQLITE_FOUND)

IF(NOT TWISTED_FOUND)
    MESSAGE("Twisted was not found. It is needed by kajongg to run.")
    macro_log_feature(TWISTED_FOUND "Twisted" "Twisted was not found. It is needed by kajongg to run. (Use -DINSTALL_KAJONGG=TRUE to install anyway)" "http://www.twistedmatrix.com/" FALSE "" "")
ENDIF(NOT TWISTED_FOUND)

IF(PYQT4_FOUND AND PYKDE4_FOUND AND SQLITE_FOUND AND TWISTED_FOUND)
    SET(INSTALL_KAJONGG TRUE)
ENDIF(PYQT4_FOUND AND PYKDE4_FOUND AND SQLITE_FOUND AND TWISTED_FOUND)

IF(INSTALL_KAJONGG)
    PYKDE4_INSTALL_PYTHON_FILES(${SRCFILES})
    install(FILES src/kajongg.py src/kajonggserver.py DESTINATION ${DATA_INSTALL_DIR}/kajongg)
    install(FILES src/tilesetselector.ui src/backgroundselector.ui DESTINATION ${DATA_INSTALL_DIR}/kajongg)
    install(FILES src/kajonggui.rc DESTINATION ${DATA_INSTALL_DIR}/kajongg)
    PYKDE4_ADD_EXECUTABLE(kajongg.py kajongg)
    PYKDE4_ADD_EXECUTABLE(kajonggserver.py kajonggserver)
    kde4_install_icons(${ICON_INSTALL_DIR})
    install(PROGRAMS kajongg.desktop DESTINATION ${XDG_APPS_INSTALL_DIR})
ENDIF(INSTALL_KAJONGG)

macro_display_feature_log()
