# Find Python-Twisted
# ~~~~~~~~~~
# Copyright (c) 2010, Wolfgang Rohdewald <wolfgang@rohdewald.de>
# adapted from FindPyDBus.cmake in the project guidance-power-manager
# Redistribution and use is allowed according to the terms of the BSD license.
# For details see the accompanying COPYING-CMAKE-SCRIPTS file.
#
# Python Twisted website: http://www.twistedmatrix.com
#
# Find the installed version of Python Twisted

IF(TWISTED_FOUND)
  # Already in cache, be silent
  SET(TWISTED_FOUND TRUE)
ELSE(TWISTED_FOUND)

  GET_FILENAME_COMPONENT(_cmake_module_path ${CMAKE_CURRENT_LIST_FILE}  PATH)

  EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} ${_cmake_module_path}/FindTwisted.py OUTPUT_VARIABLE twisted)
  IF(twisted)
    SET(TWISTED_FOUND TRUE)
  ENDIF(twisted)

  IF(TWISTED_FOUND)
    IF(NOT TWISTED_FIND_QUIETLY)
      MESSAGE(STATUS "Found python-twisted")
    ENDIF(NOT TWISTED_FIND_QUIETLY)
  ELSE(TWISTED_FOUND)
    IF(TWISTED_FIND_REQUIRED)
      MESSAGE(FATAL_ERROR "Could not find python-twisted")
    ELSE(TWISTED_FIND_REQUIRED)
      MESSAGE(STATUS "did not Found python-twisted")
    ENDIF(TWISTED_FIND_REQUIRED)
  ENDIF(TWISTED_FOUND)

ENDIF(TWISTED_FOUND)
