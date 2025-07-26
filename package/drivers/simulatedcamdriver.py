import numpy as np
from enum import Enum
from PyQt5.QtCore import QThread, pyqtSignal, QObject, QEventLoop
from package.drivers.jkamgendriver import JKamGenDriver
import datetime


class TriggerMode(Enum):
    TRIGGERING = 0
    CONTINUOUS = 1


class SimulatedCameraVideoTriggerer(QThread):
    def __init__(self, cam, driver):
        super(SimulatedCameraVideoTriggerer, self).__init__()
        self.cam = cam
        self.driver = driver

    def run(self):
        while self.driver.acquiring and not self.isInterruptionRequested():
            self.cam.trigger()
            self.msleep(20)  # Use msleep instead of wait


def gaussian_2d(x, y, x0=0, y0=0, sx=1, sy=1, amp=1.0, offset=0):
    rx = x - x0
    ry = y - y0
    return amp * np.exp(-(1/2) * ((rx/sx)**2 + ((ry/sy)**2))) + offset


class SimulatedCamera(QObject):
    trigger_signal = pyqtSignal()
    start_continuous_signal = pyqtSignal()
    stop_continuous_signal = pyqtSignal()
    frame_ready_signal = pyqtSignal()

    def __init__(self, driver):
        super(SimulatedCamera, self).__init__()
        self.driver = driver
        self.frame = None
        self.frame_ready = False
        
        # Create thread and move to it
        self.thread = QThread()
        self.moveToThread(self.thread)
        self.thread.start()
        
        # Connect signals after moving to thread
        self.trigger_signal.connect(self.trigger)
        
        # Create the continuous triggerer without parent to avoid cross-thread issues
        self.continuous_triggerer = SimulatedCameraVideoTriggerer(self, self.driver)
        self.start_continuous_signal.connect(self.continuous_triggerer.start)
        self.stop_continuous_signal.connect(self.continuous_triggerer.quit)
        
        self.x_coord_array, self.y_coord_array = np.mgrid[-50:50:100j, -50:50:100j]
        self.exposure_time = 10

    def trigger(self):
        curr_time = datetime.datetime.now()
        sx = 20 * np.sin((2 * np.pi / 5) * (curr_time.second + 1e-6*curr_time.microsecond)) + 25
        sy = 15 * np.sin((2 * np.pi / 5) * (curr_time.second + 1e-6*curr_time.microsecond)) + 20
        sim_frame = (self.exposure_time *
                     gaussian_2d(self.x_coord_array, self.y_coord_array, x0=0, y0=0, sx=sx, sy=sy, amp=256/10))
        sim_frame = np.random.poisson(sim_frame)
        sim_frame[sim_frame > 256] = 256
        self.frame = np.round(sim_frame).astype(int)
        self.frame_ready_signal.emit()
        # Remove the thread.wait() call as it's not needed and can cause issues

    def cleanup(self):
        """Clean up threads properly"""
        if hasattr(self, 'continuous_triggerer'):
            self.continuous_triggerer.requestInterruption()
            self.continuous_triggerer.quit()
            if not self.continuous_triggerer.wait(1000):
                self.continuous_triggerer.terminate()
        
        if hasattr(self, 'thread'):
            self.thread.quit()
            if not self.thread.wait(1000):
                self.thread.terminate()


class SimulatedCamDriver(JKamGenDriver):
    def __init__(self):
        super(SimulatedCamDriver, self).__init__()
        self.persistant_cam = SimulatedCamera(self)

    def _open_connection(self):
        print('Connected to Simulated Camera driver')

    def _close_connection(self):
        if hasattr(self, 'persistant_cam'):
            self.persistant_cam.cleanup()

    @staticmethod
    def _get_serial_number():
        return 'simcam8675309'

    def _arm_camera(self, serial_number):
        cam = self.persistant_cam
        return cam

    def _disarm_camera(self, cam):
        self.cam = None

    def _start_acquisition(self, cam):
        self.acquiring = True
        if self.trigger_mode == TriggerMode.CONTINUOUS:
            self.cam.start_continuous_signal.emit()

    def _stop_acquisition(self, cam):
        self.acquiring = False
        self.cam.stop_continuous_signal.emit()
        # Properly stop the continuous triggerer thread
        if hasattr(self.cam, 'continuous_triggerer'):
            self.cam.continuous_triggerer.requestInterruption()
            self.cam.continuous_triggerer.quit()
            if not self.cam.continuous_triggerer.wait(1000):
                self.cam.continuous_triggerer.terminate()

    def _set_exposure_time(self, cam, exposure_time):
        """
        exposure time input in ms.
        """
        self.exposure_time = round(exposure_time, 1)
        self.cam.exposure_time = self.exposure_time
        return self.exposure_time

    def _trigger_on(self, cam):
        self.trigger_mode = TriggerMode.TRIGGERING

    def _trigger_off(self, cam):
        self.trigger_mode = TriggerMode.CONTINUOUS

    def _set_hardware_trigger(self, cam):
        print('hardware trigger not implemented for simulated software camera')

    def _set_software_trigger(self, cam):
        pass

    def _execute_software_trigger(self, cam):
        self.cam.trigger_signal.emit()

    def _grab_frame(self, cam):
        # Check if QApplication exists before creating QEventLoop
        from PyQt5.QtWidgets import QApplication
        if QApplication.instance() is None:
            # No QApplication available, use a simple approach
            # For simulated camera, we can just return the frame directly
            if hasattr(self.cam, 'frame') and self.cam.frame is not None:
                return np.copy(self.cam.frame)
            else:
                # Trigger frame generation and return a default frame
                self.cam.trigger()
                if hasattr(self.cam, 'frame') and self.cam.frame is not None:
                    return np.copy(self.cam.frame)
                else:
                    return None
        
        # QApplication exists, use the original QEventLoop approach
        loop = QEventLoop()
        self.cam.frame_ready_signal.connect(loop.quit)
        loop.exec_()
        if self.cam.frame is not None:
            frame = np.copy(self.cam.frame)
        else:
            frame = None
        return frame

    def _load_default_settings(self, cam):
        self.frame_dict['metadata']['simulated metadata'] = 'Follow the white rabbit...'
