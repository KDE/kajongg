# A hack to add support for Python projects.
#
# This files contains the following macros:
#
# PYTHON_ADD_FILES
# PYTHON_ADD_UI_FILES
#
# Simon Edwards <simon@simonzone.com>

INCLUDE (FindPythonInterp)

MACRO(PYTHON_ADD_FILES)

    ADD_CUSTOM_TARGET(pysupport ALL)
    FOREACH (_current_FILE ${ARGN})

        # Install the source file.
        INSTALL(FILES ${_current_FILE} DESTINATION ${CMAKE_INSTALL_PREFIX}/share/apps/${PROJECT_NAME})

        # Byte compile and install the .pyc file.        
        GET_FILENAME_COMPONENT(_absfilename ${_current_FILE} ABSOLUTE)
        GET_FILENAME_COMPONENT(_filename ${_absfilename} NAME)
        GET_FILENAME_COMPONENT(_filenamebase ${_absfilename} NAME_WE)
        GET_FILENAME_COMPONENT(_basepath ${_absfilename} PATH)
        SET(_bin_py ${CMAKE_BINARY_DIR}/${_basepath}/${_filename})
        SET(_bin_pyc ${CMAKE_BINARY_DIR}/${_basepath}/${_filenamebase}.pyc)

        FILE(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/${_basepath})
        ADD_CUSTOM_COMMAND(
            TARGET pysupport
            COMMAND ${CMAKE_COMMAND} -E copy ${_absfilename} ${_bin_py}
            COMMAND ${PYTHON_EXECUTABLE} ${CMAKE_SOURCE_DIR}/cmake/modules/PythonCompile.py ${_bin_py}
            DEPENDS ${_absfilename}
        )
        INSTALL(FILES ${_bin_pyc} DESTINATION ${CMAKE_INSTALL_PREFIX}/share/apps/${PROJECT_NAME})

    ENDFOREACH (_current_FILE)
ENDMACRO(PYTHON_ADD_FILES)
