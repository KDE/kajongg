# A simple 'dist' target for creating a source tarball
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Copyright (c) 2008, Simon Edwards <simon@simonzone.com>
# Redistribution and use is allowed according to the terms of the BSD license.
# For details see the accompanying COPYING-CMAKE-SCRIPTS file.
#
# This file defines the following macros:
#
# SOURCE_DIST (base_source_directory [file glob1, file glob2, ...])
#     Generates a 'dist' target which creates a tar.bz2 file containing the
#     specified files. Each file glob is recursively expanded in the
#     base_source_directory. Any matched files will be part of the tar.bz2
#     file. Files inside .svn directories, or which are backup files or other
#     temporary files are automatically excluded.base_source_directory is
#     typically set to ${CMAKE_SOURCE_DIR}. Note that the list of files to
#     include in the tar.bz2 file is determined when cmake is run, not when
#     'make dist' is run.
#
# Note: This macro assumes GNU tar.

INCLUDE(FindUnixCommands)

MACRO(SOURCE_DIST BASE_DIR)
   
    SET(SOURCE_DIST_FILES)
    FOREACH (_arg ${ARGN})
        FILE(GLOB_RECURSE _files RELATIVE ${BASE_DIR} ${_arg})
        
        IF("${_files}" STREQUAL "")
            MESSAGE("Warning: Parameter '${_arg}' to macro SOURCE_DIST didn't match any files.")
        ELSE("${_files}" STREQUAL "")
        
        FOREACH (_x ${_files})
            GET_FILENAME_COMPONENT(name ${_x} NAME)
            SET(exclude_path_regex "/\\.svn/")
            SET(exclude_name_regex "^.*(\\.pyc)|~|(\\.bak)$")
            IF(${_x} MATCHES ${exclude_path_regex})
            ELSE(${_x} MATCHES ${exclude_path_regex})
                IF(${name} MATCHES ${exclude_name_regex})
                ELSE(${name} MATCHES ${exclude_name_regex})  
                    LIST(APPEND SOURCE_DIST_FILES ${_x})
                ENDIF(${name} MATCHES ${exclude_name_regex})
            ENDIF(${_x} MATCHES ${exclude_path_regex})
        ENDFOREACH (_x ${_files})
        
        ENDIF("${_files}" STREQUAL "")
    ENDFOREACH(_arg ${ARGN})

    ADD_CUSTOM_TARGET(dist COMMAND ${TAR} --transform=s,^,${PROJECT_NAME}-${PROGRAM_VERSION}/, -jcf ${CMAKE_BINARY_DIR}/${PROJECT_NAME}-${PROGRAM_VERSION}.tar.bz2 ${SOURCE_DIST_FILES} COMMAND ls -l ${CMAKE_BINARY_DIR}/${PROJECT_NAME}-${PROGRAM_VERSION}.tar.bz2 WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})
    MESSAGE(STATUS "Added 'dist' target")
ENDMACRO(SOURCE_DIST BASE_DIR)
