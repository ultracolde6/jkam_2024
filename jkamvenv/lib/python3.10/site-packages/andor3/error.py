# Copyright 2021 Patrick C. Tapping
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Error code definitions and exception class for dealing with errors reported from the Andor SDK.
"""

__all__ = ["AndorError", "AT_ERR"]

from enum import IntEnum

class AndorError(RuntimeError):
    """
    Exception used to indicate an error returned by the Andor SDK3.

    :param error_code: Numerical error code used by the Andor SDK3.
    """

    def __init__(self, error_code):
        self.code = error_code
        self.name = AT_ERR(self.code).name
        self.description = AT_ERR(error_code).description
    
    def __str__(self):
        return f"AT_ERR_{self.name} ({self.code}): {self.description}"


class AT_ERR(IntEnum):
    """
    Enumeration listing the valid Andor SDK3 numerical error codes.
    """
    SUCCESS = 0
    NOTINITIALISED = 1
    NOTIMPLEMENTED = 2
    READONLY = 3
    NOTREADABLE = 4
    NOTWRITABLE = 5
    OUTOFRANGE = 6
    INDEXNOTAVAILABLE = 7
    INDEXNOTIMPLEMENTED = 8
    EXCEEDEDMAXSTRINGLENGTH = 9
    CONNECTION = 10
    NODATA = 11
    INVALIDHANDLE = 12
    TIMEDOUT = 13
    BUFFERFULL = 14
    INVALIDSIZE = 15
    INVALIDALIGNMENT = 16
    COMM = 17
    STRINGNOTAVAILABLE = 18
    STRINGNOTIMPLEMENTED = 19
    NULL_FEATURE = 20
    NULL_HANDLE = 21
    NULL_IMPLEMENTED_VAR = 22
    NULL_READABLE_VAR = 23
    NULL_READONLY_VAR = 24
    NULL_WRITABLE_VAR = 25
    NULL_MINVALUE = 26
    NULL_MAXVALUE = 27
    NULL_VALUE = 28
    NULL_STRING = 29
    NULL_COUNT_VAR = 30
    NULL_ISAVAILABLE_VAR = 31
    NULL_MAXSTRINGLENGTH = 32
    NULL_EVCALLBACK = 33
    NULL_QUEUE_PTR = 34
    NULL_WAIT_PTR = 35
    NULL_PTRSIZE = 36
    NOMEMORY = 37
    DEVICEINUSE = 38
    DEVICENOTFOUND = 39
    HARDWARE_OVERFLOW = 100

    @property
    def description(self):
        """
        Return a string describing the error code.
        """
        return {
            AT_ERR.SUCCESS : "Function call was successful",
            AT_ERR.NOTINITIALISED : "Function called with an uninitialized handle",
            AT_ERR.NOTIMPLEMENTED : "Feature has not been implemented for the chosen camera",
            AT_ERR.READONLY : "Feature is read only",
            AT_ERR.NOTREADABLE : "Feature is currently not readable",
            AT_ERR.NOTWRITABLE : "Feature is currently not writable",
            AT_ERR.OUTOFRANGE : "Value is outside the maximum and minimum limits",
            AT_ERR.INDEXNOTAVAILABLE : "Index is currently not available",
            AT_ERR.INDEXNOTIMPLEMENTED : "Index is not implemented for the chosen camera",
            AT_ERR.EXCEEDEDMAXSTRINGLENGTH : "String value provided exceeds the maximum allowed length",
            AT_ERR.CONNECTION : "Error connecting to or disconnecting from hardware",
            AT_ERR.NODATA : "No Internal Event or Internal Error",
            AT_ERR.INVALIDHANDLE : "Invalid device handle passed to function",
            AT_ERR.TIMEDOUT : "The waitBuffer function timed out while waiting for data arrive in output queue",
            AT_ERR.BUFFERFULL : "The input queue has reached its capacity",
            AT_ERR.INVALIDSIZE : "The size of a queued buffer did not match the frame size",
            AT_ERR.INVALIDALIGNMENT : "A queued buffer was not aligned on an 8-byte boundary",
            AT_ERR.COMM : "An error has occurred while communicating with hardware",
            AT_ERR.STRINGNOTAVAILABLE : "Index / String is not available",
            AT_ERR.STRINGNOTIMPLEMENTED : "Index / String is not implemented for the chosen camera",
            AT_ERR.NULL_FEATURE : "NULL feature name passed to function",
            AT_ERR.NULL_HANDLE : "Null device handle passed to function",
            AT_ERR.NULL_IMPLEMENTED_VAR : "Feature not implemented",
            AT_ERR.NULL_READABLE_VAR : "Readable not set",
            AT_ERR.NULL_READONLY_VAR : "Read-only",
            AT_ERR.NULL_WRITABLE_VAR : "Writable not set",
            AT_ERR.NULL_MINVALUE : "NULL min value",
            AT_ERR.NULL_MAXVALUE : "NULL max value",
            AT_ERR.NULL_VALUE : "NULL value returned from function",
            AT_ERR.NULL_STRING : "NULL string returned from function",
            AT_ERR.NULL_COUNT_VAR : "NULL feature count",
            AT_ERR.NULL_ISAVAILABLE_VAR : "Available not set",
            AT_ERR.NULL_MAXSTRINGLENGTH : "Max string length is NULL",
            AT_ERR.NULL_EVCALLBACK : "EvCallBack parameter is NULL",
            AT_ERR.NULL_QUEUE_PTR : "Pointer to queue is NULL",
            AT_ERR.NULL_WAIT_PTR : "Wait pointer is NULL",
            AT_ERR.NULL_PTRSIZE : "Pointer size is NULL",
            AT_ERR.NOMEMORY : "No memory has been allocated for the current action",
            AT_ERR.DEVICEINUSE : "Function failed to connect to a device because it is already being used",
            AT_ERR.DEVICENOTFOUND : "Device not found",
            AT_ERR.HARDWARE_OVERFLOW : "The software was not able to retrieve data from the card or camera fast enough to avoid the internal hardware buffer bursting."
        }[self.value]
