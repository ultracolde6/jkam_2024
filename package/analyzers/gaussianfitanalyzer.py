"""
Gaussian Fit Analyzer

Provides 2D Gaussian fitting analysis for images.
Fits Gaussian functions to image data within selected ROI.
"""

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget
import pyqtgraph as pg
from package.ui.gaussianfitanalyzer_ui import Ui_GaussianFitAnalyzer
from package.analyzers.smart_gaussian2d_fit import fit_gaussian2d
from package.widgets.gaussian2d_visualization_widget import FitVisualizationWindow


class GaussianFitWorker(QThread):
    """
    Worker thread for Gaussian fitting calculations.
    
    Performs 2D Gaussian fitting in background thread to avoid
    blocking the GUI during analysis.
    """
    
    analysis_complete_signal = pyqtSignal(dict, float, float)

    def __init__(self):
        """Initialize Gaussian fit worker."""
        super(GaussianFitWorker, self).__init__()
        self.roi = None

    def run(self):
        """
        Perform 2D Gaussian fitting analysis.
        
        Extracts ROI data and fits 2D Gaussian function,
        returning fit parameters and offsets.
        """
        roi_loc_y, roi_loc_x = self.roi.getArraySlice(self.imageview.image, self.imageview.getImageItem(),
                                                      returnSlice=False)[0]
        roi_slice = tuple((slice(roi_loc_y[0], roi_loc_y[1]), slice(roi_loc_x[0], roi_loc_x[1])))
        roi_data = self.imageview.image[roi_slice]
        fit_struct = fit_gaussian2d(roi_data)
        x_offset = roi_loc_x[0]
        y_offset = roi_loc_y[0]
        self.analysis_complete_signal.emit(fit_struct, x_offset, y_offset)


class GaussianFitAnalyzer(QWidget, Ui_GaussianFitAnalyzer):
    """
    Gaussian fit analyzer widget.
    
    Provides interactive ROI selection and 2D Gaussian fitting
    with real-time visualization of fit results.
    """

    def __init__(self, parent=None):
        """
        Initialize Gaussian fit analyzer.
        
        Args:
            parent: Parent widget
        """
        super(GaussianFitAnalyzer, self).__init__(parent=parent)
        self.setupUi(self)
        self.worker = GaussianFitWorker()
        self.imageview = None
        self.enabled = False
        self.roi = None
        self.enable_checkBox.clicked.connect(self.toggle_enable)
        self.gaussian_fit_window = FitVisualizationWindow()
        self.gaussian_fit_window.window_close_signal.connect(self.window_closed)
        self.worker.analysis_complete_signal.connect(self.gaussian_fit_window.update)

    def analyze(self):
        """Start Gaussian fitting analysis if enabled."""
        if self.enabled:
            self.worker.start()

    def enable(self):
        """Enable Gaussian fitting analysis."""
        self.enabled = True
        self.roi = self.create_roi(pen='w')
        self.worker.roi = self.roi

    def disable(self):
        """Disable Gaussian fitting analysis."""
        self.enabled = False
        self.remove_roi()

    def create_roi(self, pen='w'):
        """
        Create a rectangular ROI on the image view.
        
        Args:
            pen: Color of the ROI border
            
        Returns:
            pg.RectROI: Created ROI object
        """
        roi = pg.RectROI((0, 0), (50, 50), pen=pen)
        roi.addScaleHandle([1, 1], [0, 0])
        roi.addScaleHandle([0, 0], [1, 1])
        self.imageview.addItem(roi)
        return roi

    def remove_roi(self):
        """Remove ROI from image view."""
        try:
            self.imageview.removeItem(self.roi)
            self.roi = None
            self.worker.roi = None
        except AttributeError:
            pass

    def toggle_enable(self):
        """Toggle Gaussian fitting on/off based on checkbox state."""
        if self.enable_checkBox.isChecked():
            self.gaussian_fit_window.show()
            self.enable()
        elif not self.enable_checkBox.isChecked():
            self.gaussian_fit_window.close()
            self.disable()

    def set_imageview(self, imageview):
        """
        Set the image view for analysis.
        
        Args:
            imageview: PyQtGraph ImageView widget
        """
        if imageview is not self.imageview:
            self.disable()
            self.imageview = imageview
            self.worker.imageview = self.imageview
            self.toggle_enable()

    def continuous_enabled(self):
        """Disable analyzer when continuous mode is enabled."""
        self.gaussian_fit_window.close()
        self.disable()
        self.enable_checkBox.setChecked(False)
        self.enable_checkBox.setEnabled(False)

    def triggered_enabled(self):
        """Enable analyzer when triggered mode is enabled."""
        self.enable_checkBox.setEnabled(True)

    def window_closed(self):
        """Handle fit window close event."""
        self.disable()
        self.enable_checkBox.setChecked(False)