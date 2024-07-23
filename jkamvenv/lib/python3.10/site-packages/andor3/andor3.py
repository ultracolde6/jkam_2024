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

__all__ = ["Andor3"]

import os
import platform
import typing
import logging
from ctypes import cdll, byref, c_int, c_longlong, c_double, c_wchar_p, c_void_p, POINTER, CFUNCTYPE, create_unicode_buffer
from ctypes.util import find_library

import numpy as np

from . constants import *
from . error import *
from . utils import *


_log = logging.getLogger(__name__)
"""Logging output for use by this module."""

# ctypes callback type (return type, argument types...)
_CALLBACK_FUNC = CFUNCTYPE(c_int, c_int, c_wchar_p, POINTER(c_longlong))

class Andor3():
    """
    Initialise the Andor SDK3 and attempt to open a connection to a camera.

    If ``device_index`` is None, camera initialisation won't be attempted, however the number of
    cameras attached may be queried with :data:`~Andor3.device_count`, and a camera subsequently opened
    with :meth:`open`.
    
    :param device_index: Index (zero-based) of attached camera to open.
    """

    def __init__(self, device_index:int=0):

        self.camera_handle = AT_HANDLE.UNINITIALISED
        """The "camera handle" used by the SDK to identify the currently opened camera."""

        self.software_version = ""
        """Version number of the SDK3 library in use."""

        self.device_count = 0
        """Number of detected cameras attached to the system."""

        # Andor3 library only exists for Linux or Windows
        self._dll = None
        """Reference to the python ctypes library in use."""
        if platform.system() == "Windows":
            libname = "atcore.dll"
        elif platform.system() == "Linux":
            libname = "libatcore.so.3"
        else:
            raise EnvironmentError("Did not detect a Windows or Linux operating system!")

        # Find and load the Andor library
        dll_path = None
        try:
            # Use system installed library if available
            _log.debug(f"Searching for Andor3 library in system paths...")
            self._dll = cdll.LoadLibrary(libname)
            dll_path = os.path.dirname(find_library(libname))
        except:
            pass
        
        # If that didn't work, try some other common locations
        if self._dll is None and platform.system() == "Windows":
            for loc in (os.path.join(os.environ["ProgramFiles"], "Andor SDK3"),
                        os.path.join(os.environ["ProgramFiles"], "Andor Driver Pack 3"),
                        os.path.join(os.environ["ProgramFiles"], "Andor SOLIS"),
                        os.path.join(os.environ["ProgramFiles"], "National Instruments", "LabVIEW")):
                try:
                    _log.debug(f"Searching for Andor3 library in {loc}...")
                    self._dll = cdll.LoadLibrary(os.path.join(loc, libname))
                    # If that worked, add location to path so atcore.dll can find the other dlls it needs.
                    os.environ["PATH"] = f"{os.environ['PATH']}{os.pathsep}{loc}"
                    dll_path = loc
                    break
                except:
                    pass
        
        # Check current directory
        if self._dll is None:
            try:
                loc = os.path.abspath(".")
                _log.debug(f"Searching for Andor3 library in {loc}...")
                self._dll = cdll.LoadLibrary(os.path.join(loc, libname))
                # Don't need to add to paths on Windows (atcore.dll must search in current dir)
                # On Linux, maybe need to add to LD_LIBRARY_PATH or something?
                dll_path = loc
            except:
                pass
        
        # Hopefully we found the library somewhere!
        if self._dll is None:
            raise RuntimeError(f"Couldn't find the Andor3 shared library '{libname}'")
        _log.info(f"Initialising Andor3 library found at {dll_path}{os.sep}{libname}...")
        
        # Initialise library
        error = self._dll.AT_InitialiseLibrary()
        if not error == AT_ERR.SUCCESS:
            raise AndorError(error)
        
        # Get SDK version number
        software_version = create_unicode_buffer(STRING_BUFFER_SIZE)
        error = self._dll.AT_GetString(AT_HANDLE.SYSTEM, "SoftwareVersion", byref(software_version))
        if not error == AT_ERR.SUCCESS:
            self._dll.AT_FinaliseLibrary()
            raise AndorError(error)
        self.software_version = software_version.value
        _log.debug(f"Andor3 library version {self.software_version}")


        # Get device count
        if device_index is None: device_index = -1
        device_count = c_int()
        error = self._dll.AT_GetInt(AT_HANDLE.SYSTEM, "DeviceCount", byref(device_count))
        if not error == AT_ERR.SUCCESS:
            self._dll.AT_FinaliseLibrary()
            raise AndorError(error)
        if device_count.value < 1 or device_index + 1 > device_count.value:
            # Raise error if no cameras found, or not enough cameras
            self._dll.AT_FinaliseLibrary()
            raise AndorError(AT_ERR.DEVICENOTFOUND)
        self.device_count = device_count.value
        _log.debug(f"Detected {self.device_count} device{'s' if self.device_count > 1 else ''}")

        # If a device_index is given, attempt to open the camera
        if device_index >= 0:
            try:
                self.open(device_index)
            except:
                self._dll.AT_FinaliseLibrary()
                raise
        
        # Our own record of registered feature callbacks
        self._callbacks = dict()

        # Block of memory for image buffer(s)
        self._image_buffer = None
        # Properties of images at the time the image buffer was created
        self._image_properties = None

    def open(self, device_index:int=0) -> None:
        """
        Open an attached camera device by its numerical device index.

        :param device_index: Index (zero-based) of the camera to open.
        """
        # Close any currently open camera
        self.close()
        # Attempt open of new camera
        _log.debug(f"Opening connection to camera #{device_index}...")
        camera_handle = c_int()
        error = self._dll.AT_Open(device_index, byref(camera_handle))
        if not error == AT_ERR.SUCCESS:
            raise AndorError(error)
        self.camera_handle = camera_handle.value
        _log.debug(f"Camera assigned handle {self.camera_handle}")


    def close(self) -> None:
        """
        Close any currently opened camera.
        """
        if not self.camera_handle == AT_HANDLE.UNINITIALISED:
            error = self._dll.AT_Close(self.camera_handle)
            if not error == AT_ERR.SUCCESS:
                raise AndorError(error)
            self.camera_handle = AT_HANDLE.UNINITIALISED
            _log.debug("Closed connection to camera")

    def __del__(self):
        try:
            self._dll.AT_Close(self.camera_handle)
        except: pass
        try:
            self._dll.AT_FinaliseLibrary()
        except: pass

    def isImplemented(self, feature: str) -> bool:
        """
        Check if the given feature is implemented on the currently opened camera.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: ``True`` if feature is implemented, or ``False`` otherwise.
        """
        result = c_int()
        error = self._dll.AT_IsImplemented(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return bool(result.value)
    
    def isReadable(self, feature: str) -> bool:
        """
        Check if the given feature is currently readable.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: ``True`` if feature is readable, or ``False`` otherwise.
        """
        result = c_int()
        error = self._dll.AT_IsReadable(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return bool(result.value)
    
    def isWritable(self, feature: str) -> bool:
        """
        Check if the given feature is currently writable.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: ``True`` if feature is writable, or ``False`` otherwise.
        """
        result = c_int()
        error = self._dll.AT_IsWritable(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return bool(result.value)
    
    def isReadOnly(self, feature: str) -> bool:
        """
        Check if the given feature is read-only.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: ``True`` if feature is read-only, or ``False`` otherwise.
        """
        result = c_int()
        error = self._dll.AT_IsReadOnly(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return bool(result.value)

    def setInt(self, feature: str, value: int) -> None:
        """
        Set the value for a given integer feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :param value: New value for the feature.
        """
        error = self._dll.AT_SetInt(self.camera_handle, feature, c_longlong(value))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
    
    def getInt(self, feature: str) -> int:
        """
        Get the value for a given integer feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: Value for the feature.
        """
        result = c_longlong()
        error = self._dll.AT_GetInt(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value
    
    def getIntMin(self, feature: str) -> int:
        """
        Get the minimum allowed value for a given integer feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: Minimum allowed value for the feature.
        """
        result = c_longlong()
        error = self._dll.AT_GetIntMin(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value

    def getIntMax(self, feature: str) -> int:
        """
        Get the maximum allowed value for a given integer feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: Maximum allowed value for the feature.
        """
        result = c_longlong()
        error = self._dll.AT_GetIntMax(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value

    def setFloat(self, feature: str, value: float) -> None:
        """
        Set the value for a given floating point number feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :param value: New value for the feature.
        """
        error = self._dll.AT_SetFloat(self.camera_handle, feature, c_double(value))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
    
    def getFloat(self, feature: str) -> float:
        """
        Get the value for a given floating point number feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: Value for the feature.
        """
        result = c_double()
        error = self._dll.AT_GetFloat(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value
    
    def getFloatMin(self, feature: str) -> float:
        """
        Get the minimum allowed value for a given floating point number feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: Minimum allowed value for the feature.
        """
        result = c_double()
        error = self._dll.AT_GetFloatMin(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value

    def getFloatMax(self, feature: str) -> float:
        """
        Get the maximum allowed value for a given floating point number feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: Maximum allowed value for the feature.
        """
        result = c_double()
        error = self._dll.AT_GetFloatMax(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value

    def setBool(self, feature: str, value: bool) -> None:
        """
        Set the value for a given boolean feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :param value: New value for the feature.
        """
        error = self._dll.AT_SetBool(self.camera_handle, feature, c_int(value))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
    
    def getBool(self, feature: str) -> bool:
        """
        Get the value for a given boolean feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: Value for the feature.
        """
        result = c_int()
        error = self._dll.AT_GetBool(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return bool(result.value)
    
    def setEnumIndex(self, feature: str, value: int) -> None:
        """
        Set the value for a given enumerated type feature by its numerical index.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.

        Use :meth:`getEnumCount` to determine the maximum value allowed for the enumeration index.
        The methods :meth`isEnumIndexImplemented` and :meth:`isEnumIndexAvailable` can be used to check
        if the value is implemented for the current camera model, and whether the camera is currently in a mode
        where the value is able to be selected.
        The string describing the option corresponding to the enumeration index can be obtained using
        :meth:`getEnumStringByIndex`.
        
        :param feature: String describing the camera feature.
        :param value: New value for the feature.
        """
        error = self._dll.AT_SetEnumIndex(self.camera_handle, feature, c_int(value))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
    
    def setEnumString(self, feature: str, value: str) -> None:
        """
        Set the value for a given enumerated type feature using its string representation.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.

        The string describing the option corresponding to an enumeration index can be obtained using
        :meth:`getEnumStringByIndex`.

        :param feature: String describing the camera feature.
        :param value: New value for the feature.
        """
        error = self._dll.AT_SetEnumString(self.camera_handle, feature, value)
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
    
    def getEnumIndex(self, feature: str) -> int:
        """
        Get the numerical index value for a given enumerated type feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.

        To obtain the value in the form of its description string, use
        ``cam.getEnumStringByIndex(feature, cam.getEnumIndex(feature))``.

        :param feature: String describing the camera feature.
        :returns: Value for the feature.
        """
        result = c_int()
        error = self._dll.AT_GetEnumIndex(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value
    
    def getEnumCount(self, feature: str) -> int:
        """
        Get the number of possible values available to an enumerated type feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.

        The methods :meth`isEnumIndexImplemented` and :meth:`isEnumIndexAvailable` can be used to check
        if a value is implemented for the current camera model, and whether the camera is currently in a mode
        where the value is able to be selected.
        The string describing the option corresponding to the enumeration index can be obtained using
        :meth:`getEnumStringByIndex`.

        :param feature: String describing the camera feature.
        :returns: Maximum value for the feature.
        """
        result = c_int()
        error = self._dll.AT_GetEnumCount(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value
    
    def isEnumIndexAvailable(self, feature: str, index: int) -> bool:
        """
        Determine if a given value for an enumeration type feature is currently available to be selected.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.

        Use :meth:`getEnumCount` to determine the maximum value allowed for the enumeration index.
        The method :meth`isEnumIndexImplemented` can be used to check if the value is implemented
        for the current camera model.
        The string describing the option corresponding to the enumeration index can be obtained using
        :meth:`getEnumStringByIndex`.

        :param feature: String describing the camera feature.
        :param index: Index of enumeration for the feature.
        :returns: Boolean describing if the value for the feature is currently available.
        """
        result = c_int()
        error = self._dll.AT_IsEnumIndexAvailable(self.camera_handle, feature, index, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return bool(result.value)
    
    def isEnumIndexImplemented(self, feature: str, index: int) -> bool:
        """
        Determine if a given value for an enumeration type feature is implemented for the current camera.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.

        The method :meth:`isEnumIndexAvailable` can be used to check if the camera is currently in a mode
        where the value is able to be selected.
        The string describing the option corresponding to the enumeration index can be obtained using
        :meth:`getEnumStringByIndex`.

        :param feature: String describing the camera feature.
        :param index: Index of enumeration for the feature.
        :returns: Boolean describing if the value for the feature is implemented for the camera.
        """
        result = c_int()
        error = self._dll.AT_IsEnumIndexImplemented(self.camera_handle, feature, index, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return bool(result.value)
    
    def getEnumStringByIndex(self, feature: str, index: int) -> str:
        """
        Get the string representation corresponding to the enumeration-type feature's numerical index.

        :param feature: String describing the camera feature.
        :param index: Index of enumeration for the feature.
        :returns: String describing the enumeration index.
        """
        result = create_unicode_buffer(STRING_BUFFER_SIZE)
        error = self._dll.AT_GetEnumStringByIndex(self.camera_handle, feature, index, byref(result), STRING_BUFFER_SIZE)
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value
    
    def command(self, feature: str) -> None:
        """
        Activate a command type camera feature.

        A command is a camera feature which takes no parameters, for example ``"AcquisitionStart"``, or ``"SoftwareTrigger"``.

        :param feature: String describing the camera feature.
        """
        error = self._dll.AT_Command(self.camera_handle, feature)
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
    
    def setString(self, feature: str, value: str) -> None:
        """
        Set the value for a given string type feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.

        :param feature: String describing the camera feature.
        :param value: New value for the feature.
        """
        error = self._dll.AT_SetString(self.camera_handle, feature, value)
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
    
    def getString(self, feature: str) -> str:
        """
        Get the value for a given string feature.

        See the :data:`~andor3.constants.FEATURES` dictionary for possible ``feature`` values.
        
        :param feature: String describing the camera feature.
        :returns: Value for the feature.
        """
        result = create_unicode_buffer(STRING_BUFFER_SIZE)
        error = self._dll.AT_GetString(self.camera_handle, feature, byref(result), STRING_BUFFER_SIZE)
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value

    def getStringMaxLength(self, feature: str) -> int:
        """
        Get the maximum possible string length for a string-type feature's values.

        :param feature: String describing the camera feature.
        :returns: Maximum string length for feature values.
        """
        result = c_int()
        error = self._dll.AT_GetStringMaxLength(self.camera_handle, feature, byref(result))
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return result.value
    
    # I think the Andor library ends up calling the callback function twice when triggered, it's not my fault!
    def registerFeatureCallback(self, feature: str, callback: typing.Callable, args:tuple=(), kwargs:dict={}) -> None:
        """
        Register a method to call when the selected event occurs.

        The Andor library will call the callback immediately so that the callback handler can
        perform any action on the initial value etc.
        However, I think the Andor library ends up calling the callback function twice when
        triggered which is likely a bug.

        :param feature: String describing the feature event.
        :param callback: Method to call when event occurs.
        :param args: Tuple of positional arguments to pass to ``callback``.
        :param kwargs: Dictionary of keyword arguments to pass to ``callback``.
        """
        # Keys for callback dict are the hash of the tuple of (feature, callback)
        # This means can't use the same feature and function with different calling parameters though.
        # Would we ever want to do that? Maybe. Would instead need to make a unique identifier and return it.
        key = hash((feature, callback))
        if key not in self._callbacks:
            # Make a ctypes wrapper function to pass to the Andor library
            cfunc = _CALLBACK_FUNC(self._feature_callback)
            # We could assume that nothing in the Andor libraries would try to dereference our void pointer,
            # then could just pass the key as is. But to be safe, we'll make a real c_longlong of the key and keep it around.
            ckey = c_longlong(key)
            # Add everything to our dict of callbacks
            self._callbacks[key] = (cfunc, ckey, feature, callback, args, kwargs)
            # Register with Andor library.
            # Note that callback will be called immediately once.
            error = self._dll.AT_RegisterFeatureCallback(self.camera_handle, feature, cfunc, byref(ckey))
            if not error == AT_ERR.SUCCESS:
                self._callbacks.pop(key)
                raise AndorError(error)
        else:
            _log.warning(f"Feature callback for \"{feature}\" already registered to the function \"{callback}\"")
        
    def _feature_callback(self, handle, feature, key_pointer):
        # Dereference the pointer to the c_longlong and get it's value
        key = key_pointer.contents.value
        # Grab everything from our callback dict
        _, _, feature, callback, args, kwargs = self._callbacks[key]
        # Could actually check the camera handle is the one we are currently using
        # and that the feature strings match what we expect. They're probably fine...
        # Call the requested python function and pass given parameters
        callback(*args, **kwargs)
        return 0

    def unregisterFeatureCallback(self, feature: str, callback:typing.Callable) -> None:
        """
        Unregister a previously registered callback method.

        The ``callback`` must have been previously registered to the ``feature`` using
        :meth:`registerFeatureCallback`.

        :param feature: String describing the feature event.
        :param callback: Method previously registered for callbacks.
        """
        # Generate dict key
        key = hash((feature, callback))
        if key in self._callbacks:
            # Grab everything from our callback dict and remove the entry
            cfunc, ckey, feature, callback, _, _ = self._callbacks.pop(key)
            # Unregister with Andor library.
            error = self._dll.AT_UnregisterFeatureCallback(self.camera_handle, feature, cfunc, byref(ckey))
            if not error == AT_ERR.SUCCESS:
                raise AndorError(error)
        else:
            _log.warning(f"Feature callback for \"{feature}\" was not registered to the function \"{callback}\"")

    def queueBuffer(self, count:int=1) -> None:
        """
        Prepare a memory buffer for image storage by the Andor SDK3.

        Note that any previously prepared buffers will be destroyed.
        The Buffer sizes are created to match the currently set image size and bit depth, so the
        image settings should be configured prior to buffer creation.

        Multiple buffers may be prepared in a single call by using the ``count`` parameter.

        :param count: Number of buffers to prepare.
        """
        # First, clear any existing buffer
        self.flush()
        self._image_buffer = None
        self._image_properties = None
        # Andor library wants the buffers to be aligned to 8-byte memory locations.
        # I think numpy does this anyway, but can enforce it with some array slicing.
        # Image size includes optional metadata
        imgsize = self.getInt("ImageSizeBytes")        
        # Padding required at end of image to make imgsize a multiple of 8
        postpad = (8 - imgsize%8)%8
        # Allocate a buffer big enough so can offset if needed
        buffer_size = count*(imgsize + postpad) + 8
        _log.debug(f"Allocating {buffer_size} bytes for image buffers.")
        buffer = np.empty(buffer_size, dtype=np.uint8)
        # Offset from start of buffer to enforce 8 byte alignment
        offset = -buffer.ctypes.data%8
        self._image_buffer = buffer[offset:offset + count*(imgsize + postpad)]
        # Queue up the buffer(s) in the Andor library
        for p in range(self._image_buffer.ctypes.data, self._image_buffer.ctypes.data + self._image_buffer.size, imgsize + postpad):
            error = self._dll.AT_QueueBuffer(self.camera_handle, c_void_p(p), imgsize)
            if not error == AT_ERR.SUCCESS:
                self._image_buffer = None
                self._image_properties = None
                raise AndorError(error)
        # Get the current image properties, which can be used for decoding the raw image data later
        self._image_properties = {
            "metadata" : self.MetadataEnable,
            #"metadata_frame_info" : self.MetadataFrameInfo,
            "metadata_timestamp" : self.MetadataTimestamp,
            "metadata_frame" : self.MetadataFrame,
            "encoding" : self.PixelEncoding[1],
            "size" : imgsize,
            "width" : self.AOIWidth,
            "height" : self.AOIHeight,
            "stride" : self.AOIStride
        }

    def waitBuffer(self, timeout:int=INFINITY, copy:bool=False, requeue:bool=False) -> np.ndarray:
        """
        Wait for the Andor SDK3 to fill a previously prepared memory buffer and return the data.

        The ``timeout`` parameter specifies how long to wait (in milliseconds) for the buffer to
        be filled.
        A value of :data:`~andor3.constants.INFINITY` will wait indefinitely, while a value of zero
        will return immediately if there is no buffer currently filled with new image data.

        Setting the ``copy=True`` parameter will make a copy of the data from the memory buffer,
        otherwise only a reference to the buffer memory will be used. Copying is slower (and uses
        more memory), but may be useful if the memory buffer is at risk of being overwritten by
        new data, for example if ``requeue=True`` is set, or :meth:`queueBuffer` is called to
        create a new buffer space.

        Setting the ``requeue=True`` parameter will allow the Andor SDK3 to re-use the buffer space
        in a circular-buffer type arrangement.
        It's may be a good idea to also set ``copy=True`` to ensure the data isn't overwritten by
        the camera before it's used.

        The raw data is returned as a 1-dimensional numpy array of bytes (uint8).

        :param timeout: Timeout (in milliseconds).
        :param copy: Copy the image data instead of returning a reference.
        :param requeue: Re-queue the image buffer for use again.
        :returns: 1-dimensional numpy array of raw image data.
        """
        data_pointer = c_void_p()
        data_size = c_int()
        error = self._dll.AT_WaitBuffer(self.camera_handle, byref(data_pointer), byref(data_size), timeout)
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
        # Compute slice indices
        start_i = data_pointer.value - self._image_buffer.ctypes.data
        stop_i = start_i + data_size.value
        # Get slice from image buffer
        data = self._image_buffer[start_i:stop_i]
        if copy:
            # Copy data out of buffer before it is requeued and the memory potentially overwritten
            data = data.copy()
        # Requeue the same buffer space if requested.
        if requeue:
            error = self._dll.AT_QueueBuffer(self.camera_handle, data_pointer, data_size)
            if not error == AT_ERR.SUCCESS: raise AndorError(error)
        return data
    
    def flush(self):
        """
        Destroy any existing image buffers.
        """
        self._image_buffer = None
        error = self._dll.AT_Flush(self.camera_handle)
        if not error == AT_ERR.SUCCESS: raise AndorError(error)

    def get_feature(self, feature:str, errors="warn"):
        """
        Queries the value of a camera ``feature``, without needing to know the particular data type.

        Internally, calls the appropriate :meth:`getBool`, :meth:`getInt`, :meth:`getFloat`,
        :meth:`getString` or :meth:`getEnumIndex`/:meth:`getEnumStringByIndex` for ``feature`` and returns the value.
        Enum types return a tuple of (index, string).

        See :data:`~andor3.constants.FEATURES` for a list of camera features.

        By default any errors when querying the value are warned about (``errors="warn"``).
        To instead raise exceptions, set ``errors="raise"``.
        To silence errors completely, set ``errors="ignore"``.
        If a value is unable to be queried and errors are ignored, ``None`` will be returned.

        :param feature: String matching the camera feature to query.
        :param errors: Action to take on errors, either ``ignore``, ``warn``, or ``raise``.
        :returns: Value of the requested feature.
        """
        result = None
        try:
            if feature not in FEATURES:
                raise RuntimeError(f"Unknown feature '{feature}'.")
            if FEATURES[feature] in ("Command", "Event"):
                # Commands don't have values.
                # Events, although documented as integer types, are only used to register callbacks.
                raise RuntimeError(f"Attempted to get the value of a '{FEATURES[feature]}' feature type '{feature}'.")
            elif FEATURES[feature] == "Boolean":
                result = self.getBool(feature)
            elif FEATURES[feature] == "Integer":
                result = self.getInt(feature)
            elif FEATURES[feature] == "Floating Point":
                result = self.getFloat(feature)
            elif FEATURES[feature] == "String":
                result = self.getString(feature)
            elif FEATURES[feature] == "Enumerated":
                index = self.getEnumIndex(feature)
                string = self.getEnumStringByIndex(feature, index)
                result = (index, string)
            else:
                # If we get here there's probably a typo in the FEATURES dictionary...
                raise RuntimeError(f"Unknown data type '{FEATURES[feature]}' for the feature '{feature}'.")
        except Exception as ex:
            if errors == "warn":
                _log.warning(f"Unable to get value of '{feature}': {ex}")
            elif errors == "raise":
                raise
        return result

    def set_feature(self, feature:str, value, errors="warn"):
        """
        Sets the value of a camera ``feature``, without needing to know the particular data type.

        Internally, calls the appropriate ``setBool``, ``setInt``, ``setFloat``, ``setString`` or ``setEnum`` for ``feature``.
        Enum types may be set using either the index or string representation.

        See :data:`~andor3.constants.FEATURES` for a list of camera features.

        By default any errors when setting the value are warned about (``errors="warn"``).
        To instead raise exceptions, set ``errors="raise"``.
        To silence errors completely, set ``errors="ignore"``.
        If a value is unable to be set and errors are ignored, ``None`` will be returned.

        :param feature: String matching the camera feature to set.
        :param value: New value of the feature to set.
        :param errors: Action to take on errors, either ``ignore``, ``warn``, or ``raise``.
        """
        try:
            if feature not in FEATURES:
                raise RuntimeError(f"Unknown feature '{feature}'.")
            if FEATURES[feature] == "Command":
                # Setting a command isn't really correct, but we'll allow it (ignoring the given value)
                self.command(feature)
            elif FEATURES[feature] == "Event":
                # Can't set a value for a feature.
                raise RuntimeError(f"Attempted to set the value of a '{FEATURES[feature]}' feature type '{feature}'.")
            elif FEATURES[feature] == "Boolean":
                self.setBool(feature, bool(value))
            elif FEATURES[feature] == "Integer":
                self.setInt(feature, int(value))
            elif FEATURES[feature] == "Floating Point":
                self.setFloat(feature, float(value))
            elif FEATURES[feature] == "String":
                self.setString(feature, str(value))
            elif FEATURES[feature] == "Enumerated":
                if type(value) == int:
                    self.setEnumIndex(feature, value)
                else:
                    self.setEnumString(feature, str(value))
        except Exception as ex:
            if errors == "warn":
                _log.warning(f"Unable to set value of '{feature}': {ex}")
            elif errors == "raise":
                raise

    def __getattr__(self, name):
        """
        Intercept ``__getattr__`` calls for class properties which match valid camera features.

        Allows the use of feature names as class properties, for example ``t = cam.ExposureTime``.
        """
        if name in FEATURES:
            return self.get_feature(name)
        else:
            raise AttributeError(f"Attempt to get invalid property '{name}' for Andor3.")

    def __setattr__(self, name, value):
        """
        Intercept __setattr__ calls for class properties which match valid camera features.

        Allows the use of feature names as class properties, for example ``cam.ExposureTime = 0.1``.
        """
        if name in FEATURES:
            self.set_feature(name, value)
        else:
            super().__setattr__(name, value)

    def start(self):
        """
        A shortcut for calling ``cam.command("AcquisitionStart")``.
        """
        error = self._dll.AT_Command(self.camera_handle, "AcquisitionStart")
        if not error == AT_ERR.SUCCESS: raise AndorError(error)
    
    def stop(self):
        """
        A shortcut for calling ``cam.command("AcquisitionStop")``.

        Any errors will be ignored (for example, if the camera is already stopped).
        """
        _ = self._dll.AT_Command(self.camera_handle, "AcquisitionStop")

    def min(self, feature:str, errors="warn"):
        """
        Queries the minimum allowed value of a camera ``feature``, without needing to know the particular data type.

        Internally, calls the appropriate ``getIntMin`` or ``getFloatMin`` for ``feature`` and returns the value.

        See :data:`~andor3.constants.FEATURES` for a list of camera features.

        By default any errors when querying the value are warned about (``errors="warn"``).
        To instead raise exceptions, set ``errors="raise"``.
        To silence errors completely, set ``errors="ignore"``.
        If a value is unable to be queried and errors are ignored, ``None`` will be returned.

        :param feature: String matching the camera feature to query.
        :param errors: Action to take on errors, either ``ignore``, ``warn``, or ``raise``.
        :returns: Minimum allowed value of the requested feature.
        """
        result = None
        try:
            if feature not in FEATURES:
                raise RuntimeError(f"Unknown feature '{feature}'.")
            if FEATURES[feature] in ("Command", "Event", "Boolean", "String", "Enumerated"):
                # These don't have minimum values.
                raise RuntimeError(f"Attempted to get the minimum of a '{FEATURES[feature]}' feature type '{feature}'.")
            elif FEATURES[feature] == "Integer":
                result = self.getIntMin(feature)
            elif FEATURES[feature] == "Floating Point":
                result = self.getFloatMin(feature)
            else:
                # If we get here there's probably a typo in the FEATURES dictionary...
                raise RuntimeError(f"Unknown data type '{FEATURES[feature]}' for the feature '{feature}'.")
        except Exception as ex:
            if errors == "warn":
                _log.warning(f"Unable to get minimum of '{feature}': {ex}")
            elif errors == "raise":
                raise
        return result

    def max(self, feature:str, errors="warn"):
        """
        Queries the maximum allowed value of a camera `feature`, without needing to know the particular data type.

        Internally, calls the appropriate ``getIntMax`` or ``getFloatMax`` for ``feature`` and returns the value.

        See :data:`~andor3.constants.FEATURES` for a list of camera features.

        By default any errors when querying the value are warned about (``errors="warn"``).
        To instead raise exceptions, set ``errors="raise"``.
        To silence errors completely, set ``errors="ignore"``.
        If a value is unable to be queried and errors are ignored, ``None`` will be returned.

        :param feature: String matching the camera feature to query.
        :param errors: Action to take on errors, either ``ignore``, ``warn``, or ``raise``.
        :returns: Maximum allowed value of the requested feature.
        """
        result = None
        try:
            if feature not in FEATURES:
                raise RuntimeError(f"Unknown feature '{feature}'.")
            if FEATURES[feature] in ("Command", "Event", "Boolean", "String", "Enumerated"):
                # These don't have maximum values.
                raise RuntimeError(f"Attempted to get the maximum of a '{FEATURES[feature]}' feature type '{feature}'.")
            elif FEATURES[feature] == "Integer":
                result = self.getIntMax(feature)
            elif FEATURES[feature] == "Floating Point":
                result = self.getFloatMax(feature)
            else:
                # If we get here there's probably a typo in the FEATURES dictionary...
                raise RuntimeError(f"Unknown data type '{FEATURES[feature]}' for the feature '{feature}'.")
        except Exception as ex:
            if errors == "warn":
                _log.warning(f"Unable to get maximum of '{feature}': {ex}")
            elif errors == "raise":
                raise
        return result

    @property
    def features(self):
        """
        A list of feature names available to the currently opened camera.
        """
        return [f for f in FEATURES if self.isImplemented(f)]        

    def describe_features(self):
        """
        Generate a string representation of all available camera features and their values.
        """
        s = ""
        for feature, datatype in FEATURES.items():
            if self.isImplemented(feature):
                s += (f"{feature}: "
                    f"{datatype} "
                    f"({'r' if self.isReadable(feature) else '-'}"
                    f"{'w' if self.isWritable(feature) else '-'})\n") 
                if datatype in ("Integer", "Floating Point"):
                    s += (f"  value={self.get_feature(feature):g} "
                        f"min={self.min(feature):g} "
                        f"max={self.max(feature):g}\n")
                elif datatype == "Boolean":
                    s += (f"  value={self.get_feature(feature)}\n")
                elif datatype == "String":
                    s += (f"  value=\"{self.get_feature(feature)}\"\n")
                elif datatype == "Enumerated":
                    for i in range(self.getEnumCount(feature)):
                        if self.isEnumIndexImplemented(feature, i):
                            selected_mark = "->" if self.getEnumIndex(feature) == i else "  "
                            available_mark = ":" if self.isEnumIndexAvailable(feature, i) else "x"
                            s += (f"  {selected_mark} {i:2} {available_mark} {self.getEnumStringByIndex(feature, i)}\n")
        return s.rstrip("\n")

    def decode_image(self, data_raw):
        """
        Decode an image from the raw data byte stream.

        A tuple of the decoded image and timestamp will be returned.
        If metadata is not present, the timestamp will be zero.

        :param data_raw: Raw image byte data, with optional metadata.
        :returns: Tuple of image and timestamp.
        """
        timestamp = 0
        if self._image_properties["metadata"] and self._image_properties["metadata_timestamp"]:
            # Extract timestamp from metadata
            md, data_raw = decode_metadata(data_raw)
            if "timestamp" in md:
                timestamp = md["timestamp"]
        return decode_image_data(
            data_raw=data_raw,
            encoding=self._image_properties["encoding"],
            width=self._image_properties["width"],
            height=self._image_properties["height"],
            stride=self._image_properties["stride"]), timestamp
