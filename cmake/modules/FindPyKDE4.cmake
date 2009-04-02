# FindPyKDE4
#
# Checks that Python and PyKDE4 are installed and defines a couple macros:
#     * PYKDE4_INSTALL_PYTHON_FILES
#     * PYKDE4_ADD_UI_FILES
#     * PYKDE4_ADD_EXECUTABLE
# By Simon Edwards <simon@simonzone.com>
# This file is in the public domain.

INCLUDE (FindPythonInterp)

EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} ${CMAKE_SOURCE_DIR}/cmake/modules/FindPyKDE4.py OUTPUT_VARIABLE pykde_config)
IF(NOT pykde_config)
  # Failure to run
  MESSAGE(FATAL_ERROR "PyKDE4 not found")
ENDIF(NOT pykde_config)

STRING(REGEX REPLACE ".*\npykde_version:([^\n]+).*$" "\\1" PYKDE4_VERSION ${pykde_config})
STRING(REGEX REPLACE ".*\npykde_version_str:([^\n]+).*$" "\\1" PYKDE4_VERSION_STR ${pykde_config})
MESSAGE(STATUS "Found PyKDE4 version ${PYKDE4_VERSION_STR}")

FIND_PROGRAM(PYKDE4_PYKDEUIC_EXE pykdeuic4 PATHS)# ${PYKDE4_BIN_DIR})
IF(NOT PYKDE4_PYKDEUIC_EXE)
    MESSAGE(FATAL_ERROR "ERROR: Could not find pykdeuic4 (part of PyKDE4)")
ENDIF(NOT PYKDE4_PYKDEUIC_EXE)

###########################################################################
# This comes mostly from KDE's FindKDE4Internal.cmake

macro(_SET_FANCY _var _value _comment)
   set(predefinedvalue "${_value}")
   if ("${CMAKE_INSTALL_PREFIX}" STREQUAL "${KDE4_INSTALL_DIR}" AND DEFINED KDE4_${_var})
      set(predefinedvalue "${KDE4_${_var}}")
   endif ("${CMAKE_INSTALL_PREFIX}" STREQUAL "${KDE4_INSTALL_DIR}" AND DEFINED KDE4_${_var})

   if (NOT DEFINED ${_var})
      set(${_var} ${predefinedvalue})
   else (NOT DEFINED ${_var})
      set(${_var} "${${_var}}" CACHE PATH "${_comment}")
   endif (NOT DEFINED ${_var})
endmacro(_SET_FANCY)

if (WIN32)
# use relative install prefix to avoid hardcoded install pathes in cmake_install.cmake files
   _set_fancy(EXEC_INSTALL_PREFIX  ""                                        "Base directory for executables and libraries")
   _set_fancy(SHARE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}/share"           "Base directory for files which go to share/")
   _set_fancy(BIN_INSTALL_DIR      "bin"                                     "The install dir for executables (default ${EXEC_INSTALL_PREFIX}/bin)")
   _set_fancy(SBIN_INSTALL_DIR     "sbin"                                    "The install dir for system executables (default ${EXEC_INSTALL_PREFIX}/sbin)")
else (WIN32)
   _set_fancy(EXEC_INSTALL_PREFIX  "${CMAKE_INSTALL_PREFIX}"                 "Base directory for executables and libraries")
   _set_fancy(SHARE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}/share"           "Base directory for files which go to share/")
   _set_fancy(BIN_INSTALL_DIR      "${EXEC_INSTALL_PREFIX}/bin"              "The install dir for executables (default ${EXEC_INSTALL_PREFIX}/bin)")
   _set_fancy(SBIN_INSTALL_DIR     "${EXEC_INSTALL_PREFIX}/sbin"             "The install dir for system executables (default ${EXEC_INSTALL_PREFIX}/sbin)")
endif (WIN32)

