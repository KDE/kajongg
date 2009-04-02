# - FindPyQt4
#
#
INCLUDE (FindPythonInterp)

EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} ${CMAKE_SOURCE_DIR}/cmake/modules/FindPyQt4.py OUTPUT_VARIABLE pyqt_config)
IF(NOT pyqt_config)
  # Failure to run
  MESSAGE(FATAL_ERROR "PyQt4 not found")
ENDIF(NOT pyqt_config)

STRING(REGEX REPLACE "^pyqt_bin_dir:([^\n]+).*$" "\\1" PYQT4_BIN_DIR ${pyqt_config})
STRING(REGEX REPLACE ".*\npyqt_config_args:([^\n]+).*$" "\\1" PYQT4_CONFIG_ARGS ${pyqt_config})
STRING(REGEX REPLACE ".*\npyqt_mod_dir:([^\n]+).*$" "\\1" PYQT4_MOD_DIR ${pyqt_config})
STRING(REGEX REPLACE ".*\npyqt_modules:([^\n]+).*$" "\\1" PYQT4_MODULES ${pyqt_config})
STRING(REGEX REPLACE ".*\npyqt_sip_dir:([^\n]+).*$" "\\1" PYQT4_SIP_DIR ${pyqt_config})
STRING(REGEX REPLACE ".*\npyqt_sip_flags:([^\n]+).*$" "\\1" PYQT4_SIP_FLAGS ${pyqt_config})
STRING(REGEX REPLACE ".*\npyqt_version:([^\n]+).*$" "\\1" PYQT4_VERSION ${pyqt_config})
STRING(REGEX REPLACE ".*\npyqt_version_str:([^\n]+).*$" "\\1" PYQT4_VERSION_STR ${pyqt_config})
MESSAGE(STATUS "Found PyQt4 version ${PYQT4_VERSION_STR}")

FIND_PROGRAM(PYQT4_PYUIC_EXE pyuic4 PATHS ${PYQT4_BIN_DIR})
IF(NOT PYQT4_PYUIC_EXE)
    MESSAGE(FATAL_ERROR "ERROR: Could not find PyQt4 pyuic4")
ENDIF(NOT PYQT4_PYUIC_EXE)

MACRO(PYQT4_ADD_UI_FILES)

    ADD_CUSTOM_TARGET(pysupport ALL)
    FOREACH (_current_FILE ${ARGN})

        # Convert to .py and byte compile.
        GET_FILENAME_COMPONENT(_absfilename ${_current_FILE} ABSOLUTE)
        GET_FILENAME_COMPONENT(_filename ${_absfilename} NAME)
        GET_FILENAME_COMPONENT(_filenamebase ${_absfilename} NAME_WE)
        GET_FILENAME_COMPONENT(_basepath ${_absfilename} PATH)
        SET(_bin_py ${CMAKE_BINARY_DIR}/${_basepath}/${_filenamebase}_ui.py)
        SET(_bin_pyc ${CMAKE_BINARY_DIR}/${_basepath}/${_filenamebase}_ui.pyc)

        FILE(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/${_basepath})
        ADD_CUSTOM_COMMAND(
            TARGET pysupport
            COMMAND ${PYQT4_PYUIC_EXE} -o ${_bin_py} ${_absfilename}
            COMMAND ${PYTHON_EXECUTABLE} ${CMAKE_SOURCE_DIR}/cmake/modules/PythonCompile.py ${_bin_py}
            DEPENDS ${_absfilename}
        )
        INSTALL(FILES ${_bin_py} DESTINATION ${CMAKE_INSTALL_PREFIX}/share/apps/${PROJECT_NAME})
        INSTALL(FILES ${_bin_pyc} DESTINATION ${CMAKE_INSTALL_PREFIX}/share/apps/${PROJECT_NAME})

    ENDFOREACH (_current_FILE)
ENDMACRO(PYQT4_ADD_UI_FILES)
