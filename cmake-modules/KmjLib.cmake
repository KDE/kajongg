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
            COMMAND ${CMAKE_COMMAND} ${_message} -P ${CMAKE_SOURCE_DIR}/cmake-modules/print_status.cmake
            COMMAND ${PYKDE4_PYKDEUIC_EXE} -o ${_bin_py} ${_absfilename}
            COMMAND ${CMAKE_COMMAND} ${_message2} -P ${CMAKE_SOURCE_DIR}/cmake-modules/print_status.cmake
            COMMAND ${PYTHON_EXECUTABLE} PythonCompile.py ${_bin_py}
            DEPENDS ${_absfilename}
        )
        INSTALL(FILES ${_bin_py} DESTINATION ${DATA_INSTALL_DIR}/${PROJECT_NAME})
        INSTALL(FILES ${_bin_pyc} DESTINATION ${DATA_INSTALL_DIR}/${PROJECT_NAME})

    ENDFOREACH (_current_file)
ENDMACRO(PYKDE4_ADD_UI_FILES)
