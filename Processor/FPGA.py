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
#                      FPGA / Bin Handler                                     #
###############################################################################
class BinFileHandler:
    """
    Handles FPGA .bin files with acceptance logic against JKAM data.
    """
    def __init__(self, gui):
        self.gui = gui

        self.bin_files = []
        self.fpga_creation_time_array = []
        self.mask_valid_data = []
        self.jkam_fpga_matchlist = []
        self.color_array = []
        self.cumulative_data = []
        self.highest_count = 0
        self.final_accepted = []
        self.start_time = None
        self.avg_time_gap = 0
        # For FPGA graphing, we only store the essential timestamp data.
        self.PT_cavity_timestamp_array_raw = []

        # Track which shot indexes we've already printed "FPGA error at shot X" for
        self.fpga_error_shots_reported = set()

    def update_fpga_graph(self, filename):
        unit_time_PT = 1/700  # in microseconds

        # Read the binary file and unpack bits
        raw_data = np.fromfile(filename, dtype=np.uint8)
        bin_data = np.unpackbits(raw_data)
        # Reshape into events of 32 bits each
        events = bin_data.reshape(-1, 32)
        # Pre-calculate weights for the first 25 bits (time portion)
        tparts = np.concatenate((np.flip(2**np.arange(8)),
                                 np.flip(2**np.arange(8,16)),
                                 np.flip(2**np.arange(16,24)),
                                 [16777216]))
        # Vectorized dot product to compute timestamps for each event
        timestamps = events[:, :25].dot(tparts)
        # Sort and convert to time units
        timestamps = unit_time_PT * np.sort(timestamps)

        # Store the timestamps for this shot
        self.PT_cavity_timestamp_array_raw.append(timestamps)

        # Plot the FPGA atom input times using a line or scatter
        fig = self.gui.figures[9]
        fig.clear()
        ax = fig.add_subplot(111)
        if timestamps.size == 0:
            ax.text(0.5, 0.5, "No FPGA timestamps", ha='center', va='center', transform=ax.transAxes)
        else:
            # ax.stem(timestamps, np.ones_like(timestamps), linefmt='b-', markerfmt='bo', basefmt=" ")
            ax.plot(timestamps, np.arange(len(timestamps)), ls='-', marker='o', color='b')
        ax.set_title("FPGA Photon Input Times")
        ax.set_xlabel("Time (us)")
        ax.set_ylabel("Photons In Count")
        self.gui.canvases[9].draw()

    def process_file(self, file):
        self.gui.jkam_h5_file_handler.update_settings()

        if file in self.bin_files:
            return

        try:
            file_ctime = os.path.getctime(file)
        except Exception as e:
            print(f"Error accessing file time for {file}: {e}")
            return

        self.bin_files.append(file)
        self.fpga_creation_time_array.append(file_ctime)

        if len(self.fpga_creation_time_array) == 1:
            self.start_time = file_ctime

        self.rerun_acceptance()

        new_shot_index = len(self.fpga_creation_time_array) - 1
        data_valid = False
        jkam_space_correct_str = "None"

        if 0 <= new_shot_index < len(self.mask_valid_data):
            data_valid = self.mask_valid_data[new_shot_index]

        jkam_space_dict = self.gui.jkam_h5_file_handler.shots_dict
        if new_shot_index in jkam_space_dict:
            jkam_space_correct_str = str(jkam_space_dict[new_shot_index])

        row_position = self.gui.additional_table_1.rowCount()
        self.gui.additional_table_1.insertRow(row_position)
        self.gui.additional_table_1.setItem(row_position, 0, QTableWidgetItem(str(new_shot_index)))
        self.gui.additional_table_1.setItem(row_position, 1, QTableWidgetItem(file))
        self.gui.additional_table_1.setItem(row_position, 2, QTableWidgetItem(str(data_valid)))
        self.gui.additional_table_1.setItem(row_position, 3, QTableWidgetItem(jkam_space_correct_str))

        summary_text = (
            f"<b>Start Time:</b> {self.start_time}, "
            f"<b>Current Time:</b> {file_ctime}, "
            f"<b>Avg Time Gap:</b> {self.avg_time_gap}"
        )
        self.gui.additional_table_1.setItem(row_position, 4, QTableWidgetItem(summary_text))

        self.update_fpga_graph(file)
        self.update_chart_2()

    def rerun_acceptance(self):
        self.highest_count = 0
        num_shots = len(self.fpga_creation_time_array)

        if len(self.final_accepted) < num_shots:
            self.final_accepted += [False] * (num_shots - len(self.final_accepted))

        if num_shots <= 1:
            self.avg_time_gap = 0
        else:
            total_span = abs(self.fpga_creation_time_array[-1] - self.fpga_creation_time_array[0])
            self.avg_time_gap = abs(total_span / (num_shots - 1))

        self.mask_valid_data = np.zeros(num_shots, dtype=bool)
        self.jkam_fpga_matchlist = np.full(num_shots, -1, dtype=int)
        self.color_array = ["r"] * num_shots

        jkam_space_dict = self.gui.jkam_h5_file_handler.shots_dict
        jkam_time_temp_dict = self.gui.jkam_h5_file_handler.time_temp_dict

        fpga_ctimes = np.array(self.fpga_creation_time_array)
        fpga_index_list = np.arange(num_shots)

        for shot_num in range(num_shots):
            if self.final_accepted[shot_num]:
                self.mask_valid_data[shot_num] = True
                self.color_array[shot_num] = "g"
                continue

            if shot_num in jkam_time_temp_dict and shot_num in jkam_space_dict:
                jkam_time = jkam_time_temp_dict[shot_num]
                space_correct = jkam_space_dict[shot_num]

                if self.avg_time_gap == 0:
                    if space_correct:
                        self.mask_valid_data[shot_num] = True
                        self.color_array[shot_num] = "g"
                        self.jkam_fpga_matchlist[shot_num] = shot_num
                        self.final_accepted[shot_num] = True
                    else:
                        self.mask_valid_data[shot_num] = False
                        self.color_array[shot_num] = "r"
                else:
                    time_diffs = np.abs(fpga_ctimes - jkam_time)
                    min_diff = np.min(time_diffs)
                    if (min_diff <= 0.3 * self.avg_time_gap) and space_correct:
                        self.mask_valid_data[shot_num] = True
                        closest_idx = np.argmin(time_diffs)
                        self.jkam_fpga_matchlist[shot_num] = fpga_index_list[closest_idx]
                        self.color_array[shot_num] = "g"
                        self.final_accepted[shot_num] = True
                    else:
                        self.mask_valid_data[shot_num] = False
                        self.color_array[shot_num] = "r"
                        if shot_num not in self.fpga_error_shots_reported:
                            print(f"FPGA error at shot {shot_num}")
                            self.fpga_error_shots_reported.add(shot_num)
            else:
                self.mask_valid_data[shot_num] = False
                self.jkam_fpga_matchlist[shot_num] = -1

        self.cumulative_data = []
        current_count = 0

        for shot_num in range(num_shots):
            if self.mask_valid_data[shot_num]:
                if not self.cumulative_data or self.cumulative_data[-1] == 0:
                    current_count = self.highest_count + 1
                else:
                    current_count += 1
                self.highest_count = max(self.highest_count, current_count)
                self.cumulative_data.append(current_count)
            else:
                self.cumulative_data.append(0)

    def update_chart_2(self):
        fig = self.gui.figures[1]
        fig.clear()
        ax = fig.add_subplot(111)

        x_vals = np.arange(len(self.cumulative_data))
        for i, val in enumerate(self.cumulative_data):
            ax.plot(x_vals[i], val, marker="o", color=self.color_array[i])
        ax.plot(x_vals, self.cumulative_data, linestyle="-", alpha=0.3)
        ax.set_title("Cumulative Accepted Files 2 (Bin/FPGA)")
        ax.set_xlabel("Shot Number")
        ax.set_ylabel("Cumulative Value")
        self.gui.canvases[1].draw()
