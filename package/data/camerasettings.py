"""
Camera Settings and Configuration

Defines camera types, imaging systems, and atomic properties for JKam.
Contains configuration for simulated cameras and rubidium atom properties.
"""

import numpy as np
from package.drivers.grasshopperdriver import GrasshopperDriver
from package.drivers.andordriver import AndorDriver
from package.drivers.simulatedcamdriver import SimulatedCamDriver


class GrasshopperCamera:
    @property
    def driver(self):
        """Lazy instantiation of driver to avoid QEventLoop issues"""
        if not hasattr(self, '_driver'):
            self._driver = GrasshopperDriver()
        return self._driver
    
    pixel_area = 6.45e-6**2
    quantum_efficiency = 0.6
    adu_conversion = 1
    bit_conversion = 1
    total_gain = bit_conversion * adu_conversion * quantum_efficiency


class AndorCamera:
    @property
    def driver(self):
        """Lazy instantiation of driver to avoid QEventLoop issues"""
        if not hasattr(self, '_driver'):
            self._driver = AndorDriver()
        return self._driver
    
    pixel_area = 5e-6 ** 2
    quantum_efficiency = 1
    adu_conversion = 1
    bit_conversion = 1
    total_gain = bit_conversion * adu_conversion * quantum_efficiency


class SimulatedCamera:
    """
    Simulated camera configuration for testing and development.
    
    Provides a virtual camera interface with configurable properties
    for testing the JKam application without physical hardware.
    """
    @property
    def driver(self):
        """Lazy instantiation of driver to avoid QEventLoop issues"""
        if not hasattr(self, '_driver'):
            self._driver = SimulatedCamDriver()
        return self._driver
    
    pixel_area = 5e-6 ** 2
    quantum_efficiency = 1
    adu_conversion = 1
    bit_conversion = 1
    total_gain = bit_conversion * adu_conversion * quantum_efficiency


class SideImagingSystem:
    name = 'Side Imaging'
    # camera_serial_number = '18431942'
    camera_serial_number = '17491535'
    camera_type = GrasshopperCamera()
    magnification = 0.77


class MOTImagingSystem:
    name = 'MOT Imaging'
    camera_serial_number = '18431941'
    camera_type = GrasshopperCamera()
    magnification = 0.36


class SpareGrasshopper:
    name = 'Spare Grasshopper'
    # camera_serial_number = '17491535'
    camera_serial_number = '18431942'
    camera_type = GrasshopperCamera()
    magnification = 1  # Not Applicable


class HighNASystem:
    name = 'High NA Imaging'
    camera_serial_number = 'VSC-12091'
    camera_type = AndorCamera()
    magnification = 50


class SimulatedCameraSystem:
    """
    Simulated camera imaging system for testing.
    
    Provides a complete imaging system configuration using the
    simulated camera driver for development and testing purposes.
    """
    name = 'Simulated Camera System'
    camera_serial_number = 'simcam8675309'
    camera_type = SimulatedCamera()
    magnification = 1


class RbAtom:
    """
    Rubidium-87 atom properties for absorption imaging calculations.
    
    Contains physical constants for the D2 transition used in
    absorption imaging analysis and atom number calculations.
    """
    cross_section = 2.907e-13  # m^2 - Steck Rubidium 87 D Line Data
    linewidth = 2 * np.pi * 6.07e6  # Hz -  Steck Rubidium 87 D Line Data
    saturation_intensity = 1.67 * 1e4 / 1e3  # W/m^2 - Steck Rubidium 87 D Line Data, convert mW/cm^2 to W/m^2
    transition_freq = 2 * np.pi * 384.230e12  # Hz - D2 Transition


imaging_system_list = [SideImagingSystem(), MOTImagingSystem(), HighNASystem(),
                       SpareGrasshopper(), SimulatedCameraSystem()]

# imaging_system_list = [SimulatedCameraSystem()] # TESTING ONLY
