# Format and install gettext messages
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Copyright (c) 2008, Simon Edwards <simon@simonzone.com>
# Redistribution and use is allowed according to the terms of the BSD license.
# For details see the accompanying COPYING-CMAKE-SCRIPTS file.
#
# This file defines the following macro:
#
# GETTEXT_INSTALL_MESSAGES ([CATALOG_NAME <catalog name>] [PO_DIRECTORY <directory>])
#     Formats and install gettext messages. CATALOG_NAME optional and defaults
#     to the project name and can be used to set a different name for the
#     message catalogs when installed. PO_DIRECTORY is optional and defaults
#     to the "po" directory, and can be set to specify a different directory
#     containing .po files.

SET(GETTEXTMSGFMT_FOUND 0)

FIND_PROGRAM(GETTEXT_MSGFMT_EXECUTABLE msgfmt)
IF(NOT GETTEXT_MSGFMT_EXECUTABLE)
    MESSAGE(
"------
    NOTE: msgfmt not found. Translations will *not* be installed
------")
ELSE(NOT GETTEXT_MSGFMT_EXECUTABLE)
    SET(GETTEXTMSGFMT_FOUND 1)
    MESSAGE(STATUS "Found gettext msgfmt: ${GETTEXT_MSGFMT_EXECUTABLE}")
ENDIF(NOT GETTEXT_MSGFMT_EXECUTABLE)
    
MACRO(GETTEXT_INSTALL_MESSAGES)
    SET(_po_directory po)
    SET(_catalog_name ${PROJECT_NAME})
    SET(_action "")
    FOREACH(_arg ${ARGN})
        IF ("${_arg}" STREQUAL "CATALOG_NAME")
            SET(_action "CATALOG_NAME")
        ELSEIF ("${_arg}" STREQUAL "PO_DIRECTORY")
            SET(_action "PO_DIRECTORY")
        ELSE ("${_arg}" STREQUAL "CATALOG_NAME")
            IF (${_action} STREQUAL "CATALOG_NAME")
                SET(_catalog_name "${_arg}")
            ELSEIF (${_action} STREQUAL "PO_DIRECTORY")
                SET(_po_directory "${_arg}")
            ENDIF (${_action} STREQUAL "CATALOG_NAME")
        ENDIF ("${_arg}" STREQUAL "CATALOG_NAME")
    ENDFOREACH(_arg ${ARGN})

    ADD_CUSTOM_TARGET(translations ALL)

    FILE(GLOB PO_FILES ${_po_directory}/*.po)
        
    FOREACH(_poFile ${PO_FILES})
        GET_FILENAME_COMPONENT(_lang ${_poFile} NAME_WE)
        SET(_gmoFile ${CMAKE_CURRENT_BINARY_DIR}/${_lang}.gmo)
        ADD_CUSTOM_COMMAND(TARGET translations
            COMMAND ${GETTEXT_MSGFMT_EXECUTABLE} --check -o ${_gmoFile} ${_poFile}
            DEPENDS ${_poFile})
        INSTALL(FILES ${_gmoFile} DESTINATION ${LOCALE_INSTALL_DIR}/${_lang}/LC_MESSAGES/ RENAME ${_catalog_name}.mo)
    ENDFOREACH(_poFile ${PO_FILES})
 
ENDMACRO(GETTEXT_INSTALL_MESSAGES)
