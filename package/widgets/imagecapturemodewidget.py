from enum import Enum
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget
from package.ui.imagecapturemodewidget_ui import Ui_ImageCaptureModeWidget


class ImagingMode(Enum):
    VIDEO = 0
    ABSORPTION = 1
    FLUORESCENCE = 2
    MULTISHOT = 3


class ImageCaptureModeWidget(QWidget, Ui_ImageCaptureModeWidget):
    state_set_signal = pyqtSignal(object)

    def __init__(self, parent=None):
        super(ImageCaptureModeWidget, self).__init__(parent=parent)
        self.setupUi(self)

        self.imaging_mode = ImagingMode.VIDEO
        self.image_capture_buttonGroup.buttonClicked.connect(self.set_imaging_mode)
        self.multishot_spinBox.valueChanged.connect(self.spinbox_adjusted)
        self.multishot_update_pushButton.clicked.connect(self.update_multishot_frames)
        self.set_imaging_mode()

    def set_imaging_mode(self):
        if self.video_mode_radioButton.isChecked():
            self.imaging_mode = ImagingMode.VIDEO
        elif self.absorption_mode_radioButton.isChecked():
            self.imaging_mode = ImagingMode.ABSORPTION
        elif self.fluorescence_mode_radioButton.isChecked():
            self.imaging_mode = ImagingMode.FLUORESCENCE
        elif self.multishot_mode_radioButton.isChecked():
            self.imaging_mode = ImagingMode.MULTISHOT
        # Use theme-aware colors
        window = self.window()
        if window and hasattr(window, 'dark_mode') and window.dark_mode:
            self.multishot_spinBox.setStyleSheet("QSpinBox {background-color: #3c3c3c;}")
        else:
            self.multishot_spinBox.setStyleSheet("QSpinBox {background-color: #FFFFFF;}")
        
        # Enable update button only when multishot mode is selected and triggered mode is enabled
        if self.multishot_mode_radioButton.isChecked() and self.multishot_mode_radioButton.isEnabled():
            self.multishot_update_pushButton.setEnabled(True)
        else:
            self.multishot_update_pushButton.setEnabled(False)
            
        self.state_set_signal.emit(self.imaging_mode)

    def continuous_enabled(self):
        self.video_mode_radioButton.setEnabled(True)
        self.absorption_mode_radioButton.setEnabled(False)
        self.fluorescence_mode_radioButton.setEnabled(False)
        self.multishot_mode_radioButton.setEnabled(False)
        self.multishot_spinBox.setEnabled(False)
        self.video_mode_radioButton.setChecked(True)
        self.imaging_mode = ImagingMode.VIDEO
        self.state_set_signal.emit(self.imaging_mode)

    def triggered_enabled(self):
        self.video_mode_radioButton.setEnabled(True)
        self.absorption_mode_radioButton.setEnabled(True)
        self.fluorescence_mode_radioButton.setEnabled(True)
        self.multishot_mode_radioButton.setEnabled(True)
        self.multishot_spinBox.setEnabled(True)
        self.multishot_update_pushButton.setEnabled(True)


    def started(self):
        self.video_mode_radioButton.setEnabled(False)
        self.absorption_mode_radioButton.setEnabled(False)
        self.fluorescence_mode_radioButton.setEnabled(False)
        self.multishot_mode_radioButton.setEnabled(False)
        self.multishot_spinBox.setEnabled(False)
        self.multishot_update_pushButton.setEnabled(False)


    def disarmed(self):
        self.video_mode_radioButton.setEnabled(True)
        self.absorption_mode_radioButton.setEnabled(True)
        self.fluorescence_mode_radioButton.setEnabled(True)
        self.multishot_mode_radioButton.setEnabled(True)
        self.multishot_spinBox.setEnabled(True)
        self.multishot_update_pushButton.setEnabled(True)

    def spinbox_adjusted(self):
        # Use theme-aware colors
        window = self.window()
        if window and hasattr(window, 'dark_mode') and window.dark_mode:
            self.multishot_spinBox.setStyleSheet("QSpinBox {background-color: #8B0000;}")
        else:
            self.multishot_spinBox.setStyleSheet("QSpinBox {background-color: #FFAAAA;}")

    def update_multishot_frames(self):
        """
        Update the multishot frame count and apply the changes immediately.
        This method is called when the update button is clicked.
        """
        # Reset the spinbox styling to normal
        window = self.window()
        if window and hasattr(window, 'dark_mode') and window.dark_mode:
            self.multishot_spinBox.setStyleSheet("QSpinBox {background-color: #3c3c3c;}")
        else:
            self.multishot_spinBox.setStyleSheet("QSpinBox {background-color: #FFFFFF;}")
        
        # Emit the signal to update the imaging mode with the new frame count
        self.state_set_signal.emit(self.imaging_mode)

