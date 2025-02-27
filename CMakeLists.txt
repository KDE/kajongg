# vim: set expandtab shiftwidth=4 softtabstop=4:
cmake_minimum_required (VERSION 3.16)

# Release Service version, managed by release script
set(RELEASE_SERVICE_VERSION_MAJOR "24")
set(RELEASE_SERVICE_VERSION_MINOR "12")
set(RELEASE_SERVICE_VERSION_MICRO "3")
set(RELEASE_SERVICE_VERSION "${RELEASE_SERVICE_VERSION_MAJOR}.${RELEASE_SERVICE_VERSION_MINOR}.${RELEASE_SERVICE_VERSION_MICRO}")

project(kajongg VERSION ${RELEASE_SERVICE_VERSION})

set(PYTHON_MIN_VERSION "3.8.0")
set(QT_MIN_VERSION "6.5.0")
set(KF_MIN_VERSION "6.0.0")
set(TWISTED_MIN_VERSION "16.6.0")

find_package(ECM ${KF_MIN_VERSION} REQUIRED NO_MODULE)
    
set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake-modules ${ECM_MODULE_PATH})

include(FeatureSummary)
include(KDEInstallDirs)
include(ECMInstallIcons)
include(KDECMakeSettings)

find_package(Python3 ${PYTHON_MIN_VERSION} COMPONENTS REQUIRED)

include(KDEPython)

find_package(Twisted ${TWISTED_MIN_VERSION} REQUIRED)
find_package(Qt6 ${QT_MIN_VERSION} REQUIRED COMPONENTS
    Core
    Gui
    Svg
    SvgWidgets
    Widgets
)

find_package(KF6 ${KF_MIN_VERSION} REQUIRED COMPONENTS
    DocTools
    I18n
)

add_subdirectory( voices )
add_subdirectory( doc )
add_subdirectory( icons )

set(SRCFILES
    src/permutations.py
    src/animation.py
    src/mjresource.py
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
    src/wind.py
    src/rand.py
    src/config.py
    src/kdestub.py
    src/deferredutil.py
    src/differ.py
    src/player.py
    src/game.py
    src/games.py
    src/genericdelegates.py
    src/guiutil.py
    src/humanclient.py
    src/mi18n.py
    src/login.py
    src/kde.py
    src/dialogs.py
    src/mainwindow.py
    src/move.py
    src/modeltest.py
    src/playerlist.py
    src/predefined.py
    src/qtreactor.py
    src/query.py
    src/rulesetselector.py
    src/hand.py
    src/rule.py
    src/rulecode.py
    src/scene.py
    src/scoringdialog.py
    src/scoring.py
    src/user.py
    src/servertable.py
    src/servercommon.py
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
    src/visible.py
    src/log.py
    src/qt.py
    src/configdialog.py
    src/tilesource.py
    src/util.py
    src/kajcsv.py)

set(DATAFILES
    src/kajonggui.rc)


find_package(KMahjongglib6 6.0.0 REQUIRED)

# In KDE4, this was done with PYKDE4_INSTALL_PYTHON_FILES and PYKDE4_ADD_EXECUTABLE
# because including PYKDE4 does not seem appropriate when not using PYKDE4 bindings,
# I expanded those macros, reducing to what we actually need. No Windows support here yet.
# Those macros come from ./cmake-modules/KDEPython.cmake

# generating appversion.py 2x, once for toplevel setup ,once for app in src/ itself
configure_file(src/appversion.py.in appversion.py)
configure_file(src/appversion.py.in src/appversion.py)
configure_file(src/kdepaths.py.in src/kdepaths.py)

KDE_INSTALL_PYTHON_FILES(${SRCFILES} src/kajongg.py src/kajonggserver.py)
KDE_INSTALL_PYTHON_FILES(${CMAKE_CURRENT_BINARY_DIR}/src/kdepaths.py)
KDE_INSTALL_PYTHON_FILES(${CMAKE_CURRENT_BINARY_DIR}/src/appversion.py)
KDE_ADD_PYTHON_EXECUTABLE(kajongg.py kajongg)
KDE_ADD_PYTHON_EXECUTABLE(kajonggserver.py kajonggserver)

install(FILES ${DATAFILES} DESTINATION ${KDE_INSTALL_DATADIR}/kajongg)

install(FILES org.kde.kajongg.desktop DESTINATION ${KDE_INSTALL_APPDIR})
install(FILES org.kde.kajongg.appdata.xml DESTINATION ${KDE_INSTALL_METAINFODIR})

ki18n_install(po)
kdoctools_install(po)

feature_summary(WHAT ALL FATAL_ON_MISSING_REQUIRED_PACKAGES)