_set_fancy(PLUGIN_INSTALL_DIR       "${LIB_INSTALL_DIR}/kde4"                "The subdirectory relative to the install prefix where plugins will be installed (default is ${LIB_INSTALL_DIR}/kde4)")
_set_fancy(CONFIG_INSTALL_DIR       "${SHARE_INSTALL_PREFIX}/config"         "The config file install dir")
_set_fancy(DATA_INSTALL_DIR         "${SHARE_INSTALL_PREFIX}/apps"           "The parent directory where applications can install their data")
_set_fancy(HTML_INSTALL_DIR         "${SHARE_INSTALL_PREFIX}/doc/HTML"       "The HTML install dir for documentation")
_set_fancy(ICON_INSTALL_DIR         "${SHARE_INSTALL_PREFIX}/icons"          "The icon install dir (default ${SHARE_INSTALL_PREFIX}/share/icons/)")
_set_fancy(KCFG_INSTALL_DIR         "${SHARE_INSTALL_PREFIX}/config.kcfg"    "The install dir for kconfig files")
_set_fancy(LOCALE_INSTALL_DIR       "${SHARE_INSTALL_PREFIX}/locale"         "The install dir for translations")
_set_fancy(MIME_INSTALL_DIR         "${SHARE_INSTALL_PREFIX}/mimelnk"        "The install dir for the mimetype desktop files")
_set_fancy(SERVICES_INSTALL_DIR     "${SHARE_INSTALL_PREFIX}/kde4/services"  "The install dir for service (desktop, protocol, ...) files")
_set_fancy(SERVICETYPES_INSTALL_DIR "${SHARE_INSTALL_PREFIX}/kde4/servicetypes" "The install dir for servicestypes desktop files")
_set_fancy(SOUND_INSTALL_DIR        "${SHARE_INSTALL_PREFIX}/sounds"         "The install dir for sound files")
_set_fancy(TEMPLATES_INSTALL_DIR    "${SHARE_INSTALL_PREFIX}/templates"      "The install dir for templates (Create new file...)")
_set_fancy(WALLPAPER_INSTALL_DIR    "${SHARE_INSTALL_PREFIX}/wallpapers"     "The install dir for wallpapers")
_set_fancy(KCONF_UPDATE_INSTALL_DIR "${DATA_INSTALL_DIR}/kconf_update"       "The kconf_update install dir")
# this one shouldn't be used anymore
_set_fancy(APPLNK_INSTALL_DIR       "${SHARE_INSTALL_PREFIX}/applnk"         "Is this still used ?")
_set_fancy(AUTOSTART_INSTALL_DIR    "${SHARE_INSTALL_PREFIX}/autostart"      "The install dir for autostart files")

_set_fancy(XDG_APPS_INSTALL_DIR     "${SHARE_INSTALL_PREFIX}/applications/kde4"         "The XDG apps dir")
_set_fancy(XDG_DIRECTORY_INSTALL_DIR "${SHARE_INSTALL_PREFIX}/desktop-directories"      "The XDG directory")
_set_fancy(XDG_MIME_INSTALL_DIR     "${SHARE_INSTALL_PREFIX}/mime/packages"  "The install dir for the xdg mimetypes")

_set_fancy(SYSCONF_INSTALL_DIR      "${CMAKE_INSTALL_PREFIX}/etc"            "The kde sysconfig install dir (default /etc)")
_set_fancy(MAN_INSTALL_DIR          "${CMAKE_INSTALL_PREFIX}/man"            "The kde man install dir (default ${CMAKE_INSTALL_PREFIX}/man/)")
_set_fancy(INFO_INSTALL_DIR         "${CMAKE_INSTALL_PREFIX}/info"           "The kde info install dir (default ${CMAKE_INSTALL_PREFIX}/info)")
_set_fancy(DBUS_INTERFACES_INSTALL_DIR      "${SHARE_INSTALL_PREFIX}/dbus-1/interfaces" "The kde dbus interfaces install dir (default  ${SHARE_INSTALL_PREFIX}/dbus-1/interfaces)")
_set_fancy(DBUS_SERVICES_INSTALL_DIR      "${SHARE_INSTALL_PREFIX}/dbus-1/services"     "The kde dbus services install dir (default  ${SHARE_INSTALL_PREFIX}/dbus-1/services)")

