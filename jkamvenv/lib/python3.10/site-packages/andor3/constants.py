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
Definitions of special values, feature strings, and camera handles used by the Andor SDK.
"""

__all__ = ["STRING_BUFFER_SIZE", "INFINITY", "FEATURES", "AT_HANDLE"]

from enum import IntEnum


# Maximum size of strings sent/returned
STRING_BUFFER_SIZE = 1024
"""Buffer size to use when sending or receiving strings from the camera."""

# Infinite timeout when waiting on image buffer
INFINITY = 0xFFFFFFFF
"""Value to indicate an infinite timeout value when waiting on an image buffer."""

# Dictionary of features and their corresponding data type
FEATURES = {
    "AccumulateCount": "Integer",
    "AcquiredCount": "Integer",
    "AcquisitionStart": "Command",
    "AcquisitionStop": "Command",
    "AlternatingReadoutDirection": "Boolean",
    "AOIBinning": "Enumerated",
    "AOIHBin": "Integer",
    "AOIHeight": "Integer",
    "AOILayout": "Enumerated",
    "AOILeft": "Integer",
    "AOIStride": "Integer",
    "AOITop": "Integer",
    "AOIVBin": "Integer",
    "AOIWidth": "Integer",
    "AuxiliaryOutSource": "Enumerated",
    "AuxOutSourceTwo": "Enumerated",
    "BackoffTemperatureOffset": "Floating Point",
    "Baseline": "Integer",
    "BitDepth": "Enumerated",
    "BufferOverflowEvent": "Event",
    "BytesPerPixel": "Floating Point",
    "CameraAcquiring": "Boolean",
    "CameraDump": "Command",
    "CameraFamily": "String",
    "CameraMemory": "Integer",
    "CameraModel": "String",
    "CameraName": "String",
    "CameraPresent": "Boolean",
    "ColourFilter": "Enumerated",
    "ControllerID": "String",
    "CoolerPower": "Floating Point",
    "CycleMode": "Enumerated",
    "DDGIOCEnable": "Boolean",
    "DDGIOCNumberOfPulses": "Integer",
    "DDGIOCPeriod": "Integer",
    "DDGOutputDelay": "Integer",
    "DDGOutputEnable": "Boolean",
    "DDGOutputStepEnable": "Boolean",
    "DDGOpticalWidthEnable": "Boolean",
    "DDGOutputPolarity": "Enumerated",
    "DDGOutputSelector": "Enumerated",
    "DDGOutputWidth": "Integer",
    "DDGStepCount": "Integer",
    "DDGStepDelayCoefficientA": "Floating Point",
    "DDGStepDelayCoefficientB": "Floating Point",
    "DDGStepDelayMode": "Enumerated",
    "DDGStepEnabled": "Boolean",
    "DDGStepUploadProgress": "Integer",
    "DDGStepUploadRequired": "Boolean",
    "DDGStepWidthCoefficientA": "Floating Point",
    "DDGStepWidthCoefficientB": "Floating Point",
    "DDGStepWidthMode": "Enumerated",
    "DDGStepUploadModeValues": "Command",
    "DDR2Type": "String",
    "DeviceCount": "Integer",
    "DeviceVideoIndex": "Integer",
    "DisableShutter": "Boolean",
    "DriverVersion": "String",
    "ElectronicShutteringMode": "Enumerated",
    "EventEnable": "Boolean",
    "EventsMissedEvent": "Event",
    "EventSelector": "Enumerated",
    "ExposedPixelHeight": "Integer",
    "ExposureTime": "Floating Point",
    "ExposureEndEvent": "Event",
    "ExposureStartEvent": "Event",
    "ExternalIOReadout": "Boolean",
    "ExternalTriggerDelay": "Floating Point",
    "FanSpeed": "Enumerated",
    "FastAOIFrameRateEnable": "Boolean",
    "FirmwareVersion": "String",
    "ForceShutterOpen": "Boolean",
    "FrameCount": "Integer",
    "FrameInterval": "Floating Point",
    "FrameIntervalTiming": "Boolean",
    "FrameRate": "Floating Point",
    "FullAOIControl": "Boolean",
    "GateMode": "Enumerated",
    "HeatSinkTemperature": "Floating Point",
    "I2CAddress": "Integer",
    "I2CByte": "Integer",
    "I2CByteCount": "Integer",
    "I2CByteSelector": "Integer",
    "I2CRead": "Command",
    "I2CWrite": "Command",
    "ImageSizeBytes": "Integer",
    "InputVoltage": "Floating Point",
    "InsertionDelay": "Enumerated",
    "InterfaceType": "String",
    "IOControl": "Enumerated",
    "IODirection": "Enumerated",
    "IOState": "Boolean",
    "IOInvert": "Boolean",
    "IOSelector": "Enumerated",
    "IRPreFlashEnable": "Boolean",
    "KeepCleanEnable": "Boolean",
    "KeepCleanPostExposureEnable": "Boolean",
    "LineScanSpeed": "Floating Point",
    "LUTIndex": "Integer",
    "LUTValue": "Integer",
    "MaxInterfaceTransferRate": "Floating Point",
    "MCPGain": "Integer",
    "MCPIntelligate": "Boolean",
    "MCPVoltage": "Integer",
    "MetadataEnable": "Boolean",
    "MetadataFrame": "Boolean",
    "MetadataFrameInfo": "Boolean", # Not in documentation, indicates whether frame info is contained in metadata.
    "MetadataTimestamp": "Boolean",
    "MicrocodeVersion": "String",
    "MultitrackBinned": "Boolean",
    "MultitrackCount": "Integer",
    "MultitrackEnd": "Integer",
    "MultitrackSelector": "Integer",
    "MultitrackStart": "Integer",
    "Overlap": "Boolean",
    "PIVEnable": "Boolean",
    "PixelCorrection": "Boolean", # Documentation says Enumerated on SimCam only, but implemented on Zyla and returns a boolean.
    "PixelEncoding": "Enumerated",
    "PixelHeight": "Floating Point",
    "PixelReadoutRate": "Enumerated",
    "PixelWidth": "Floating Point",
    "PortSelector": "Integer",
    "PreAmpGain": "Enumerated",
    "PreAmpGainChannel": "Enumerated",
    "PreAmpGainControl": "Enumerated",
    "PreAmpGainValue": "Integer",
    "PreAmpGainSelector": "Enumerated",
    "PreAmpOffsetValue": "Integer",
    "PreTriggerEnable": "Boolean",
    "ReadoutTime": "Floating Point",
    "RollingShutterGlobalClear": "Boolean",
    "RowNExposureEndEvent": "Event",
    "RowNExposureStartEvent": "Event",
    "RowReadTime": "Floating Point",
    "ScanSpeedControlEnable": "Boolean",
    "SensorCooling": "Boolean",
    "SensorHeight": "Integer",
    "SensorModel": "String",
    "SensorReadoutMode": "Enumerated",
    "SensorType": "String",  # Documentation says Enumerated on Apogee only, but implemented on Zyla and returns a string.
    "SensorTemperature": "Floating Point",
    "SensorWidth": "Integer",
    "SerialNumber": "String",
    "ShutterAmpControl": "Boolean",
    "ShutterMode": "Enumerated",
    "ShutterOutputMode": "Enumerated",
    "ShutterState": "Boolean",
    "ShutterStrobePeriod": "Floating Point",
    "ShutterStrobePosition": "Floating Point",
    "ShutterTransferTime": "Floating Point",
    "SimplePreAmpGainControl": "Enumerated",
    "SoftwareTrigger": "Command",
    "SoftwareVersion": "String",
    "SpuriousNoiseFilter": "Boolean",
    "StaticBlemishCorrection": "Boolean",
    "SynchronousTriggering": "Boolean",
    "TargetSensorTemperature": "Floating Point",
    "TemperatureControl": "Enumerated",
    "TemperatureStatus": "Enumerated",
    "TimestampClock": "Integer",
    "TimestampClockFrequency": "Integer",
    "TimestampClockReset": "Command",
    "TransmitFrames": "Boolean",
    "TriggerMode": "Enumerated",
    "UsbProductId": "Integer",
    "UsbDeviceId": "Integer",
    "VerticallyCentreAOI": "Boolean"
}
"""
Dictionary containing valid camera feature strings and their corresponding data type.
"""


class AT_HANDLE(IntEnum):
    """
    Enumeration of special camera handle values used by the Andor SDK3.
    """
    UNINITIALISED = -1
    SYSTEM = 1