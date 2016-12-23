# Find PyQt5
# ~~~~~~~~~~
# Copyright (c) 2007-2008, Simon Edwards <simon@simonzone.com>
# Redistribution and use is allowed according to the terms of the BSD license.
# For details see the accompanying COPYING-CMAKE-SCRIPTS file.
#
# PyQt5 website: http://www.riverbankcomputing.co.uk/pyqt/index.php
#
# Find the installed version of PyQt5. FindPyQt5 should only be called after
# Python has been found.
#
# This file defines the following variables, which can also be overriden by
# users:
#
# PYQT5_VERSION - The version of PyQt5 found expressed as a 6 digit hex number
#     suitable for comparison as a string
#
# PYQT5_VERSION_STR - The version of PyQt5 as a human readable string.
#
# PYQT5_VERSION_TAG - The Qt5 version tag used by PyQt's sip files.
#
# PYQT5_SIP_DIR - The directory holding the PyQt5 .sip files. This can be unset
# if PyQt5 was built using its new build system and pyqtconfig.py is not
# present on the system, as in this case its value cannot be determined
# automatically.
#
# PYQT5_SIP_FLAGS - The SIP flags used to build PyQt.

IF(EXISTS PYQT5_VERSION)
  # Already in cache, be silent
  SET(PYQT5_FOUND TRUE)
ELSE(EXISTS PYQT5_VERSION)

  FIND_FILE(_find_pyqt_py FindPyQt5.py PATHS ${CMAKE_MODULE_PATH})

  EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} ${_find_pyqt_py} OUTPUT_VARIABLE pyqt_config)
  IF(pyqt_config)
    STRING(REGEX MATCH "^pyqt_version:([^\n]+).*$" _dummy ${pyqt_config})
    SET(PYQT5_VERSION "${CMAKE_MATCH_1}" CACHE STRING "PyQt5's version as a 6-digit hexadecimal number")

    STRING(REGEX MATCH ".*\npyqt_version_str:([^\n]+).*$" _dummy ${pyqt_config})
    SET(PYQT5_VERSION_STR "${CMAKE_MATCH_1}" CACHE STRING "PyQt5's version as a human-readable string")

    STRING(REGEX MATCH ".*\npyqt_version_tag:([^\n]+).*$" _dummy ${pyqt_config})
    SET(PYQT5_VERSION_TAG "${CMAKE_MATCH_1}" CACHE STRING "The Qt5 version tag used by PyQt5's .sip files")

#    STRING(REGEX MATCH ".*\npyqt_sip_dir:([^\n]+).*$" _dummy ${pyqt_config})
#    SET(PYQT5_SIP_DIR "${CMAKE_MATCH_1}" CACHE PATH "The base directory where PyQt5's .sip files are installed")

    STRING(REGEX MATCH ".*\npyqt_sip_flags:([^\n]+).*$" _dummy ${pyqt_config})
    SET(PYQT5_SIP_FLAGS "${CMAKE_MATCH_1}" CACHE STRING "The SIP flags used to build PyQt5")

#    IF(NOT IS_DIRECTORY "${PYQT5_SIP_DIR}")
#      MESSAGE(WARNING "The base directory where PyQt5's SIP files are installed could not be determined. This usually means PyQt5 was built with its new build system and pyqtconfig.py is not present.\n"
#                      "Please set the PYQT5_SIP_DIR variable manually.")
#    ELSE(NOT IS_DIRECTORY "${PYQT5_SIP_DIR}")
     SET(PYQT5_FOUND TRUE)
#    ENDIF(NOT IS_DIRECTORY "${PYQT5_SIP_DIR}")
  ENDIF(pyqt_config)

  IF(PYQT5_FOUND)
    IF(NOT PYQT5_FIND_QUIETLY)
      MESSAGE(STATUS "Found PyQt5 version: ${PYQT5_VERSION_STR}")
    ENDIF(NOT PYQT5_FIND_QUIETLY)
  ELSE(PYQT5_FOUND)
    IF(PYQT5_FIND_REQUIRED)
      MESSAGE(FATAL_ERROR "Could not find Python")
    ENDIF(PYQT5_FIND_REQUIRED)
  ENDIF(PYQT5_FOUND)

ENDIF(EXISTS PYQT5_VERSION)
