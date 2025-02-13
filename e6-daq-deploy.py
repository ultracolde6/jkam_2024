#UPDATED 2/12 MOST ADVANCED ONE YET WITH RED PITAYA GRAPHING

import sys
import time
import os
import warnings
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QWidget, QTabWidget, QGridLayout, QHeaderView,
    QLabel, QHBoxLayout, QLineEdit, QDockWidget, QCheckBox, QComboBox
)
from PyQt5.QtCore import QTimer, Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import h5py
from scipy import signal
import pickle

###############################################################################
#                          JKAM Handler                                       #
###############################################################################
class JkamH5FileHandler:
    def __init__(self, gui):
        self.gui = gui
        self.jkam_files = []  # We'll store file paths here

        # Data arrays
        self.jkam_creation_time_array = []  # Creation times for each shot
        self.shots_dict = {}                # {shot_index: space_correct_boolean}
        self.time_temp_dict = {}            # {shot_index: time_temp_value}

        # Tracking
        self.shots_num = 0
        self.last_passed_idx = 0
        self.start_time = None

        # For the JKAM chart
        self.cumulative_data = []
        self.highest_count = 0  # Track highest count reached

        # For the FFT chart
        self.all_datapoints = []

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

    def update_settings(self):
        """ Pull the current GUI settings into local variables. """
        self.time_me = self.gui.time_me_checkbox.isChecked()
        self.plot_tenth_shot = self.gui.plot_tenth_shot_checkbox.isChecked()
        self.het_freq = float(self.gui.het_freq_input.text())
        self.dds_freq = float(self.gui.dds_freq_input.text())
        self.samp_freq = float(self.gui.samp_freq_input.text())
        self.averaging_time = float(self.gui.averaging_time_input.text())
        self.step_time = float(self.gui.step_time_input.text())
        self.filter_time = float(self.gui.filter_time_input.text())
        self.voltage_conversion = float(self.gui.voltage_conversion_input.text())
        self.kappa = float(self.gui.kappa_input.text())
        self.LO_power = float(self.gui.LO_power_input.text())
        self.PHOTON_ENERGY = float(self.gui.PHOTON_ENERGY_input.text())
        self.LO_rate = float(self.gui.LO_rate_input.text())
        self.photonrate_conversion = float(self.gui.photonrate_conversion_input.text())

        # Window selection
        self.window = self.gui.window_select.currentText()

    def process_file(self, file):
        """
        Process a single JKAM .h5 file. We'll treat file creation time as "time_temp".
        """
        self.update_settings()

        try:
            file_ctime = os.path.getctime(file)
        except Exception as e:
            print(f"Error accessing file time for {file}: {e}")
            return

        # Skip if we already processed it
        if file in self.jkam_files:
            return

        # Verify we can open it
        try:
            with h5py.File(file, 'r'):
                pass
        except Exception as e:
            print(f"Error processing JKAM file {file}: {e}")
            return

        self.jkam_files.append(file)
        self.jkam_creation_time_array.append(file_ctime)

        jkam_avg_time_gap = 0
        space_correct = True
        time_temp = file_ctime

        if self.shots_num == 0:
            self.start_time = file_ctime
        else:
            jkam_avg_time_gap = abs((time_temp - self.start_time) / self.shots_num)
            if (self.shots_num > 0) & (
                abs(time_temp - self.jkam_creation_time_array[self.shots_num - 1]
                    - jkam_avg_time_gap) > 0.2 * jkam_avg_time_gap
            ):
                space_correct = False

        # Store
        self.shots_dict[self.shots_num] = space_correct
        self.time_temp_dict[self.shots_num] = time_temp

        # Cumulative data
        if self.shots_num == 0:
            new_val = 1
        elif space_correct:
            new_val = (self.cumulative_data[self.last_passed_idx] + 1) if self.cumulative_data else 1
        else:
            new_val = 0

        self.cumulative_data.append(new_val)
        if space_correct:
            self.last_passed_idx = self.shots_num
        self.shots_num += 1
        self.all_datapoints.append(file_ctime)
        
        # *** NEW: update the avg_time_gap attribute so that other file handlers can use it ***
        self.avg_time_gap = jkam_avg_time_gap

        # Update main JKAM table
        row_position = self.gui.table.rowCount()
        self.gui.table.insertRow(row_position)
        self.gui.table.setItem(row_position, 0, QTableWidgetItem(str(self.shots_num - 1)))
        self.gui.table.setItem(row_position, 1, QTableWidgetItem(file))
        self.gui.table.setItem(row_position, 2, QTableWidgetItem(str(space_correct)))
        summary_text = (
            f"<b>Start Time:</b> {self.start_time}, "
            f"<b>Current Time:</b> {file_ctime}, "
            f"<b>Avg Time Gap:</b> {jkam_avg_time_gap}"
        )
        self.gui.table.setItem(row_position, 3, QTableWidgetItem(summary_text))

        # Update JKAM chart & the FFT chart
        self.update_cumulative_plot()
        self.update_fft_plot()

    def update_cumulative_plot(self):
        fig = self.gui.figures[0]
        fig.clear()
        ax = fig.add_subplot(111)
        x_vals = range(len(self.cumulative_data))
        ax.plot(x_vals, self.cumulative_data, marker="o", linestyle="-")
        ax.set_title("Cumulative Accepted Files 1 (JKAM)")
        ax.set_xlabel("Shot Number")
        ax.set_ylabel("Cumulative Value")
        self.gui.canvases[0].draw()

    def update_fft_plot(self):
        """
        Attempt an FFT/demod plot if there's at least one valid GageScope shot.
        """
        self.update_settings()

        # We need at least some JKAM data
        if len(self.jkam_creation_time_array) < 1:
            return

        # We need at least one GageScope shot
        num_shots_gage = len(self.gui.gage_h5_file_handler.gage_files)
        if num_shots_gage == 0:
            return

        # If LO_rate or kappa <= 0, skip
        if (self.LO_rate <= 0) or (self.kappa <= 0):
            print("LO_rate or kappa is <= 0 -- skipping FFT computation.")
            return

        # If we are timing but GageScope has no creation times
        if self.time_me and (len(self.gui.gage_h5_file_handler.gage_creation_time_array) == 0):
            return

        heterodyne_conversion = 1 / np.sqrt(self.LO_rate)
        cavity_conversion = 1 / np.sqrt(self.kappa)
        conversion_factor = (self.voltage_conversion *
                             self.photonrate_conversion *
                             heterodyne_conversion *
                             cavity_conversion)

        # Example: define length from the first GageScope file
        chlen = len(self.gui.gage_h5_file_handler.gage_files[0]['CH1']['CH1_frame0'])
        t_vec = np.arange(chlen) * (1 / self.samp_freq)
        ch1_pure_vec = np.exp(-1j * 2 * np.pi * self.dds_freq * t_vec)
        ch3_pure_vec = np.exp(-1j * 2 * np.pi * self.het_freq * t_vec)

        # Generate a list of "start times" in samples
        t0_list = np.arange(0, chlen / self.samp_freq - self.filter_time + self.step_time, self.step_time)
        timebin_array = np.empty((len(t0_list), 2), dtype=float)
        timebin_array[:, 0] = t0_list
        timebin_array[:, 1] = t0_list + self.filter_time

        num_segments = 3
        cmplx_amp_array = np.empty((2, num_shots_gage, num_segments, len(t0_list)), dtype=np.cdouble)

        # Window
        window_function = self.window

        for shot_num in range(len(self.jkam_creation_time_array)):
            if (self.gui.gage_h5_file_handler.mask_valid_data is not None and
                shot_num < len(self.gui.gage_h5_file_handler.mask_valid_data) and
                self.gui.gage_h5_file_handler.mask_valid_data[shot_num]):

                if shot_num >= len(self.gui.gage_h5_file_handler.gage_files):
                    continue

                # Access channel data from memory
                gage_data = self.gui.gage_h5_file_handler.gage_files[shot_num]

                for seg_num in range(num_segments):
                    ch1 = gage_data['CH1'][f'CH1_frame{seg_num}'] * conversion_factor
                    ch3 = gage_data['CH3'][f'CH3_frame{seg_num}'] * conversion_factor

                    cmplx_amp_list_ch1 = t0_list * 0j
                    cmplx_amp_list_ch3 = t0_list * 0j

                    for i, t0_f in enumerate(t0_list):
                        t0_i = int(round(t0_f * self.samp_freq))
                        t1_i = t0_i + int(round(self.filter_time * self.samp_freq))

                        length = t1_i - t0_i
                        if length <= 0:
                            cmplx_amp_list_ch1[i] = np.nan
                            cmplx_amp_list_ch3[i] = np.nan
                            continue

                        if window_function == 'flattop':
                            w = signal.windows.flattop(length)
                        elif window_function == 'square':
                            w = 1
                        else:  # default 'hann'
                            w = signal.windows.hann(length) * 2

                        ch1_segment = ch1[t0_i:t1_i]
                        ch3_segment = ch3[t0_i:t1_i]

                        ch1_demod = ch1_segment * w * ch1_pure_vec[t0_i:t1_i]
                        ch3_demod = ch3_segment * w * ch3_pure_vec[t0_i:t1_i]

                        ch1_sum = np.cumsum(ch1_demod)
                        ch3_sum = np.cumsum(ch3_demod)

                        cmplx_amp_list_ch1[i] = (ch1_sum[-1] - ch1_sum[0]) / length
                        cmplx_amp_list_ch3[i] = (ch3_sum[-1] - ch3_sum[0]) / length

                    cmplx_amp_array[0, shot_num, seg_num] = cmplx_amp_list_ch1
                    cmplx_amp_array[1, shot_num, seg_num] = cmplx_amp_list_ch3

            else:
                if shot_num < cmplx_amp_array.shape[1]:
                    cmplx_amp_array[:, shot_num, :, :] = np.nan

        # Save results
        try:
            with open(
                f'C:\\Users\\jayom\\Downloads\\fft_gage_cmplx_amp_{self.filter_time}_{self.step_time}.pkl', 'wb'
            ) as f1:
                pickle.dump(cmplx_amp_array, f1)

            with open(
                f'C:\\Users\\jayom\\Downloads\\fft_gage_timebin_{self.filter_time}_{self.step_time}.pkl', 'wb'
            ) as f3:
                pickle.dump(timebin_array, f3)
        except Exception as e:
            print("Could not save FFT results to pickle:", e)

        # Plot something on figure[4]
        fig_fft = self.gui.figures[4]
        fig_fft.clear()
        ax = fig_fft.add_subplot(111)

        # Find valid shots that have data
        valid_shots = []
        for s in range(num_shots_gage):
            if (s < len(self.gui.gage_h5_file_handler.mask_valid_data) and
                self.gui.gage_h5_file_handler.mask_valid_data[s]):
                valid_shots.append(s)

        if not valid_shots:
            ax.text(0.5, 0.5, "No valid GageScope shots found for FFT plotting",
                    ha='center', va='center', transform=ax.transAxes)
        else:
            last_shot = valid_shots[-1]
            ch1_magnitude = np.abs(cmplx_amp_array[0, last_shot, 0, :])
            ax.plot(ch1_magnitude, label=f"Shot {last_shot}, CH1 seg0 (magnitude)")
            ax.set_title("FFT Magnitude (Segment 0, last valid shot)")
            ax.legend()

        self.gui.canvases[4].draw()


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

        # Track which shot indexes we've already printed "FPGA error at shot X" for
        self.fpga_error_shots_reported = set()

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
                        # Only print the error once per shot
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

        # Track which shot indexes we've already printed "Gage error at shot X" for
        self.gage_error_shots_reported = set()

    def process_file(self, file):
        self.gui.jkam_h5_file_handler.update_settings()

        try:
            file_ctime = os.path.getctime(file)
        except Exception as e:
            print(f"Error accessing file time for {file}: {e}")
            return

        # Check if we've already processed this ctime
        if file_ctime in self.gage_creation_time_array:
            return

        # Extract data
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

            # Re-run acceptance
            self.rerun_acceptance_gage()

            new_shot_index = len(self.gage_creation_time_array) - 1
            data_valid = False
            jkam_space_correct_str = "None"

            if 0 <= new_shot_index < len(self.mask_valid_data):
                data_valid = self.mask_valid_data[new_shot_index]

            jkam_space_dict = self.gui.jkam_h5_file_handler.shots_dict
            if new_shot_index in jkam_space_dict:
                jkam_space_correct_str = str(jkam_space_dict[new_shot_index])

            # Add row to GageScope table
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

            # Let JKAM code know we have another shot time
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

        # Recompute cumulative data
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


