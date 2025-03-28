#3/13 Red Pitaya atomatic file ingestion Integration - hopefully works only tested locally - if not revert to prev (2/19?) version 
import sys
import time
import os
import warnings
import numpy as np
import h5py
import pickle
from scipy import signal
from Gage import GageScopeH5FileHandler
from FPGA import BinFileHandler
from JKAM import JkamH5FileHandler
from RP import RedPitayaFileHandler

# -------------------- NEW: we need paramiko for SSH/SFTP --------------------
import paramiko

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QWidget, QTabWidget, QGridLayout, QHeaderView,
    QLabel, QHBoxLayout, QLineEdit, QDockWidget, QCheckBox, QComboBox
)
from PyQt5.QtCore import QTimer, Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

###############################################################################
#                           Main GUI (Modified)                               #
###############################################################################
class FileProcessorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Processor GUI")
        self.setGeometry(100, 100, 1600, 900)

        self.inputs_accepted = False

        # Handlers
        self.jkam_h5_file_handler = JkamH5FileHandler(self)
        self.gage_h5_file_handler = GageScopeH5FileHandler(self)
        self.bin_handler = BinFileHandler(self)
        self.redpitaya_handler = RedPitayaFileHandler(self)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_hlayout = QHBoxLayout(self.central_widget)

        # Left Dock: Feature Options
        self.leftDock = QDockWidget("Feature Options", self)
        self.leftDock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.leftDock)

        self.feature_options_widget = QWidget()
        self.feature_options_layout = QVBoxLayout(self.feature_options_widget)

        # Checkboxes
        self.time_me_checkbox = QCheckBox("time_me")
        self.plot_tenth_shot_checkbox = QCheckBox("plot_tenth_shot")
        self.time_me_checkbox.setChecked(True)
        self.plot_tenth_shot_checkbox.setChecked(True)
        self.feature_options_layout.addWidget(self.time_me_checkbox)
        self.feature_options_layout.addWidget(self.plot_tenth_shot_checkbox)

        # Numeric fields
        self.het_freq_label = QLabel("het_freq (MHz):")
        self.het_freq_input = QLineEdit("20.000446")
        self.feature_options_layout.addWidget(self.het_freq_label)
        self.feature_options_layout.addWidget(self.het_freq_input)

        self.dds_freq_label = QLabel("dds_freq:")
        self.dds_freq_input = QLineEdit("10.000223")
        self.feature_options_layout.addWidget(self.dds_freq_label)
        self.feature_options_layout.addWidget(self.dds_freq_input)

        self.samp_freq_label = QLabel("samp_freq (MHz):")
        self.samp_freq_input = QLineEdit("200")
        self.feature_options_layout.addWidget(self.samp_freq_label)
        self.feature_options_layout.addWidget(self.samp_freq_input)

        self.averaging_time_label = QLabel("averaging_time (us):")
        self.averaging_time_input = QLineEdit("0")
        self.feature_options_layout.addWidget(self.averaging_time_label)
        self.feature_options_layout.addWidget(self.averaging_time_input)

        self.step_time_label = QLabel("step_time (us):")
        self.step_time_input = QLineEdit("1")
        self.feature_options_layout.addWidget(self.step_time_label)
        self.feature_options_layout.addWidget(self.step_time_input)

        self.filter_time_label = QLabel("filter_time (us):")
        self.filter_time_input = QLineEdit("5")
        self.feature_options_layout.addWidget(self.filter_time_label)
        self.feature_options_layout.addWidget(self.filter_time_input)

        self.voltage_conversion_label = QLabel("voltage_conversion (mV):")
        self.voltage_conversion_input = QLineEdit("0.0305176")
        self.feature_options_layout.addWidget(self.voltage_conversion_label)
        self.feature_options_layout.addWidget(self.voltage_conversion_input)

        self.kappa_label = QLabel("kappa (MHz):")
        self.kappa_input = QLineEdit("6.9115")
        self.feature_options_layout.addWidget(self.kappa_label)
        self.feature_options_layout.addWidget(self.kappa_input)

        self.LO_power_label = QLabel("LO_power (uW):")
        self.LO_power_input = QLineEdit("314")
        self.feature_options_layout.addWidget(self.LO_power_label)
        self.feature_options_layout.addWidget(self.LO_power_input)

        self.PHOTON_ENERGY_label = QLabel("PHOTON_ENERGY:")
        self.PHOTON_ENERGY_input = QLineEdit("2.55e-19")
        self.feature_options_layout.addWidget(self.PHOTON_ENERGY_label)
        self.feature_options_layout.addWidget(self.PHOTON_ENERGY_input)

        self.LO_rate_label = QLabel("LO_rate (count/us):")
        self.LO_rate_input = QLineEdit("1.23e9")
        self.feature_options_layout.addWidget(self.LO_rate_label)
        self.feature_options_layout.addWidget(self.LO_rate_input)

        self.photonrate_conversion_label = QLabel("photonrate_conversion (count/us):")
        self.photonrate_conversion_input = QLineEdit("9450")
        self.feature_options_layout.addWidget(self.photonrate_conversion_label)
        self.feature_options_layout.addWidget(self.photonrate_conversion_input)

        # Window function selector
        self.window_select_label = QLabel("Window function:")
        self.window_select = QComboBox()
        self.window_select.addItems(["hann", "flattop", "square"])
        self.window_select.setCurrentIndex(0)
        self.feature_options_layout.addWidget(self.window_select_label)
        self.feature_options_layout.addWidget(self.window_select)

        # ---------------------- NEW: Field to specify local RP download folder ---
        self.rp_download_dir_label = QLabel("Red Pitaya Download Folder:")
        self.rp_download_dir_edit = QLineEdit("C:\\Users\\jayom\\Downloads\\run4\\rp-automatic")
        self.feature_options_layout.addWidget(self.rp_download_dir_label)
        self.feature_options_layout.addWidget(self.rp_download_dir_edit)
        # -------------------------------------------------------------------------

        # Accept Inputs
        self.accept_button = QPushButton("Accept Inputs")
        self.accept_button.clicked.connect(self.accept_inputs)
        self.feature_options_layout.addWidget(self.accept_button)

        self.inputs_status_label = QLabel(
            "PLEASE ENTER INPUTS (or keep defaults) AND CLICK 'Accept Inputs' TO START!"
        )
        self.feature_options_layout.addWidget(self.inputs_status_label)
        self.feature_options_layout.addStretch()
        self.feature_options_widget.setLayout(self.feature_options_layout)
        self.leftDock.setWidget(self.feature_options_widget)

        # Right side
        self.right_side_widget = QWidget()
        self.right_side_layout = QVBoxLayout(self.right_side_widget)
        self.main_hlayout.addWidget(self.right_side_widget)

        self.tabs = QTabWidget()
        self.right_side_layout.addWidget(self.tabs)

        # Chart tab
        self.chart_tab = QWidget()
        self.chart_layout = QGridLayout(self.chart_tab)
        self.tabs.addTab(self.chart_tab, "Accept Charts")

        # JKAM table tab
        self.table_tab = QWidget()
        self.table_layout = QVBoxLayout(self.table_tab)
        self.tabs.addTab(self.table_tab, "JKAM Data")

        # FPGA table tab
        self.additional_table_tab_1 = QWidget()
        self.additional_table_tab_1_layout = QVBoxLayout(self.additional_table_tab_1)
        self.tabs.addTab(self.additional_table_tab_1, "FPGA Data")

        # GageScope table tab
        self.additional_table_tab_2 = QWidget()
        self.additional_table_tab_2_layout = QVBoxLayout(self.additional_table_tab_2)
        self.tabs.addTab(self.additional_table_tab_2, "GageScope Data")

        # Red Pitaya table tab
        self.additional_table_tab_3 = QWidget()
        self.additional_table_tab_3_layout = QVBoxLayout(self.additional_table_tab_3)
        self.tabs.addTab(self.additional_table_tab_3, "Red Pitaya Data")

        # FFT Graph tab
        self.fft_tab = QWidget()
        self.fft_tab_layout = QVBoxLayout(self.fft_tab)
        self.tabs.addTab(self.fft_tab, "FFT Graph")

        # Red Pitaya Visualizations Tab
        self.rp_tab = QWidget()
        self.rp_tab_layout = QGridLayout(self.rp_tab)
        self.tabs.addTab(self.rp_tab, "Red Pitaya Graphs")

        # FPGA Visualizations Tab
        self.fpga_tab = QWidget()
        self.fpga_tab_layout = QVBoxLayout(self.fpga_tab)
        self.tabs.addTab(self.fpga_tab, "FPGA Graphs")

        # JKAM table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Shot Number", "File Name", "Accepted", "Summary Statistics"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table_layout.addWidget(self.table)

        # Button in JKAM table tab
        self.add_file_button_table = QPushButton("Add Files")
        self.add_file_button_table.clicked.connect(self.add_files)
        self.table_layout.addWidget(self.add_file_button_table)

        # FPGA table
        self.additional_table_1 = QTableWidget()
        self.additional_table_1.setColumnCount(5)
        self.additional_table_1.setHorizontalHeaderLabels([
            "Shot Number", "File Name", "Accepted", "JKAM Space Correct", "Summary Statistics"
        ])
        self.additional_table_1.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.additional_table_1.horizontalHeader().setStretchLastSection(True)
        self.additional_table_tab_1_layout.addWidget(self.additional_table_1)

        # GageScope table
        self.additional_table_2 = QTableWidget()
        self.additional_table_2.setColumnCount(5)
        self.additional_table_2.setHorizontalHeaderLabels([
            "Shot Number", "File Name", "Accepted", "JKAM Space Correct", "Summary Statistics"
        ])
        self.additional_table_2.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.additional_table_2.horizontalHeader().setStretchLastSection(True)
        self.additional_table_tab_2_layout.addWidget(self.additional_table_2)

        # Red Pitaya table
        self.additional_table_3 = QTableWidget()
        self.additional_table_3.setColumnCount(5)
        self.additional_table_3.setHorizontalHeaderLabels([
            "Shot Number", "File Name", "Accepted", "JKAM Space Correct", "Summary Statistics"
        ])
        self.additional_table_3.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.additional_table_3.horizontalHeader().setStretchLastSection(True)
        self.additional_table_tab_3_layout.addWidget(self.additional_table_3)

        # Set up 10 figures
        self.figures = [Figure() for _ in range(10)]
        self.canvases = [FigureCanvas(fig) for fig in self.figures]

        self.chart_layout.addWidget(self.canvases[0], 0, 0)
        self.chart_layout.addWidget(self.canvases[1], 0, 1)
        self.chart_layout.addWidget(self.canvases[2], 1, 0)
        self.chart_layout.addWidget(self.canvases[3], 1, 1)

        self.add_file_button_charts = QPushButton("Add Files")
        self.add_file_button_charts.clicked.connect(self.add_files)
        self.chart_layout.addWidget(self.add_file_button_charts, 2, 0, 1, 2)

        self.fft_tab_layout.addWidget(self.canvases[4])

        self.rp_tab_layout.addWidget(self.canvases[5], 0, 0)
        self.rp_tab_layout.addWidget(self.canvases[6], 0, 1)
        self.rp_tab_layout.addWidget(self.canvases[7], 1, 0)
        self.rp_tab_layout.addWidget(self.canvases[8], 1, 1)

        self.fpga_tab_layout.addWidget(self.canvases[9])

        self.initialize_plot(0, "Cumulative Accepted Files 1 (JKAM)")
        self.initialize_plot(1, "Cumulative Accepted Files 2 (Bin/FPGA)")
        self.initialize_plot(2, "Cumulative Accepted Files (Red Pitaya)")
        self.initialize_plot(3, "Cumulative Accepted Files 3 (GageScope)")
        self.initialize_fft_plot(4)

        self.initialize_rp_plot(5)
        self.initialize_rp_plot(6)
        self.initialize_rp_plot(7)
        self.initialize_rp_plot(8)

        self.initialize_fpga_plot(9)

        self.stream_controls_layout = QHBoxLayout()
        self.stream_dir_label = QLabel("Stream Directory:")
        self.stream_dir_edit = QLineEdit(os.getcwd())
        self.stream_start_button = QPushButton("Start Stream")
        self.stream_stop_button = QPushButton("Stop Stream")
        self.stream_status_label = QLabel("Not streaming")
        self.stream_controls_layout.addWidget(self.stream_dir_label)
        self.stream_controls_layout.addWidget(self.stream_dir_edit)
        self.stream_controls_layout.addWidget(self.stream_start_button)
        self.stream_controls_layout.addWidget(self.stream_stop_button)
        self.stream_controls_layout.addWidget(self.stream_status_label)
        self.right_side_layout.addLayout(self.stream_controls_layout)

        self.stream_timer = QTimer()
        self.stream_timer.setInterval(2000)
        self.stream_timer.timeout.connect(self.check_for_new_files)

        self.stream_start_button.clicked.connect(self.start_stream)
        self.stream_stop_button.clicked.connect(self.stop_stream)

        self.stream_processed_files = set()

    def accept_inputs(self):
        fields = [
            self.het_freq_input, self.dds_freq_input, self.samp_freq_input,
            self.averaging_time_input, self.step_time_input, self.filter_time_input,
            self.voltage_conversion_input, self.kappa_input, self.LO_power_input,
            self.PHOTON_ENERGY_input, self.LO_rate_input, self.photonrate_conversion_input
        ]
        for field in fields:
            if field.text().strip() == "":
                print("Please fill in all inputs before accepting.")
                self.inputs_accepted = False
                return

        self.inputs_accepted = True
        self.inputs_status_label.setText("Inputs accepted! You may now add/stream files.")
        print("Inputs accepted! You may now use the rest of the GUI.")

    def initialize_plot(self, index, title_str):
        ax = self.figures[index].add_subplot(111)
        ax.plot([], [])
        ax.set_title(title_str)
        ax.set_xlabel("Shot Number")
        ax.set_ylabel("Cumulative Value")
        self.canvases[index].draw()

    def initialize_rp_plot(self, index):
        ax = self.figures[index].add_subplot(111)
        ax.plot([], [])
        ax.set_title("Cav & Perp Phase Locks")
        self.canvases[index].draw()

    def initialize_fft_plot(self, index):
        ax = self.figures[index].add_subplot(111)
        ax.plot([], [])
        ax.set_title("FFT of the Signal")
        ax.set_xlabel("Frequency")
        ax.set_ylabel("Amplitude")
        self.canvases[index].draw()

    def initialize_fpga_plot(self, index):
        ax = self.figures[index].add_subplot(111)
        ax.plot([], [])
        ax.set_title("FPGA Atom Input Times")
        ax.set_xlabel("Time (us)")
        ax.set_ylabel("Atoms In (Y/N)")
        self.canvases[index].draw()

    def add_files(self):
        if not self.inputs_accepted:
            print("Please fill in all inputs (or defaults) and click 'Accept Inputs' first.")
            return

        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*.*)")
        if not files:
            return

        for file in files:
            self.process_one_file(file)

    def process_one_file(self, file):
        self.jkam_h5_file_handler.update_settings()

        file_extension = os.path.splitext(file)[-1].lower()
        fname_lower = os.path.basename(file).lower()

        if file_extension == ".h5":
            if "jkam" in fname_lower:
                self.jkam_h5_file_handler.process_file(file)
            elif "gage" in fname_lower:
                self.gage_h5_file_handler.process_file(file)
            else:
                print(f"Unsupported .h5 file (not recognized as JKAM or GageScope). Skipping: {file}")
        elif file_extension == ".bin":
            self.bin_handler.process_file(file)
        elif file_extension == ".txt":
            self.redpitaya_handler.process_file(file)
        else:
            print(f"Unsupported file extension '{file_extension}' - skipping: {file}")

    def start_stream(self):
        if not self.inputs_accepted:
            print("Please fill in all inputs (or defaults) and click 'Accept Inputs' first.")
            return

        self.stream_processed_files.clear()
        self.stream_timer.start()
        self.stream_status_label.setText("Streaming has started!")
        print("Stream started. Monitoring directory:", self.stream_dir_edit.text())

    def stop_stream(self):
        self.stream_timer.stop()
        self.stream_status_label.setText("Not streaming")
        print("Stream stopped.")

    def check_for_new_files(self):
        if not self.inputs_accepted:
            return

        watch_dir = self.stream_dir_edit.text()
        if not os.path.isdir(watch_dir):
            print(f"Invalid stream directory: {watch_dir}")
            return

        subfolders = sorted(
            d for d in os.listdir(watch_dir)
            if os.path.isdir(os.path.join(watch_dir, d))
        )

        for subfolder in subfolders:
            subfolder_path = os.path.join(watch_dir, subfolder)
            folder_files = sorted(
                os.path.join(subfolder_path, f)
                for f in os.listdir(subfolder_path)
                if os.path.isfile(os.path.join(subfolder_path, f))
            )

            new_files = [f for f in folder_files if f not in self.stream_processed_files]
            for nf in new_files:
                self.process_one_file(nf)
                self.stream_processed_files.add(nf)

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def cleanup(self):
        self.jkam_h5_file_handler.jkam_files.clear()
        self.gage_h5_file_handler.gage_files.clear()
        self.bin_handler.bin_files.clear()
        self.redpitaya_handler.rp_files.clear()


###############################################################################
#                               Main Run                                      #
###############################################################################
if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = FileProcessorGUI()
    main_window.show()
    sys.exit(app.exec_())
