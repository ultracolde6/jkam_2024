"""
JKam package provides a GUI interface to control camera sensors especially for use in ultracold atomic imaging
applications. Software control of various types of sensors is supported through the JKamGenDriver class which acts
as an interface between the JKam package and a sensor specific driver.
Functionality includes video acquisition and setting up software and hardware triggering as well as
sensor exposure adjustments. There is also support for absorption imaging which includes the capture of three
frames and subsequent image processing.
Images can be saved and autosaved upon acquisition and processing.
Some basic image processing functionality is implemented such as region of area integration with background subtraction.
There are plans to implement a Gaussian fit analyzer.

Original program by Jonathan Kohler.
Updated by Justin Gerber (2020) - gerberja@berkeley.edu
Updated by Tai Xiang (2025) - taiyangxiang@berkeley.edu
"""

import copy
import sys
import ctypes
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QApplication, QAction, QMenu, QMessageBox
from PyQt5.QtGui import QIcon
from package.ui.camerawindow_ui import Ui_CameraWindow
from package.data.camerasettings import RbAtom
from package.widgets.imagecapturemodewidget import ImagingMode
import time
import h5py
import pyqtgraph as pg

class JKamWindow(QMainWindow, Ui_CameraWindow):
    """
    Main window class for the JKam GUI application.

    This class provides the main interface for camera control, image acquisition, visualization,
    saving, and basic analysis for ultracold atomic imaging applications.

    Signals:
        analyze_signal: Emitted to trigger analysis of the current image.
        all_frames_received_signal: Emitted when all frames for a given acquisition are received.

    Attributes:
        multimode (bool): Determines if multishot mode is enabled.
        imaging_mode: Current imaging mode (VIDEO, ABSORPTION, FLUORESCENCE, MULTISHOT).
        video_frame_dict: Stores the latest video frame dictionary.
        imaging_system: Reference to the current imaging system.
        dark_mode (bool): Current theme state (True for dark, False for light).
    """

    analyze_signal = pyqtSignal()
    all_frames_received_signal = pyqtSignal()
    multimode = True

    def __init__(self):
        """
        Initialize the JKamWindow, set up UI, connect signals, and show the window.
        """
        super(JKamWindow, self).__init__()
        self.setupUi(self)
        
        # Theme management
        self.dark_mode = False
        self.setup_theme_menu()
        self.setup_views_menu()
        self.setup_splitter()
        self.apply_theme()

        # Connect frame received signal to capture handler
        self.frame_received_signal = self.camera_control_widget.frame_received_signal
        self.frame_received_signal.connect(self.on_capture)

        # Connect analysis complete signals from view widgets
        self.absorption_view_widget.analysis_complete_signal.connect(self.on_all_frames_received)
        self.fluorescence_view_widget.analysis_complete_signal.connect(self.on_all_frames_received)
        self.multishot_view_widget.analysis_complete_signal.connect(self.on_all_frames_received)

        # Connect multishot frame signals if multimode is enabled
        if self.multimode is True:
            self.multishot_view_widget.first_frame_complete_signal.connect(self.on_first_frame_received)
            self.multishot_view_widget.second_frame_complete_signal.connect(self.on_second_frame_received)
            self.multishot_view_widget.third_frame_complete_signal.connect(self.on_third_frame_received)
            
        # Connect multishot vertical view signals
        self.multishot_vertical_view_widget.analysis_complete_signal.connect(self.on_all_frames_received)
        
        # Connect multishot 1013 LS view signals
        self.multishot_1013ls_view_widget.analysis_complete_signal.connect(self.on_all_frames_received)

        # Connect analysis signals to analyzer widgets
        self.analyze_signal.connect(self.roi_analyzer_widget.analyze)
        self.analyze_signal.connect(self.gaussian2d_analyzer_widget.analyze)

        self.imaging_mode = None

        # Connect imaging mode widget signals
        self.imagecapturemodewidget.state_set_signal.connect(self.set_imaging_mode)
        self.camera_control_widget.started_signal.connect(self.absorption_view_widget.reset)
        self.camera_control_widget.started_signal.connect(self.fluorescence_view_widget.reset)
        self.camera_control_widget.started_signal.connect(self.imagecapturemodewidget.started)
        self.camera_control_widget.continuous_enabled_signal.connect(self.imagecapturemodewidget.continuous_enabled)
        self.camera_control_widget.continuous_enabled_signal.connect(self.gaussian2d_analyzer_widget.continuous_enabled)
        self.camera_control_widget.triggered_enabled_signal.connect(self.imagecapturemodewidget.triggered_enabled)
        self.camera_control_widget.triggered_enabled_signal.connect(self.gaussian2d_analyzer_widget.triggered_enabled)
        self.camera_control_widget.disarmed_signal.connect(self.imagecapturemodewidget.disarmed)
        self.imagecapturemodewidget.set_imaging_mode()

        # Connect armed/disarmed signals
        self.camera_control_widget.armed_signal.connect(self.armed)
        self.camera_control_widget.disarmed_signal.connect(self.disarmed)

        # Connect save button
        self.savebox_widget.save_single_pushButton.clicked.connect(self.save_frames)

        self.video_frame_dict = None
        self.imaging_system = None
        
        self.show()

    def on_capture(self, frame_dict_in):
        """
        Handle a new frame received from the camera.

        Args:
            frame_dict_in (dict): Dictionary containing frame data.
        """
        frame_dict = copy.deepcopy(frame_dict_in)
        self.frame_received_signal.disconnect(self.on_capture)
        if self.imaging_mode is ImagingMode.VIDEO:
            self.display_video_frame(frame_dict)
        elif self.imaging_mode is ImagingMode.ABSORPTION:
            self.display_absorption_frame(frame_dict)
        elif self.imaging_mode is ImagingMode.FLUORESCENCE:
            self.display_fluorescence_frame(frame_dict)
        elif self.imaging_mode is ImagingMode.MULTISHOT:
            self.display_multishot_frame(frame_dict)
        self.frame_received_signal.connect(self.on_capture)

    def display_video_frame(self, frame_dict):
        """
        Display a video frame in the video view editor.

        Args:
            frame_dict (dict): Dictionary containing frame data.
        """
        self.video_frame_dict = frame_dict
        video_frame = self.video_frame_dict['frame']
        self.videovieweditor.setImage(video_frame, autoRange=False,
                                      autoLevels=False, autoHistogramRange=False)
        self.on_all_frames_received()

    def display_absorption_frame(self, frame_dict):
        """
        Process and display an absorption frame.

        Args:
            frame_dict (dict): Dictionary containing frame data.
        """
        self.absorption_view_widget.process_frame(frame_dict)

    def display_fluorescence_frame(self, frame_dict):
        """
        Process and display a fluorescence frame.

        Args:
            frame_dict (dict): Dictionary containing frame data.
        """
        self.fluorescence_view_widget.process_frame(frame_dict)

    def display_multishot_frame(self, frame_dict):
        """
        Process and display a multishot frame.

        Args:
            frame_dict (dict): Dictionary containing frame data.
        """
        self.multishot_view_widget.process_frame(frame_dict)
        self.multishot_vertical_view_widget.process_frame(frame_dict)
        self.multishot_1013ls_view_widget.process_frame(frame_dict)

    def show_error_dialog(self, title, message, details=None):
        """
        Show an error dialog with the given title and message.
        
        Args:
            title (str): Dialog title
            message (str): Error message
            details (str, optional): Additional error details
        """
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        if details:
            msg_box.setDetailedText(details)
        msg_box.exec_()

    def on_all_frames_received(self):
        """
        Called when all frames for an acquisition are received.
        Triggers analysis and autosave if enabled.
        """
        self.analyze_signal.emit()
        if self.verify_autosave():
            try:
                self.save_frames()
            except OSError as e:
                self.show_error_dialog(
                    "Save Error", 
                    "Failed to save frame data.",
                    f"Error details: {str(e)}"
                )
            except Exception as e:
                self.show_error_dialog(
                    "Unexpected Error", 
                    "An unexpected error occurred while saving frames.",
                    f"Error details: {str(e)}"
                )

    def on_first_frame_received(self):
        """
        Called when the first frame in multishot mode is received.
        Triggers saving of the first frame.
        """
        try:
            self.save_frames_1()
        except OSError as e:
            self.show_error_dialog(
                "Save Error", 
                "Failed to save first frame.",
                f"Error details: {str(e)}"
            )
        except Exception as e:
            self.show_error_dialog(
                "Unexpected Error", 
                "An unexpected error occurred while saving first frame.",
                f"Error details: {str(e)}"
            )

    def on_second_frame_received(self):
        """
        Called when the second frame in multishot mode is received.
        Triggers saving of the second frame.
        """
        try:
            self.save_frames_2()
        except OSError as e:
            self.show_error_dialog(
                "Save Error", 
                "Failed to save second frame.",
                f"Error details: {str(e)}"
            )
        except Exception as e:
            self.show_error_dialog(
                "Unexpected Error", 
                "An unexpected error occurred while saving second frame.",
                f"Error details: {str(e)}"
            )

    def on_third_frame_received(self):
        """
        Called when the third frame in multishot mode is received.
        Triggers saving of the third frame.
        """
        try:
            self.save_frames_3()
        except OSError as e:
            self.show_error_dialog(
                "Save Error", 
                "Failed to save third frame.",
                f"Error details: {str(e)}"
            )
        except Exception as e:
            self.show_error_dialog(
                "Unexpected Error", 
                "An unexpected error occurred while saving third frame.",
                f"Error details: {str(e)}"
            )

    def save_frames(self):
        """
        Save frames according to the current imaging mode.
        """
        if self.imaging_mode is ImagingMode.VIDEO:
            self.savebox_widget.save(self.video_frame_dict)
        if self.imaging_mode is ImagingMode.ABSORPTION:
            atom_frame_dict = self.absorption_view_widget.atom_frame_dict
            bright_frame_dict = self.absorption_view_widget.bright_frame_dict
            dark_frame_dict = self.absorption_view_widget.dark_frame_dict
            self.savebox_widget.save(atom_frame_dict, bright_frame_dict, dark_frame_dict)
        if self.imaging_mode is ImagingMode.FLUORESCENCE:
            atom_frame_dict = self.fluorescence_view_widget.atom_frame_dict
            ref_frame_dict = self.fluorescence_view_widget.ref_frame_dict
            self.savebox_widget.save(atom_frame_dict, ref_frame_dict)
        if self.imaging_mode is ImagingMode.MULTISHOT and self.multimode is False:
            frame_dict_list = self.multishot_view_widget.frame_dict_list
            self.savebox_widget.save(frame_dict_list)
        if self.imaging_mode is ImagingMode.MULTISHOT and self.multimode is True:
            frame_dict_list = self.multishot_view_widget.frame_dict_list
            self.savebox_widget.save(frame_dict_list)

    def save_frames_1(self):
        """
        Save the first frame in multishot mode.
        """
        if self.imaging_mode is ImagingMode.MULTISHOT and self.multimode is True:
            frame_dict_list_0 = [self.multishot_view_widget.frame_dict_list[0]]
            try:
                self.savebox_widget.save_1(frame_dict_list_0)
            except Exception as e:
                self.show_error_dialog(
                    "Save Error",
                    "Failed to save first frame. Retrying...",
                    f"Error details: {str(e)}"
                )
                time.sleep(0.1)
                frame_dict_list_0 = [self.multishot_view_widget.frame_dict_list[0]]
                self.savebox_widget.save_1(frame_dict_list_0)

    def save_frames_2(self):
        """
        Save the second frame in multishot mode.
        """
        if self.imaging_mode is ImagingMode.MULTISHOT and self.multimode is True:
            frame_dict_list_1 = [self.multishot_view_widget.frame_dict_list[1]]
            try:
                self.savebox_widget.save_2(frame_dict_list_1)
            except Exception as e:
                self.show_error_dialog(
                    "Save Error",
                    "Failed to save second frame. Retrying...",
                    f"Error details: {str(e)}"
                )
                time.sleep(0.1)
                frame_dict_list_1 = [self.multishot_view_widget.frame_dict_list[1]]
                self.savebox_widget.save_2(frame_dict_list_1)

    def save_frames_3(self):
        """
        Save the third frame in multishot mode.
        """
        if self.imaging_mode is ImagingMode.MULTISHOT and self.multimode is True:
            frame_dict_list_2 = [self.multishot_view_widget.frame_dict_list[2]]
            try:
                self.savebox_widget.save_3(frame_dict_list_2)
            except Exception as e:
                self.show_error_dialog(
                    "Save Error",
                    "Failed to save third frame. Retrying...",
                    f"Error details: {str(e)}"
                )
                time.sleep(0.1)
                frame_dict_list_2 = [self.multishot_view_widget.frame_dict_list[2]]
                self.savebox_widget.save_3(frame_dict_list_2)

    def set_imaging_mode(self, imaging_mode):
        """
        Set the current imaging mode and update the UI accordingly.

        Args:
            imaging_mode: Imaging mode to set (VIDEO, ABSORPTION, FLUORESCENCE, MULTISHOT).
        """
        self.imaging_mode = imaging_mode
        if self.imaging_mode is ImagingMode.VIDEO:
            self.view_stackedWidget.setCurrentIndex(0)
            self.roi_analyzer_widget.set_imageview(self.videovieweditor.imageview)
            self.gaussian2d_analyzer_widget.set_imageview(self.videovieweditor.imageview)
            self.savebox_widget.mode = self.savebox_widget.ModeType.SINGLE
            # Hide views menu
            self.views_menu.setVisible(False)
        elif self.imaging_mode is ImagingMode.ABSORPTION:
            self.view_stackedWidget.setCurrentIndex(1)
            self.roi_analyzer_widget.set_imageview(self.absorption_view_widget.N_view_editor.imageview)
            self.gaussian2d_analyzer_widget.set_imageview(self.absorption_view_widget.N_view_editor.imageview)
            self.savebox_widget.mode = self.savebox_widget.ModeType.ABSORPTION
            # Hide views menu
            self.views_menu.setVisible(False)
        elif self.imaging_mode is ImagingMode.FLUORESCENCE:
            self.view_stackedWidget.setCurrentIndex(2)
            self.roi_analyzer_widget.set_imageview(self.fluorescence_view_widget.N_view_editor.imageview)
            self.gaussian2d_analyzer_widget.set_imageview(self.fluorescence_view_widget.N_view_editor.imageview)
            self.savebox_widget.mode = self.savebox_widget.ModeType.FLUORESCENCE
            # Hide views menu
            self.views_menu.setVisible(False)
        elif self.imaging_mode is ImagingMode.MULTISHOT:
            # Show tabbed view by default
            self.view_stackedWidget.setCurrentIndex(3)  # Tabbed view
            num_frames = self.imagecapturemodewidget.multishot_spinBox.value()
            self.multishot_view_widget.setup_frames(num_frames)
            self.multishot_vertical_view_widget.setup_frames(num_frames)
            self.multishot_1013ls_view_widget.setup_frames(num_frames)
            self.roi_analyzer_widget.set_imageview(self.multishot_view_widget.editor_list[0].imageview)
            self.gaussian2d_analyzer_widget.set_imageview(self.multishot_view_widget.editor_list[0].imageview)
            self.savebox_widget.mode = self.savebox_widget.ModeType.MULTISHOT
            # Show views menu
            self.views_menu.setVisible(True)
            # Set default view to tabbed
            self.multishot_tab_widget.setCurrentIndex(0)
            self.tabbed_action.setChecked(True)
            self.vertical_action.setChecked(False)
            self.view_1013ls_action.setChecked(False)

    def switch_multishot_view(self, view_index):
        """
        Switch between tabbed, vertical, and 1013 LS views in multishot mode.
        
        Args:
            view_index (int): 0 for tabbed view, 1 for vertical view, 2 for 1013 LS view
        """
        if self.imaging_mode is ImagingMode.MULTISHOT:
            self.multishot_tab_widget.setCurrentIndex(view_index)
            
            # Update menu check states
            self.tabbed_action.setChecked(view_index == 0)
            self.vertical_action.setChecked(view_index == 1)
            self.view_1013ls_action.setChecked(view_index == 2)

    def armed(self):
        """
        Called when the camera system is armed.
        Loads analyzers and arms the savebox widget.
        """
        self.imaging_system = self.camera_control_widget.imaging_system
        self.absorption_view_widget.load_analyzer(atom=RbAtom, imaging_system=self.imaging_system)
        self.savebox_widget.arm(imaging_system=self.imaging_system)

    def disarmed(self):
        """
        Called when the camera system is disarmed.
        Unloads analyzers and disarms the savebox widget.
        """
        self.absorption_view_widget.unload_analyzer()
        self.savebox_widget.disarm()

    def verify_autosave(self):
        """
        Verify if autosave should be performed.

        Returns:
            bool: True if autosave is enabled and not in continuous mode, False otherwise.
        """
        if not self.camera_control_widget.continuous_radioButton.isChecked() and self.savebox_widget.autosaving:
            return True
        else:
            return False



    def setup_theme_menu(self):
        """
        Set up the theme menu in the menubar.
        """
        # Create theme menu
        theme_menu = self.menubar.addMenu('Theme')
        
        # Light theme action
        light_action = QAction('Light Theme', self)
        light_action.setCheckable(True)
        light_action.setChecked(not self.dark_mode)
        light_action.triggered.connect(lambda: self.set_theme(False))
        theme_menu.addAction(light_action)
        
        # Dark theme action
        dark_action = QAction('Dark Theme', self)
        dark_action.setCheckable(True)
        dark_action.setChecked(self.dark_mode)
        dark_action.triggered.connect(lambda: self.set_theme(True))
        theme_menu.addAction(dark_action)
        
        # Store actions for later use
        self.light_action = light_action
        self.dark_action = dark_action

    def setup_views_menu(self):
        """
        Set up the views menu in the menubar for multishot mode.
        """
        # Create views menu
        self.views_menu = self.menubar.addMenu('Views')
        
        # Tabbed view action
        tabbed_action = QAction('Tabbed View', self)
        tabbed_action.setCheckable(True)
        tabbed_action.setChecked(True)  # Default to tabbed view
        tabbed_action.triggered.connect(lambda: self.switch_multishot_view(0))
        self.views_menu.addAction(tabbed_action)
        
        # Vertical view action
        vertical_action = QAction('Vertical View', self)
        vertical_action.setCheckable(True)
        vertical_action.setChecked(False)
        vertical_action.triggered.connect(lambda: self.switch_multishot_view(1))
        self.views_menu.addAction(vertical_action)
        
        # 1013 LS view action
        view_1013ls_action = QAction('1013 LS', self)
        view_1013ls_action.setCheckable(True)
        view_1013ls_action.setChecked(False)
        view_1013ls_action.triggered.connect(lambda: self.switch_multishot_view(2))
        self.views_menu.addAction(view_1013ls_action)
        
        # Store actions for later use
        self.tabbed_action = tabbed_action
        self.vertical_action = vertical_action
        self.view_1013ls_action = view_1013ls_action
        
        # Add separator and reset option
        self.views_menu.addSeparator()
        reset_splitter_action = QAction('Reset Splitter', self)
        reset_splitter_action.triggered.connect(self.reset_splitter)
        self.views_menu.addAction(reset_splitter_action)
        
        # Initially hide the views menu
        self.views_menu.setVisible(False)

    def setup_splitter(self):
        """
        Set up the main splitter with reasonable default sizes.
        """
        # Set initial splitter sizes (control area gets more space)
        total_height = self.height()
        view_height = int(total_height * 0.35)  # 30% for view area
        control_height = total_height - view_height  # 70% for control area
        
        self.main_splitter.setSizes([view_height, control_height])
        
        # Set minimum sizes to prevent widgets from becoming too small
        self.view_area.setMinimumHeight(200)
        self.control_area.setMinimumHeight(150)
        # Style the splitter handle to make it more visible
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #666666;
                border: 1px solid #444444;
            }
            QSplitter::handle:hover {
                background-color: #888888;
            }
        """)
    def reset_splitter(self):
        """
        Reset the splitter to default sizes.
        """
        total_height = self.height()
        view_height = int(total_height * 0.35)
        control_height = total_height - view_height
        self.main_splitter.setSizes([view_height, control_height])

    def set_theme(self, dark_mode):
        """
        Set the application theme.

        Args:
            dark_mode (bool): True for dark theme, False for light theme.
        """
        self.dark_mode = dark_mode
        self.apply_theme()
        
        # Update menu check states
        self.light_action.setChecked(not dark_mode)
        self.dark_action.setChecked(dark_mode)

    def apply_theme(self):
        """
        Apply the current theme to the application.
        """
        if self.dark_mode:
            # Apply dark theme
            self.apply_dark_stylesheets()
        else:
            # Apply light theme
            self.apply_light_stylesheets()

    def apply_dark_stylesheets(self):
        """
        Apply dark mode stylesheets to specific widgets.
        """
        # Dark theme colors
        dark_bg = "#2b2b2b"
        dark_text = "#ffffff"
        dark_button = "#404040"
        dark_button_text = "#ffffff"
        dark_input = "#3c3c3c"
        dark_border = "#555555"
        
        # Main window
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {dark_bg};
                color: {dark_text};
            }}
            QWidget {{
                background-color: {dark_bg};
                color: {dark_text};
            }}
            QPushButton {{
                background-color: {dark_button};
                color: {dark_button_text};
                border: 1px solid {dark_border};
                padding: 5px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: #505050;
            }}
            QPushButton:pressed {{
                background-color: #606060;
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background-color: {dark_input};
                color: {dark_text};
                border: 1px solid {dark_border};
                padding: 3px;
                border-radius: 2px;
            }}
            QRadioButton {{
                color: {dark_text};
            }}
            QRadioButton::indicator {{
                width: 13px;
                height: 13px;
            }}
            QRadioButton::indicator:unchecked {{
                border: 2px solid {dark_border};
                background-color: {dark_bg};
                border-radius: 7px;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {dark_border};
                background-color: #0078d4;
                border-radius: 7px;
            }}
            QTabWidget::pane {{
                border: 1px solid {dark_border};
                background-color: {dark_bg};
            }}
            QTabBar::tab {{
                background-color: {dark_button};
                color: {dark_button_text};
                padding: 8px 12px;
                border: 1px solid {dark_border};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: {dark_bg};
            }}
            QMenuBar {{
                background-color: {dark_bg};
                color: {dark_text};
                border-bottom: 1px solid {dark_border};
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 4px 8px;
            }}
            QMenuBar::item:selected {{
                background-color: {dark_button};
            }}
            QMenu {{
                background-color: {dark_bg};
                color: {dark_text};
                border: 1px solid {dark_border};
            }}
            QMenu::item {{
                padding: 4px 20px;
            }}
            QMenu::item:selected {{
                background-color: {dark_button};
            }}
            QStatusBar {{
                background-color: {dark_bg};
                color: {dark_text};
                border-top: 1px solid {dark_border};
            }}
        """)

    def apply_light_stylesheets(self):
        """
        Apply light mode stylesheets to specific widgets.
        """
        # Light theme colors
        light_bg = "#ffffff"
        light_text = "#000000"
        light_button = "#f0f0f0"
        light_button_text = "#000000"
        light_input = "#ffffff"
        light_border = "#cccccc"
        
        # Main window
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {light_bg};
                color: {light_text};
            }}
            QWidget {{
                background-color: {light_bg};
                color: {light_text};
            }}
            QPushButton {{
                background-color: {light_button};
                color: {light_button_text};
                border: 1px solid {light_border};
                padding: 5px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: #e0e0e0;
            }}
            QPushButton:pressed {{
                background-color: #d0d0d0;
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background-color: {light_input};
                color: {light_text};
                border: 1px solid {light_border};
                padding: 3px;
                border-radius: 2px;
            }}
            QRadioButton {{
                color: {light_text};
            }}
            QRadioButton::indicator {{
                width: 13px;
                height: 13px;
            }}
            QRadioButton::indicator:unchecked {{
                border: 2px solid {light_border};
                background-color: {light_bg};
                border-radius: 7px;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {light_border};
                background-color: #0078d4;
                border-radius: 7px;
            }}
            QTabWidget::pane {{
                border: 1px solid {light_border};
                background-color: {light_bg};
            }}
            QTabBar::tab {{
                background-color: {light_button};
                color: {light_button_text};
                padding: 8px 12px;
                border: 1px solid {light_border};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: {light_bg};
            }}
            QMenuBar {{
                background-color: {light_bg};
                color: {light_text};
                border-bottom: 1px solid {light_border};
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 4px 8px;
            }}
            QMenuBar::item:selected {{
                background-color: {light_button};
            }}
            QMenu {{
                background-color: {light_bg};
                color: {light_text};
                border: 1px solid {light_border};
            }}
            QMenu::item {{
                padding: 4px 20px;
            }}
            QMenu::item:selected {{
                background-color: {light_button};
            }}
            QStatusBar {{
                background-color: {light_bg};
                color: {light_text};
                border-top: 1px solid {light_border};
            }}
        """)

    def closeEvent(self, event):
        """
        Handle the window close event.

        Args:
            event: Close event.
        """
        self.camera_control_widget.close()
        sys.exit()


def main():
    """
    Main entry point for the JKam application.
    Sets up the QApplication, window icon, and launches the main window.
    """
    app = QApplication(sys.argv)

    # Code to setup windows icon for jkam
    app.setWindowIcon(QIcon('jkamicon.ico'))
    myappid = u'jkam_app'  # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    ex = JKamWindow()
    ex.show()
    app.exec_()


if __name__ == '__main__':
    main()
    sys.exit()
