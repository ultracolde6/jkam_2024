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
#                     Red Pitaya Handler (.txt)                               #
###############################################################################
class RedPitayaFileHandler:
    """
    Handles Red Pitaya .txt files with acceptance logic vs. JKAM data.
    Also contains method to auto-SCP from Red Pitaya into a local folder.
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

    def download_redpitaya_files(self):
        """
        Attempt to SSH into the Red Pitaya and SFTP-get the text files into the
        user-specified local directory. Adjust as needed for your environment.
        """
        host = "169.254.13.29"
        username = "root"
        password = "root"

        # This is where those files live on the Red Pitaya. Adjust if needed.
        remote_folder = "/root/RedPitaya/"

        # The files you want to copy over:
        rp_filenames = [
            "phicav.txt",
            "phiperp.txt",
            "cnstperp.txt",
            "histcav.txt",
            "histperp.txt",
            "lencav.txt",
            "lenperp.txt",
            "outcav.txt",
            "outperp.txt",
        ]

        # The local destination folder typed into the GUI:
        local_dir = self.gui.rp_download_dir_edit.text().strip()
        if not local_dir:
            print("No local Red Pitaya download directory specified. Skipping download.")
            return

        # Ensure local directory exists
        os.makedirs(local_dir, exist_ok=True)

        # Perform SFTP
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, username=username, password=password)

            sftp = client.open_sftp()

            for fname in rp_filenames:
                remote_file = os.path.join(remote_folder, fname)
                local_file = os.path.join(local_dir, fname)
                #i used print below for debugging but since its happening every 5 shots its gonna be too much so not doing it rn
                #print(f"Downloading {remote_file} -> {local_file}")
                sftp.get(remote_file, local_file)

            sftp.close()
            client.close()
            # Don't print this below either for same reason as above
            #print("Successfully downloaded Red Pitaya files.")
        except Exception as e:
            print(f"Error downloading from Red Pitaya: {e}")

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

