import numpy as np
from package.drivers.grasshopperdriver import GrasshopperDriver
from package.drivers.andordriver import AndorDriver
from package.drivers.simulatedcamdriver import SimulatedCamDriver


class GrasshopperCamera:
    driver = GrasshopperDriver()
    pixel_area = 6.45e-6**2
    quantum_efficiency = 0.38  # Number of electrons per photon
    adu_conversion = 1 / 0.37  # Number of digital counts per electron, ADU/e-
    bit_conversion = 2**-8  # 16 bit camera output is converted to 8 bits before data is captured
    total_gain = bit_conversion * adu_conversion * quantum_efficiency  # Number of recoreded digital counts per photon


class AndorCamera:
    driver = AndorDriver()
    pixel_area = 6.5e-6**2
    quantum_efficiency = 0.58  # Number of electrons per photon

    # Number of digital counts per electron, ADU/e-
    # See Sec. 2.4 in manual: Dual Amplifier Dynamic Range
    adu_conversion_12_high_well = 1 / 7.5  # 12-bit (high well capacity) mode
    adu_conversion_12_low_noise = 1 / 0.28  # 12-bit (low noise) mode
    adu_conversion_16 = 1 / 0.45  # 16-bit (low noise and high well capacity)
    adu_conversion = adu_conversion_12_low_noise  # Number of digital counts per electron

    bit_conversion = 2**0  # No truncation or padding
    total_gain = bit_conversion * adu_conversion * quantum_efficiency  # Number of recoreded digital counts per photon


class SimulatedCamera:
    driver = SimulatedCamDriver()
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
    name = 'Simulated Camera System'
    camera_serial_number = 'simcam8675309'
    camera_type = SimulatedCamera()
    magnification = 1


class RbAtom:
    cross_section = 2.907e-13  # m^2 - Steck Rubidium 87 D Line Data
    linewidth = 2 * np.pi * 6.07e6  # Hz -  Steck Rubidium 87 D Line Data
    saturation_intensity = 1.67 * 1e4 / 1e3  # W/m^2 - Steck Rubidium 87 D Line Data, convert mW/cm^2 to W/m^2
    transition_freq = 2 * np.pi * 384.230e12  # Hz - D2 Transition


imaging_system_list = [SideImagingSystem(), MOTImagingSystem(), HighNASystem(),
                       SpareGrasshopper(), SimulatedCameraSystem()]