###############################################################################
#                     Red Pitaya Handler (.txt)                               #
###############################################################################
class RedPitayaFileHandler:
    """
    Handles Red Pitaya .txt files with acceptance logic vs. JKAM data.
    """
    def __init__(self, gui):
        self.gui = gui
        self.rp_files = []
        self.rp_times_list = []

        self.mask_valid_data_rp = []
        self.jkam_rp_matchlist = []
        self.color_array = []
        self.cumulative_data = []
        self.final_accepted = []

        self.cav_contrast = None
        self.perp_contrast = None
        self.cav_hist = None
        self.perp_hist = None
        self.cav_len = None
        self.perp_len = None
        self.cav_output = None
        self.perp_output = None
        self.cav_phase = None
        self.perp_phase = None

        self.done1 = 0
        self.done2 = 0
        self.done3 = 0
        self.done4 = 0

    def load_data(self, file):
        """ Helper to load data and ensure it is 2D. """
        try:
            data = np.loadtxt(file, dtype=float, delimiter=',')
            if data.ndim == 1:
                data = data.reshape(1, -1)
            return data
        except Exception as e:
            print(f"Error loading {file}: {e}")
            return None

    def process_file(self, file):
        self.gui.jkam_h5_file_handler.update_settings()

        if file in self.rp_files:
            return

        if not os.path.exists(file):
            print(f"File does not exist: {file}")
            return

        try:
            # Turn UserWarning into an exception to detect empty files
            with warnings.catch_warnings():
                warnings.simplefilter("error", UserWarning)
                filename_phase = np.loadtxt(file, dtype=float, delimiter=',')
        except UserWarning:
            print(f"Error: Red Pitaya file is empty: {file}")
            self.rp_files.append(file)
            self.rp_times_list.append(None)
            self.rerun_acceptance_rp()
            return
        except Exception as e:
            print(f"Failed to load Red Pitaya file {file}: {e}")
            self.rp_files.append(file)
            self.rp_times_list.append(None)
            self.rerun_acceptance_rp()
            return

        if filename_phase.size == 0:
            print(f"Error: Red Pitaya file is empty: {file}")
            self.rp_files.append(file)
            self.rp_times_list.append(None)
            self.rerun_acceptance_rp()
            return
        
        if len(filename_phase.shape) == 1:
            filename_phase = filename_phase.reshape(1, -1)

        rp_creation_time_array = filename_phase[:, 0]

        self.rp_files.append(file)
        self.rp_times_list.append(rp_creation_time_array)
        self.rerun_acceptance_rp()

        new_shot_index = len(self.rp_files) - 1
        data_valid = False
        if 0 <= new_shot_index < len(self.mask_valid_data_rp):
            data_valid = self.mask_valid_data_rp[new_shot_index]

        jkam_space_correct_str = "None"
        jkam_space_dict = self.gui.jkam_h5_file_handler.shots_dict
        if new_shot_index in jkam_space_dict:
            jkam_space_correct_str = str(jkam_space_dict[new_shot_index])

        row_position = self.gui.additional_table_3.rowCount()
        self.gui.additional_table_3.insertRow(row_position)
        self.gui.additional_table_3.setItem(row_position, 0, QTableWidgetItem(str(new_shot_index)))
        self.gui.additional_table_3.setItem(row_position, 1, QTableWidgetItem(file))
        self.gui.additional_table_3.setItem(row_position, 2, QTableWidgetItem(str(data_valid)))
        self.gui.additional_table_3.setItem(row_position, 3, QTableWidgetItem(jkam_space_correct_str))

        info_str = (
            "No Data"
            if (rp_creation_time_array is None or len(rp_creation_time_array) == 0)
            else f"RP Times Count: {len(rp_creation_time_array)}"
        )
        self.gui.additional_table_3.setItem(row_position, 4, QTableWidgetItem(info_str))

        # Load additional Red Pitaya files based on filename substrings
        if 'cnstcav' in file:
            self.cav_contrast = self.load_data(file)
        if 'cnstperp' in file:
            self.perp_contrast = self.load_data(file)
        if 'histcav' in file:
            self.cav_hist = self.load_data(file)
        if 'histperp' in file:
            self.perp_hist = self.load_data(file)
        if 'lencav' in file:
            self.cav_len = self.load_data(file)
        if 'lenperp' in file:
            self.perp_len = self.load_data(file)
        if 'outcav' in file:
            self.cav_output = self.load_data(file)
        if 'outperp' in file:
            self.perp_output = self.load_data(file)
        if 'phicav' in file:
            self.cav_phase = self.load_data(file)
        if 'phiperp' in file:
            self.perp_phase = self.load_data(file)

        self.update_chart_rp()
        self.update_unique_rp()

    def rerun_acceptance_rp(self):
        num_shots = len(self.rp_files)

        if len(self.final_accepted) < num_shots:
            self.final_accepted += [False] * (num_shots - len(self.final_accepted))

        self.mask_valid_data_rp = [False] * num_shots
        self.jkam_rp_matchlist = [-1] * num_shots
        self.color_array = ["r"] * num_shots
        self.cumulative_data = []
        highest_count = 0
        last_success_count = 0

        jkam_space_dict = self.gui.jkam_h5_file_handler.shots_dict
        jkam_time_temp_dict = self.gui.jkam_h5_file_handler.time_temp_dict
        jkam_avg_time_gap = self.gui.jkam_h5_file_handler.avg_time_gap

        for shot_num in range(num_shots):
            if self.final_accepted[shot_num]:
                self.mask_valid_data_rp[shot_num] = True
                self.color_array[shot_num] = "g"
                if not self.cumulative_data or self.cumulative_data[-1] == 0:
                    last_success_count = highest_count + 1
                else:
                    last_success_count += 1
                highest_count = max(highest_count, last_success_count)
                self.cumulative_data.append(last_success_count)
                continue

            rp_creation_time_array = self.rp_times_list[shot_num]
            if rp_creation_time_array is None or len(rp_creation_time_array) == 0:
                self.mask_valid_data_rp[shot_num] = False
                self.color_array[shot_num] = "r"
                self.jkam_rp_matchlist[shot_num] = -1
                self.cumulative_data.append(0)
                continue

            if (shot_num not in jkam_time_temp_dict) or (shot_num not in jkam_space_dict):
                self.mask_valid_data_rp[shot_num] = False
                self.color_array[shot_num] = "r"
                self.jkam_rp_matchlist[shot_num] = -1
                self.cumulative_data.append(0)
                continue

            time_temp = jkam_time_temp_dict[shot_num]
            jkam_space_correct = jkam_space_dict[shot_num]

            if jkam_space_correct:
                rp_index_list = np.arange(len(rp_creation_time_array))
                min_diff = np.min(np.abs(rp_creation_time_array - time_temp))
                if (jkam_avg_time_gap != 0) and (min_diff <= 0.3 * jkam_avg_time_gap):
                    self.mask_valid_data_rp[shot_num] = True
                    idx = np.argmin(np.abs(rp_creation_time_array - time_temp))
                    self.jkam_rp_matchlist[shot_num] = rp_index_list[idx]
                    self.color_array[shot_num] = "g"
                    self.final_accepted[shot_num] = True
                    if not self.cumulative_data or self.cumulative_data[-1] == 0:
                        last_success_count = highest_count + 1
                    else:
                        last_success_count += 1
                    highest_count = max(highest_count, last_success_count)
                    self.cumulative_data.append(last_success_count)
                else:
                    print(f"error at {shot_num}")
                    self.mask_valid_data_rp[shot_num] = False
                    self.color_array[shot_num] = "r"
                    self.jkam_rp_matchlist[shot_num] = -1
                    self.cumulative_data.append(0)
            else:
                print(f"error at {shot_num}")
                self.mask_valid_data_rp[shot_num] = False
                self.color_array[shot_num] = "r"
                self.jkam_rp_matchlist[shot_num] = -1
                self.cumulative_data.append(0)

    def update_chart_rp(self):
        fig = self.gui.figures[2]
        fig.clear()
        ax = fig.add_subplot(111)

        x_vals = np.arange(len(self.cumulative_data))
        for i, val in enumerate(self.cumulative_data):
            ax.plot(x_vals[i], val, marker="o", color=self.color_array[i])
        ax.plot(x_vals, self.cumulative_data, linestyle="-", alpha=0.3)

        ax.set_title("Cumulative Accepted Files (Red Pitaya)")
        ax.set_xlabel("Shot Number")
        ax.set_ylabel("Cumulative Value")
        self.gui.canvases[2].draw()

    def update_unique_rp(self):
        # Graph 5: cav_len and perp_len
        if self.done1 == 0 and self.cav_len is not None and self.perp_len is not None:
            if self.cav_len.ndim == 2 and self.cav_len.shape[1] >= 2 and \
               self.perp_len.ndim == 2 and self.perp_len.shape[1] >= 2:
                self.done1 = 1
                fig = self.gui.figures[5]
                fig.clear()
                ax = fig.add_subplot(111)
                ax.plot(self.cav_len[:, 0], self.cav_len[:, 1], label="cav_len(locked)")
                ax.plot(self.perp_len[:, 0], self.perp_len[:, 1], label="perp_len(locked)")
                ax.legend()
                self.gui.canvases[5].draw()
            else:
                print("Invalid data shape for lencav or lenperp. Skipping graph 5.")

        # Graph 6: cav_contrast and perp_contrast
        if self.done2 == 0 and self.cav_contrast is not None and self.perp_contrast is not None:
            if self.cav_contrast.ndim == 2 and self.cav_contrast.shape[1] >= 2 and \
               self.perp_contrast.ndim == 2 and self.perp_contrast.shape[1] >= 2:
                self.done2 = 1
                fig = self.gui.figures[6]
                fig.clear()
                ax = fig.add_subplot(111)
                ax.plot(self.cav_contrast[:, 0], self.cav_contrast[:, 1], label="cav_contrast")
                ax.plot(self.perp_contrast[:, 0], self.perp_contrast[:, 1], label="perp_contrast")
                ax.legend()
                self.gui.canvases[6].draw()
            else:
                print("Invalid data shape for cav_contrast or perp_contrast. Skipping graph 6.")

        # Graph 7: cav_output and perp_output
        if self.done3 == 0 and self.cav_output is not None and self.perp_output is not None:
            if self.cav_output.ndim == 2 and self.cav_output.shape[1] >= 2 and \
               self.perp_output.ndim == 2 and self.perp_output.shape[1] >= 2:
                self.done3 = 1
                fig = self.gui.figures[7]
                fig.clear()
                ax = fig.add_subplot(111)
                ax.plot(self.cav_output[:, 0], self.cav_output[:, 1], label="cav_output")
                ax.plot(self.perp_output[:, 0], self.perp_output[:, 1], label="perp_output")
                ax.set_ylim(-1.2, 1.2)
                ax.legend()
                self.gui.canvases[7].draw()
            else:
                print("Invalid data shape for cav_output or perp_output. Skipping graph 7.")

        # Graph 8: cav_phase and perp_phase
        num_shot_start = 0
        if self.done4 == 0 and self.cav_phase is not None and self.perp_phase is not None:
            if self.cav_phase.ndim == 2 and self.cav_phase.shape[1] >= 2 and \
               self.perp_phase.ndim == 2 and self.perp_phase.shape[1] >= 2:
                self.done4 = 1
                fig = self.gui.figures[8]
                fig.clear()
                ax = fig.add_subplot(111)
                ax.plot(self.cav_phase[:, 0], self.cav_phase[:, 1], label="cav_phase")
                ax.plot(self.perp_phase[:, 0], self.perp_phase[:, 1], label="perp_phase")
                ax.axhline(0.11, c='k')
                ax.axhline(-0.11, c='k')
                ax.axvline(self.cav_phase[num_shot_start, 0], c='k')
                ax.legend()
                self.gui.canvases[8].draw()
            else:
                print("Invalid data shape for cav_phase or perp_phase. Skipping graph 8.")


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
        self.window_select.setCurrentIndex(0)  # default = hann
        self.feature_options_layout.addWidget(self.window_select_label)
        self.feature_options_layout.addWidget(self.window_select)

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
        self.tabs.addTab(self.chart_tab, "Charts")

        # JKAM table tab
        self.table_tab = QWidget()
        self.table_layout = QVBoxLayout(self.table_tab)
        self.tabs.addTab(self.table_tab, "JKAM Data Table")

        # FPGA table tab
        self.additional_table_tab_1 = QWidget()
        self.additional_table_tab_1_layout = QVBoxLayout(self.additional_table_tab_1)
        self.tabs.addTab(self.additional_table_tab_1, "Additional Table 1 (FPGA)")

        # GageScope table tab
        self.additional_table_tab_2 = QWidget()
        self.additional_table_tab_2_layout = QVBoxLayout(self.additional_table_tab_2)
        self.tabs.addTab(self.additional_table_tab_2, "Additional Table 2 (GageScope)")

        # Red Pitaya table tab
        self.additional_table_tab_3 = QWidget()
        self.additional_table_tab_3_layout = QVBoxLayout(self.additional_table_tab_3)
        self.tabs.addTab(self.additional_table_tab_3, "Additional Table 3 (Red Pitaya)")

        # FFT Graph tab
        self.fft_tab = QWidget()
        self.fft_tab_layout = QVBoxLayout(self.fft_tab)
        self.tabs.addTab(self.fft_tab, "FFT Graph")

        # Red Pitaya Visualizations Tab
        self.rp_tab = QWidget()
        self.rp_tab_layout = QGridLayout(self.rp_tab)
        self.tabs.addTab(self.rp_tab, "Red Pitaya Graphs")

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

        # Set up 9 figures
        self.figures = [Figure() for _ in range(9)]
        self.canvases = [FigureCanvas(fig) for fig in self.figures]

        # Place 4 figures (charts) in a 2x2 layout
        self.chart_layout.addWidget(self.canvases[0], 0, 0)
        self.chart_layout.addWidget(self.canvases[1], 0, 1)
        self.chart_layout.addWidget(self.canvases[2], 1, 0)
        self.chart_layout.addWidget(self.canvases[3], 1, 1)

        # "Add Files" button in Charts tab
        self.add_file_button_charts = QPushButton("Add Files")
        self.add_file_button_charts.clicked.connect(self.add_files)
        self.chart_layout.addWidget(self.add_file_button_charts, 2, 0, 1, 2)

        # The FFT chart is figure[4]
        self.fft_tab_layout.addWidget(self.canvases[4])

        # Red pitaya 4 graphs setup
        self.rp_tab_layout.addWidget(self.canvases[5], 0, 0)
        self.rp_tab_layout.addWidget(self.canvases[6], 0, 1)
        self.rp_tab_layout.addWidget(self.canvases[7], 1, 0)
        self.rp_tab_layout.addWidget(self.canvases[8], 1, 1)

        # Initialize subplots
        self.initialize_plot(0, "Cumulative Accepted Files 1 (JKAM)")
        self.initialize_plot(1, "Cumulative Accepted Files 2 (Bin/FPGA)")
        self.initialize_plot(2, "Cumulative Accepted Files (Red Pitaya)")
        self.initialize_plot(3, "Cumulative Accepted Files 3 (GageScope)")
        self.initialize_fft_plot(4)

        self.initialize_rp_plot(5)
        self.initialize_rp_plot(6)
        self.initialize_rp_plot(7)
        self.initialize_rp_plot(8)

        # Streaming Controls
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
        ax.plot([], [], marker="o")
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
        """
        Recursively checks subfolders (RedPitaya, PhotonTimer, High NA Imaging, gage, etc.)
        The acceptance logic for JKAM, GageScope, FPGA, or Red Pitaya remains unchanged;
        only how we scan for new files is adjusted.
        """
        if not self.inputs_accepted:
            return

        watch_dir = self.stream_dir_edit.text()
        if not os.path.isdir(watch_dir):
            print(f"Invalid stream directory: {watch_dir}")
            return

        # Look into each subfolder in watch_dir
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
        """Clean up resources before closing."""
        self.cleanup()
        super().closeEvent(event)

    def cleanup(self):
        """Release resources."""
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