###########################################################################
# PYKDE4_INSTALL_PYTHON_FILES(file_name...)
#
# Installs and bytes compiles Python files into the data directory for this
# project..
#
MACRO(PYKDE4_INSTALL_PYTHON_FILES)

    ADD_CUSTOM_TARGET(pysupport ALL)
    FOREACH (_current_file ${ARGN})

        # Install the source file.
        INSTALL(FILES ${_current_file} DESTINATION ${DATA_INSTALL_DIR}/${PROJECT_NAME})

        # Byte compile and install the .pyc file.        
        GET_FILENAME_COMPONENT(_absfilename ${_current_file} ABSOLUTE)
        GET_FILENAME_COMPONENT(_filename ${_current_file} NAME)
        GET_FILENAME_COMPONENT(_filenamebase ${_current_file} NAME_WE)
        GET_FILENAME_COMPONENT(_basepath ${_current_file} PATH)
        SET(_bin_py ${CMAKE_BINARY_DIR}/${_basepath}/${_filename})
        SET(_bin_pyc ${CMAKE_BINARY_DIR}/${_basepath}/${_filenamebase}.pyc)

        FILE(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/${_basepath})

        SET(_message "-DMESSAGE=Byte-compiling ${_bin_py}")

        GET_FILENAME_COMPONENT(_abs_bin_py ${_bin_py} ABSOLUTE)
        IF(_abs_bin_py STREQUAL ${_absfilename})    # Don't copy the file onto itself.
            ADD_CUSTOM_COMMAND(
                TARGET pysupport
                COMMAND ${CMAKE_COMMAND} ${_message} -P ${CMAKE_SOURCE_DIR}/cmake/modules/print_status.cmake
                COMMAND ${PYTHON_EXECUTABLE} ${CMAKE_SOURCE_DIR}/cmake/modules/PythonCompile.py ${_bin_py}
                DEPENDS ${_absfilename}
            )
        ELSE(_abs_bin_py STREQUAL ${_absfilename})
            ADD_CUSTOM_COMMAND(
                TARGET pysupport
                COMMAND ${CMAKE_COMMAND} ${_message} -P ${CMAKE_SOURCE_DIR}/cmake/modules/print_status.cmake
                COMMAND ${CMAKE_COMMAND} -E copy ${_absfilename} ${_bin_py}
                COMMAND ${PYTHON_EXECUTABLE} ${CMAKE_SOURCE_DIR}/cmake/modules/PythonCompile.py ${_bin_py}
                DEPENDS ${_absfilename}
            )
        ENDIF(_abs_bin_py STREQUAL ${_absfilename})

        INSTALL(FILES ${_bin_pyc} DESTINATION ${DATA_INSTALL_DIR}/${PROJECT_NAME})

    ENDFOREACH (_current_file)
ENDMACRO(PYKDE4_INSTALL_PYTHON_FILES)

###########################################################################
# PYKDE4_ADD_UI_FILES(ui_file_name...)
#
# Compiles Qt4 designer files to Python and installs them into the data
# directory for this project.
#
MACRO(PYKDE4_ADD_UI_FILES)

    ADD_CUSTOM_TARGET(pysupport ALL)
    FOREACH (_current_file ${ARGN})

        # Convert to .py and byte compile.
        GET_FILENAME_COMPONENT(_absfilename ${_current_file} ABSOLUTE)
        GET_FILENAME_COMPONENT(_filename ${_current_file} NAME)
        GET_FILENAME_COMPONENT(_filenamebase ${_current_file} NAME_WE)
        GET_FILENAME_COMPONENT(_basepath ${_current_file} PATH)
        SET(_bin_py ${CMAKE_BINARY_DIR}/${_basepath}/${_filenamebase}_ui.py)
        SET(_bin_pyc ${CMAKE_BINARY_DIR}/${_basepath}/${_filenamebase}_ui.pyc)

        FILE(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/${_basepath})

        SET(_message "-DMESSAGE=Compiling UI file ${_current_file}")
        SET(_message2 "-DMESSAGE=Byte-compiling ${_bin_py}")

        ADD_CUSTOM_COMMAND(
            TARGET pysupport
            COMMAND ${CMAKE_COMMAND} ${_message} -P ${CMAKE_SOURCE_DIR}/cmake/modules/print_status.cmake
            COMMAND ${PYKDE4_PYKDEUIC_EXE} -o ${_bin_py} ${_absfilename}
            COMMAND ${CMAKE_COMMAND} ${_message2} -P ${CMAKE_SOURCE_DIR}/cmake/modules/print_status.cmake
            COMMAND ${PYTHON_EXECUTABLE} ${CMAKE_SOURCE_DIR}/cmake/modules/PythonCompile.py ${_bin_py}
            DEPENDS ${_absfilename}
        )
        INSTALL(FILES ${_bin_py} DESTINATION ${DATA_INSTALL_DIR}/${PROJECT_NAME})
        INSTALL(FILES ${_bin_pyc} DESTINATION ${DATA_INSTALL_DIR}/${PROJECT_NAME})

    ENDFOREACH (_current_file)
ENDMACRO(PYKDE4_ADD_UI_FILES)

###########################################################################
# PYKDE4_ADD_EXECUTABLE(py_name exe_name)
#
# Creates a smybolic link with name exe_name at install time from the
# install bin directory to the Python file. The Python file is also make
# executable.
#
MACRO(PYKDE4_ADD_EXECUTABLE _pyname _exename)
    INSTALL(CODE "EXECUTE_PROCESS(COMMAND ${CMAKE_COMMAND} -DTARGET=${DATA_INSTALL_DIR}/${PROJECT_NAME}/${_pyname} -DLINK_NAME=${BIN_INSTALL_DIR}/${_exename} -P ${CMAKE_SOURCE_DIR}/cmake/modules/create_exe_symlink.cmake)" )

ENDMACRO(PYKDE4_ADD_EXECUTABLE)
