import sys
import time
import os
import warnings
import numpy as np
import h5py
import pickle
from scipy import signal

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QWidget, QTabWidget, QGridLayout, QHeaderView,
    QLabel, QHBoxLayout, QLineEdit, QDockWidget, QCheckBox, QComboBox
)
from PyQt5.QtCore import QTimer, Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


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

        if self.shots_num % 5 == 0:
            # Attempt to download the Red Pitaya files into the user‐specified folder - if folder isnt specified then it;ll just say print saying cant save
            self.gui.redpitaya_handler.download_redpitaya_files()

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
        # check that file masks exist and that the shot is valid
        for shot_num in range(len(self.jkam_creation_time_array)):
            if (self.gui.gage_h5_file_handler.mask_valid_data is not None and
                shot_num < len(self.gui.gage_h5_file_handler.mask_valid_data) and
                self.gui.gage_h5_file_handler.mask_valid_data[shot_num]):

                if shot_num >= len(self.gui.gage_h5_file_handler.gage_files):
                    continue

                # Access channel data from memory
                gage_data = self.gui.gage_h5_file_handler.gage_files[shot_num]
                print("Accessed gage file: ", gage_data)

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

