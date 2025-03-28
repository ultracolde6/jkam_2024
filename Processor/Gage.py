
#3/13 Red Pitaya atomatic file ingestion Integration - hopefully works only tested locally - if not revert to prev (2/19?) version 
import sys
import time
import os
import warnings
import numpy as np
import h5py
import pickle
from scipy import signal

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
#                      GageScope .h5 Handler                                  #
###############################################################################
class GageScopeH5FileHandler:
    """
    Properly closes each GageScope file after extracting only needed data.
    """
    def __init__(self, gui):
        self.gui = gui

        self.gage_files = []  # store dictionaries of channel data
        self.gage_creation_time_array = []
        self.mask_valid_data = []
        self.jkam_gage_matchlist = []
        self.color_array = []
        self.cumulative_data = []
        self.final_accepted = []
        self.start_time = None
        self.avg_time_gap = 0

        # Defaults (will be updated from GUI)
        self.time_me = False
        self.plot_tenth_shot = False
        self.het_freq = 0
        self.dds_freq = 0
        self.samp_freq = 0
        self.averaging_time = 0
        self.step_time = 0
        self.filter_time = 0
        self.voltage_conversion = 0
        self.kappa = 0
        self.LO_power = 0
        self.PHOTON_ENERGY = 0
        self.LO_rate = 0
        self.photonrate_conversion = 0

        # Window‐function choice (default 'hann')
        self.window = "hann"
        
        # *** NEW: add avg_time_gap attribute for acceptance in downstream handlers ***
        self.avg_time_gap = 0

        # Track which shot indexes we've already printed "Gage error at shot X" for
        self.gage_error_shots_reported = set()
        self.cmplx_amp_array = []
        self.timebin_array = []

    def process_file(self, file):
        self.gui.jkam_h5_file_handler.update_settings()

        try:
            file_ctime = os.path.getctime(file)
        except Exception as e:
            print(f"Error accessing file time for {file}: {e}")
            return

        # Prevent duplicates
        if file_ctime in self.gage_creation_time_array:
            return

        try:
            with h5py.File(file, 'r') as h5_file:
                ch1_data = {}
                ch3_data = {}
                for frame in range(3):
                    ch1_data[f'CH1_frame{frame}'] = np.array(h5_file[f'CH1_frame{frame}'])
                    ch3_data[f'CH3_frame{frame}'] = np.array(h5_file[f'CH3_frame{frame}'])
            self.gage_files.append({'CH1': ch1_data, 'CH3': ch3_data})
            self.gage_creation_time_array.append(file_ctime)

            if len(self.gage_creation_time_array) == 1:
                self.start_time = file_ctime

            self.rerun_acceptance_gage()

            new_shot_index = len(self.gage_creation_time_array) - 1
            data_valid = False
            jkam_space_correct_str = "None"

            if 0 <= new_shot_index < len(self.mask_valid_data):
                data_valid = self.mask_valid_data[new_shot_index]

            jkam_space_dict = self.gui.jkam_h5_file_handler.shots_dict
            if new_shot_index in jkam_space_dict:
                jkam_space_correct_str = str(jkam_space_dict[new_shot_index])

            row_position = self.gui.additional_table_2.rowCount()
            self.gui.additional_table_2.insertRow(row_position)
            self.gui.additional_table_2.setItem(row_position, 0, QTableWidgetItem(str(new_shot_index)))
            self.gui.additional_table_2.setItem(row_position, 1, QTableWidgetItem(file))
            self.gui.additional_table_2.setItem(row_position, 2, QTableWidgetItem(str(data_valid)))
            self.gui.additional_table_2.setItem(row_position, 3, QTableWidgetItem(jkam_space_correct_str))

            summary_text = (
                f"<b>Start Time:</b> {self.start_time}, "
                f"<b>Current Time:</b> {file_ctime}, "
                f"<b>Avg Time Gap:</b> {self.avg_time_gap}"
            )
            self.gui.additional_table_2.setItem(row_position, 4, QTableWidgetItem(summary_text))

            self.update_chart_3()

            self.gui.jkam_h5_file_handler.all_datapoints.append(file_ctime)
            self.gui.jkam_h5_file_handler.update_fft_plot()

        except Exception as e:
            print(f"Error processing GageScope file {file}: {e}")
            return

    def rerun_acceptance_gage(self):
        num_shots = len(self.gage_creation_time_array)

        if len(self.final_accepted) < num_shots:
            self.final_accepted += [False] * (num_shots - len(self.final_accepted))

        if num_shots <= 1:
            self.avg_time_gap = 0
        else:
            total_span = (self.gage_creation_time_array[-1] - self.gage_creation_time_array[0])
            self.avg_time_gap = total_span / (num_shots - 1)

        self.mask_valid_data = np.zeros(num_shots, dtype=bool)
        self.jkam_gage_matchlist = np.full(num_shots, -1, dtype=int)
        self.color_array = ["r"] * num_shots

        jkam_space_dict = self.gui.jkam_h5_file_handler.shots_dict
        jkam_time_temp_dict = self.gui.jkam_h5_file_handler.time_temp_dict

        gage_ctimes = np.array(self.gage_creation_time_array)
        gage_index_list = np.arange(num_shots)

        for shot_num in range(num_shots):
            if self.final_accepted[shot_num]:
                self.mask_valid_data[shot_num] = True
                self.color_array[shot_num] = "g"
                continue

            if shot_num in jkam_time_temp_dict and shot_num in jkam_space_dict:
                jkam_time = jkam_time_temp_dict[shot_num]
                space_correct = jkam_space_dict[shot_num]

                if space_correct:
                    if self.avg_time_gap == 0:
                        self.mask_valid_data[shot_num] = True
                        self.color_array[shot_num] = "g"
                        self.jkam_gage_matchlist[shot_num] = shot_num
                        self.final_accepted[shot_num] = True
                    else:
                        time_diffs = np.abs(gage_ctimes - jkam_time)
                        min_diff = np.min(time_diffs)
                        if min_diff <= 0.3 * self.avg_time_gap:
                            self.mask_valid_data[shot_num] = True
                            closest_idx = np.argmin(time_diffs)
                            self.jkam_gage_matchlist[shot_num] = gage_index_list[closest_idx]
                            self.color_array[shot_num] = "g"
                            self.final_accepted[shot_num] = True
                        else:
                            self.mask_valid_data[shot_num] = False
                            self.color_array[shot_num] = "r"
                            if shot_num not in self.gage_error_shots_reported:
                                print(f"Gage error at shot {shot_num}")
                                self.gage_error_shots_reported.add(shot_num)
                else:
                    self.mask_valid_data[shot_num] = False
                    self.color_array[shot_num] = "r"
            else:
                self.mask_valid_data[shot_num] = False
                self.jkam_gage_matchlist[shot_num] = -1

        self.cumulative_data = []
        last_success_count = 0
        highest_count = 0

        for shot_num in range(num_shots):
            if self.mask_valid_data[shot_num]:
                if not self.cumulative_data or self.cumulative_data[-1] == 0:
                    last_success_count = highest_count + 1
                else:
                    last_success_count += 1
                highest_count = max(highest_count, last_success_count)
                self.cumulative_data.append(last_success_count)
            else:
                self.cumulative_data.append(0)

    def update_chart_3(self):
        fig = self.gui.figures[3]
        fig.clear()
        ax = fig.add_subplot(111)

        x_vals = np.arange(len(self.cumulative_data))
        for i, val in enumerate(self.cumulative_data):
            ax.plot(x_vals[i], val, marker="o", color=self.color_array[i])
        ax.plot(x_vals, self.cumulative_data, linestyle="-", alpha=0.3)

        ax.set_title("Cumulative Accepted Files 3 (GageScope)")
        ax.set_xlabel("Shot Number")
        ax.set_ylabel("Cumulative Value")
        self.gui.canvases[3].draw()