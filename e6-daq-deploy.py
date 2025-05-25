#4/29 version 2 with atom survival/brightness plots and trap loadings - revert back to 3/13 or 2/19 versions if doesn't work cause this one only tested locally and unsure if outputs are correct at all
#Prev one was 3/13 Red Pitaya atomatic file ingestion Integration - hopefully works only tested locally - (2/19?) was more basic working version 
import sys
import time
import os
import warnings
import traceback
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QWidget, QTabWidget, QGridLayout, QHeaderView,
    QLabel, QHBoxLayout, QLineEdit, QDockWidget, QCheckBox, QComboBox
)
from PyQt5.QtCore import QTimer, Qt, QRunnable, QThreadPool, pyqtSlot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import h5py
from scipy import signal
import pickle
import paramiko

# -------------------- ROI Definitions --------------------
roi_width = 16
roi_height = 16
roi_area = roi_width * roi_height

def roi_center(tweezer_freq):
    center_x = round(2 * (0.01 * (tweezer_freq - 108)**2 + 26.8 * (tweezer_freq - 100) + 414)) / 2
    center_y = round(2 * (-0.5 * (tweezer_freq - 100) + 28)) / 2
    return [center_x, center_y]

def roi_slice_func(tweezer_freq):
    cx, cy = roi_center(tweezer_freq)
    y0 = round(cy - roi_height/2)
    y1 = round(cy + roi_height/2)
    x0 = round(cx - roi_width/2)
    x1 = round(cx + roi_width/2)
    return (slice(y0, y1, 1), slice(x0, x1, 1))

# -------------------- Atom-Level Analysis --------------------
class AtomAnalysisHandler:
    def __init__(self, gui, batch_size: int = 5):
        self.gui = gui
        self.batch_size = batch_size
        self.num_frames = 3
        self.tweezer_freq_list = 88 + 0.8 * np.arange(40)
        self.num_tweezers = len(self.tweezer_freq_list)
        thresh = 400 * np.ones(self.num_tweezers)
        self.upper_threshold_mat = [thresh] * self.num_frames
        self._buffer = []
        self._history = []

    def add_shot(self, brightness_tensor: np.ndarray):
        # updating the trap‐status table in real time (am uisng the first frame as "loaded" indicator)
        exists = brightness_tensor[0, :] > self.upper_threshold_mat[0]
        self.gui.update_trap_table(exists.astype(int))

        if brightness_tensor.shape != (self.num_frames, self.num_tweezers):
            print("[AtomAnalysis] bad tensor shape", brightness_tensor.shape)
            return
        self._buffer.append(brightness_tensor)
        self._history.append(brightness_tensor)
        if len(self._buffer) >= self.batch_size:
            self._compute_and_draw()
            self._buffer.clear()

    def _compute_and_draw(self):
        arr = np.stack(self._history, axis=0)
        N = arr.shape[0]
        existence = np.zeros_like(arr, dtype=bool)
        for f in range(self.num_frames):
            existence[:, f, :] = arr[:, f, :] > self.upper_threshold_mat[f]

        survival = np.full(self.num_tweezers, np.nan)
        surv_err = np.full(self.num_tweezers, np.nan)
        brightness = np.full(self.num_tweezers, np.nan)
        bright_err = np.full(self.num_tweezers, np.nan)

        for tw in range(self.num_tweezers):
            loaded_mask  = existence[:, 0, tw]                    
            survive_mask = np.logical_and(loaded_mask, existence[:, 1, tw])  

            loaded = loaded_mask.sum()
            if loaded > 0:
                surv_val     = survive_mask.sum() / loaded
                survival[tw] = surv_val
                surv_err[tw] = np.sqrt(surv_val * (1 - surv_val) / loaded)
                brightness[tw] = np.nanmean(arr[:, 0, tw][loaded_mask])
                bright_err[tw] = np.nanstd(arr[:, 0, tw][loaded_mask])

        loading = np.sum(existence[:,0,:], axis=0) / N
        self._draw(survival, surv_err, loading, brightness, bright_err)

    def _draw(self, surv, s_err, load, bright, b_err):
        fig = self.gui.figures[10]
        fig.clear()
        ax = fig.add_subplot(111)
        ax.errorbar(self.tweezer_freq_list, surv, yerr=s_err, marker='o', ls='-', label='Survival')
        ax.plot(self.tweezer_freq_list, load, marker='x', ls='--', label='Loading')
        ax.errorbar(self.tweezer_freq_list, bright/1000, yerr=b_err/1000,
                    marker='s', ls=':', label='Brightness×1e3')
        ax.set_ylim(0, 1.1)
        ax.set_xlabel('Tweezer Freq (MHz)')
        ax.set_title('Per-Tweezer Metrics (Rolling)')
        ax.legend()
        self.gui.canvases[10].draw()

# -------------------- Worker --------------------
class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
    @pyqtSlot()
    def run(self):
        self.fn(*self.args, **self.kwargs)

# -------------------- JKAM Handler --------------------
class JkamH5FileHandler:
    def __init__(self, gui):
        self.gui = gui
        self.jkam_files = []
        self.jkam_creation_time_array = []
        self.shots_dict = {}
        self.time_temp_dict = {}
        self.shots_num = 0
        self.last_passed_idx = 0
        self.start_time = None
        self.cumulative_data = []
        self.highest_count = 0
        self.all_datapoints = []
        self.time_me = False
        self.plot_tenth_shot = False
        self.het_freq = self.dds_freq = self.samp_freq = 0
        self.averaging_time = self.step_time = self.filter_time = 0
        self.voltage_conversion = self.kappa = self.LO_power = self.PHOTON_ENERGY = 0
        self.LO_rate = self.photonrate_conversion = 0
        self.window = "hann"
        self.avg_time_gap = 0

    def update_settings(self):
        g = self.gui
        self.time_me = g.time_me_checkbox.isChecked()
        self.plot_tenth_shot = g.plot_tenth_shot_checkbox.isChecked()
        self.het_freq = float(g.het_freq_input.text())
        self.dds_freq = float(g.dds_freq_input.text())
        self.samp_freq = float(g.samp_freq_input.text())
        self.averaging_time = float(g.averaging_time_input.text())
        self.step_time = float(g.step_time_input.text())
        self.filter_time = float(g.filter_time_input.text())
        self.voltage_conversion = float(g.voltage_conversion_input.text())
        self.kappa = float(g.kappa_input.text())
        self.LO_power = float(g.LO_power_input.text())
        self.PHOTON_ENERGY = float(g.PHOTON_ENERGY_input.text())
        self.LO_rate = float(g.LO_rate_input.text())
        self.photonrate_conversion = float(g.photonrate_conversion_input.text())
        self.window = g.window_select.currentText()

    def process_file(self, file):
        self.update_settings()
        try:
            file_ctime = os.path.getctime(file)
        except Exception as e:
            print(f"Error accessing file time for {file}: {e}")
            return
        if file in self.jkam_files:
            return
        # Validate HDF5
        try:
            with h5py.File(file, 'r'): pass
        except Exception as e:
            print(f"Error processing JKAM file {file}: {e}")
            return
        num_tweezers = len(self.gui.atom_analysis_handler.tweezer_freq_list)
        num_frames = 3
        counts = np.zeros((num_frames, num_tweezers))
        try:
            hf = h5py.File(file, 'r')
            for f in range(num_frames):
                ds = hf.get(f'frame-{str(f+2).zfill(2)}')
                if ds is None:
                    raise KeyError(f"Missing dataset frame-{str(f+2).zfill(2)}")
                photo = np.array(ds)
                for t_idx, tf in enumerate(self.gui.atom_analysis_handler.tweezer_freq_list):
                    counts[f, t_idx] = np.sum(photo[roi_slice_func(tf)])
            hf.close()
        except Exception as e:
            print(f"Error computing counts for {file}: {e}")
            traceback.print_exc()
            return
        brightness = np.zeros_like(counts)
        brightness[0, :] = counts[0, :]
        for f in range(1, num_frames):
            brightness[f, :] = counts[f, :] - counts[0, :]
        # Register shot
        self.jkam_files.append(file)
        self.jkam_creation_time_array.append(file_ctime)
        if self.shots_num == 0:
            self.start_time = file_ctime
            self.shots_dict[0] = True
            self.avg_time_gap = 0
        else:
            gap = abs((file_ctime - self.start_time) / self.shots_num)
            prev = file_ctime - self.jkam_creation_time_array[self.shots_num - 1]
            space_ok = abs(prev - gap) <= 0.2 * gap
            self.shots_dict[self.shots_num] = space_ok
            self.avg_time_gap = gap
        self.time_temp_dict[self.shots_num] = file_ctime
        if self.shots_num == 0 or self.shots_dict[self.shots_num]:
            val = (self.cumulative_data[self.last_passed_idx] + 1) if self.cumulative_data else 1
            self.cumulative_data.append(val)
            if self.shots_dict[self.shots_num]:
                self.last_passed_idx = self.shots_num
        else:
            self.cumulative_data.append(0)
        self.shots_num += 1
        self.all_datapoints.append(file_ctime)
        row = self.gui.table.rowCount()
        self.gui.table.insertRow(row)
        self.gui.table.setItem(row, 0, QTableWidgetItem(str(self.shots_num - 1)))
        self.gui.table.setItem(row, 1, QTableWidgetItem(file))
        self.gui.table.setItem(row, 2, QTableWidgetItem(str(self.shots_dict[self.shots_num - 1])))
        summary = (f"<b>Start Time:</b> {self.start_time}, "
                   f"<b>Current Time:</b> {file_ctime}, "
                   f"<b>Avg Time Gap:</b> {self.avg_time_gap:.3f}")
        self.gui.table.setItem(row, 3, QTableWidgetItem(summary))
        self.update_cumulative_plot()
        self.update_fft_plot()
        self.gui.atom_analysis_handler.add_shot(brightness)
        # download RP files automatically BUT MAY HAVE TO COMMENT OUT NEXT 2 LINES IF TESTING LOCALLY WHILE NOT CONNECTED TO RED PITAYA
        if self.shots_num % 5 == 0:
            self.gui.redpitaya_handler.download_redpitaya_files()

    def update_cumulative_plot(self):
        fig = self.gui.figures[0]; fig.clear()
        ax = fig.add_subplot(111)
        ax.plot(range(len(self.cumulative_data)), self.cumulative_data, marker='o')
        ax.set_title("Cumulative Accepted Files 1 (JKAM)")
        ax.set_xlabel("Shot Number"); ax.set_ylabel("Cumulative Value")
        self.gui.canvases[0].draw()

    def update_fft_plot(self):
        try:
            num_g = len(self.gui.gage_h5_file_handler.gage_files)
            if num_g < 2 or self.LO_rate <= 0 or self.kappa <= 0:
                return
            het_c = 1/np.sqrt(self.LO_rate)
            cav_c = 1/np.sqrt(self.kappa)
            conv = (self.voltage_conversion *
                    self.photonrate_conversion *
                    het_c * cav_c)
            base = self.gui.gage_h5_file_handler.gage_files[0]['CH1']['CH1_frame0']
            chlen = len(base)
            t_vec = np.arange(chlen) * (1 / self.samp_freq)
            pure1 = np.exp(-1j * 2 * np.pi * self.dds_freq * t_vec)
            pure3 = np.exp(-1j * 2 * np.pi * self.het_freq * t_vec)
            t0 = np.arange(0, chlen / self.samp_freq - self.filter_time + self.step_time, self.step_time)
            timebin = np.vstack((t0, t0 + self.filter_time)).T
            n_seg = 3
            cmplx = np.empty((2, num_g, n_seg, len(t0)), dtype=np.cdouble)
            mask = self.gui.gage_h5_file_handler.mask_valid_data
            for shot in range(len(self.jkam_creation_time_array)):
                if shot < len(mask) and mask[shot]:
                    data = self.gui.gage_h5_file_handler.gage_files[shot]
                    for seg in range(n_seg):
                        ch1 = data['CH1'][f'CH1_frame{seg}'] * conv
                        ch3 = data['CH3'][f'CH3_frame{seg}'] * conv
                        for i, start in enumerate(t0):
                            i0 = int(round(start * self.samp_freq))
                            i1 = i0 + int(round(self.filter_time * self.samp_freq))
                            L = i1 - i0
                            if L <= 0:
                                cmplx[0, shot, seg, i] = np.nan
                                cmplx[1, shot, seg, i] = np.nan
                            else:
                                w = (signal.windows.flattop(L) if self.window == 'flattop'
                                     else 1 if self.window == 'square'
                                     else signal.windows.hann(L) * 2)
                                d1 = ch1[i0:i1] * w * pure1[i0:i1]
                                d3 = ch3[i0:i1] * w * pure3[i0:i1]
                                c1 = np.cumsum(d1); c3 = np.cumsum(d3)
                                cmplx[0, shot, seg, i] = (c1[-1] - c1[0]) / L
                                cmplx[1, shot, seg, i] = (c3[-1] - c3[0]) / L
                else:
                    if shot < num_g:
                        cmplx[:, shot, :, :] = np.nan

            pickle.dump(cmplx, open(f'fft_cmplx_{self.filter_time}_{self.step_time}.pkl','wb'))
            pickle.dump(timebin, open(f'fft_timebin_{self.filter_time}_{self.step_time}.pkl','wb'))

            fig = self.gui.figures[4]; fig.clear()
            ax = fig.add_subplot(111)
            valid = [i for i in range(num_g) if i < len(mask) and mask[i]]
            if valid:
                last = valid[-1]
                mag = np.abs(cmplx[0, last, 0, :])
                ax.plot(mag, label=f"Shot {last}, CH1 seg0")
                ax.legend()
            else:
                ax.text(0.5,0.5,"No valid GageScope shots",ha='center',va='center',transform=ax.transAxes)
            ax.set_title("FFT Magnitude (Segment 0)")
            self.gui.canvases[4].draw()
        except Exception as e:
            print("Exception in update_fft_plot:", e)
            traceback.print_exc()

# -------------------- FPGA / Bin Handler --------------------
class BinFileHandler:
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
        self.PT_cavity_timestamp_array_raw = []
        self.fpga_error_shots_reported = set()

    def update_fpga_graph(self, filename):
        unit_time_PT = 1/700
        raw_data = np.fromfile(filename, dtype=np.uint8)
        bits = np.unpackbits(raw_data).reshape(-1,32)
        tparts = np.concatenate((np.flip(2**np.arange(8)),
                                 np.flip(2**np.arange(8,16)),
                                 np.flip(2**np.arange(16,24)),
                                 [16777216]))
        timestamps = unit_time_PT * np.sort(bits[:,:25].dot(tparts))
        self.PT_cavity_timestamp_array_raw.append(timestamps)
        fig = self.gui.figures[9]; fig.clear()
        ax = fig.add_subplot(111)
        if timestamps.size == 0:
            ax.text(0.5,0.5,"No FPGA timestamps",ha='center',va='center',transform=ax.transAxes)
        else:
            ax.plot(timestamps, np.arange(len(timestamps)), ls='-', marker='o')
        ax.set_title("FPGA Photon Input Times")
        ax.set_xlabel("Time (µs)"); ax.set_ylabel("Photons In Count")
        self.gui.canvases[9].draw()

    def process_file(self, file):
        self.gui.jkam_h5_file_handler.update_settings()
        if file in self.bin_files:
            return
        try:
            file_ctime = os.path.getctime(file)
        except:
            return
        self.bin_files.append(file)
        self.fpga_creation_time_array.append(file_ctime)
        if len(self.fpga_creation_time_array) == 1:
            self.start_time = file_ctime
        self.rerun_acceptance()
        idx = len(self.fpga_creation_time_array) - 1
        valid = idx < len(self.mask_valid_data) and self.mask_valid_data[idx]
        jkam_str = str(self.gui.jkam_h5_file_handler.shots_dict.get(idx, "None"))
        row = self.gui.additional_table_1.rowCount()
        self.gui.additional_table_1.insertRow(row)
        for col, val in enumerate([idx, file, valid, jkam_str]):
            self.gui.additional_table_1.setItem(row, col, QTableWidgetItem(str(val)))
        summary = (f"<b>Start Time:</b> {self.start_time}, "
                   f"<b>Current Time:</b> {file_ctime}, "
                   f"<b>Avg Time Gap:</b> {self.avg_time_gap:.3f}")
        self.gui.additional_table_1.setItem(row, 4, QTableWidgetItem(summary))
        self.update_fpga_graph(file)
        self.update_chart_2()

    def rerun_acceptance(self):
        n = len(self.fpga_creation_time_array)
        if len(self.final_accepted) < n:
            self.final_accepted += [False] * (n - len(self.final_accepted))
        if n <= 1:
            self.avg_time_gap = 0
        else:
            span = abs(self.fpga_creation_time_array[-1] - self.fpga_creation_time_array[0])
            self.avg_time_gap = span / (n - 1)
        self.mask_valid_data = np.zeros(n, dtype=bool)
        self.jkam_fpga_matchlist = np.full(n, -1, dtype=int)
        self.color_array = ["r"] * n
        jt = self.gui.jkam_h5_file_handler.time_temp_dict
        js = self.gui.jkam_h5_file_handler.shots_dict
        ft = np.array(self.fpga_creation_time_array)
        for i in range(n):
            if self.final_accepted[i]:
                self.mask_valid_data[i] = True
                self.color_array[i] = "g"
                continue
            if i in jt and i in js and js[i]:
                if self.avg_time_gap == 0:
                    self.mask_valid_data[i] = True
                    self.color_array[i] = "g"
                    self.jkam_fpga_matchlist[i] = i
                    self.final_accepted[i] = True
                else:
                    diffs = np.abs(ft - jt[i])
                    md = np.min(diffs)
                    if md <= 0.3 * self.avg_time_gap:
                        self.mask_valid_data[i] = True
                        self.jkam_fpga_matchlist[i] = int(np.argmin(diffs))
                        self.color_array[i] = "g"
                        self.final_accepted[i] = True
                    elif i not in self.fpga_error_shots_reported:
                        print(f"FPGA error at shot {i}")
                        self.fpga_error_shots_reported.add(i)
            else:
                self.mask_valid_data[i] = False
                self.jkam_fpga_matchlist[i] = -1
        self.cumulative_data = []
        curr = 0
        for ok in self.mask_valid_data:
            if ok:
                curr = (self.highest_count + 1) if not self.cumulative_data or self.cumulative_data[-1] == 0 else curr + 1
                self.highest_count = max(self.highest_count, curr)
                self.cumulative_data.append(curr)
            else:
                self.cumulative_data.append(0)

    def update_chart_2(self):
        fig = self.gui.figures[1]; fig.clear()
        ax = fig.add_subplot(111)
        x = np.arange(len(self.cumulative_data))
        for i, v in enumerate(self.cumulative_data):
            ax.plot(x[i], v, marker='o', color=self.color_array[i])
        ax.plot(x, self.cumulative_data, linestyle='-', alpha=0.3)
        ax.set_title("Cumulative Accepted Files 2 (Bin/FPGA)")
        ax.set_xlabel("Shot Number"); ax.set_ylabel("Cumulative Value")
        self.gui.canvases[1].draw()

# -------------------- GageScope Handler --------------------
class GageScopeH5FileHandler:
    def __init__(self, gui):
        self.gui = gui
        self.gage_files = []
        self.gage_creation_time_array = []
        self.mask_valid_data = []
        self.jkam_gage_matchlist = []
        self.color_array = []
        self.cumulative_data = []
        self.final_accepted = []
        self.start_time = None
        self.avg_time_gap = 0
        self.gage_error_shots_reported = set()

    def process_file(self, file):
        print(f"\n=== GageScope processing start: {file} ===")
        if not os.path.isfile(file):
            print(f"File not found: {file}")
            return
        try:
            ok = h5py.is_hdf5(file)
        except Exception as e:
            print(f"HDF5 check error: {e}")
            return
        print(f"is_hdf5: {ok}")
        if not ok:
            print(f"Not HDF5: {file}")
            return
        ctime = os.path.getctime(file)
        if ctime in self.gage_creation_time_array:
            print(f"Duplicate ctime {ctime}")
            return
        try:
            with h5py.File(file,'r') as h5f:
                keys = list(h5f.keys())
                print(f"Datasets: {keys}")
                exp = [f'CH1_frame{i}' for i in range(3)] + [f'CH3_frame{i}' for i in range(3)]
                miss = [ds for ds in exp if ds not in keys]
                if miss:
                    print(f"Missing: {miss}")
                    return
                ch1 = {}; ch3 = {}
                for ds in exp:
                    arr = np.array(h5f[ds])
                    if ds.startswith('CH1_'):
                        ch1[ds] = arr
                    else:
                        ch3[ds] = arr
        except Exception as e:
            print(f"GageScope read error: {e}")
            traceback.print_exc()
            return
        self.gage_files.append({'CH1': ch1, 'CH3': ch3})
        self.gage_creation_time_array.append(ctime)
        print(f"Registered GageScope at {ctime}")
        if len(self.gage_creation_time_array) == 1:
            self.start_time = ctime
        self.gui.jkam_h5_file_handler.update_settings()
        self.rerun_acceptance_gage()
        idx = len(self.gage_creation_time_array) - 1
        valid = idx < len(self.mask_valid_data) and self.mask_valid_data[idx]
        jstr = str(self.gui.jkam_h5_file_handler.shots_dict.get(idx, "None"))
        row = self.gui.additional_table_2.rowCount()
        self.gui.additional_table_2.insertRow(row)
        for col, val in enumerate([idx, file, valid, jstr]):
            self.gui.additional_table_2.setItem(row, col, QTableWidgetItem(str(val)))
        summ = (f"<b>Start Time:</b> {self.start_time}, "
                f"<b>Current Time:</b> {ctime}, "
                f"<b>Avg Time Gap:</b> {self.avg_time_gap:.3f}")
        self.gui.additional_table_2.setItem(row, 4, QTableWidgetItem(summ))
        try:
            self.update_chart_3()
            print("update_chart_3 OK")
        except Exception as e:
            print("Chart3 error:", e)
            traceback.print_exc()
        try:
            self.gui.jkam_h5_file_handler.update_fft_plot()
            print("FFT OK")
        except Exception as e:
            print("FFT error:", e)
            traceback.print_exc()

    def rerun_acceptance_gage(self):
        n = len(self.gage_creation_time_array)
        if len(self.final_accepted) < n:
            self.final_accepted += [False] * (n - len(self.final_accepted))
        self.avg_time_gap = 0 if n <= 1 else (self.gage_creation_time_array[-1] - self.gage_creation_time_array[0]) / (n - 1)
        self.mask_valid_data = np.zeros(n, dtype=bool)
        self.jkam_gage_matchlist = np.full(n, -1, dtype=int)
        self.color_array = ["r"] * n
        sd = self.gui.jkam_h5_file_handler.shots_dict
        td = self.gui.jkam_h5_file_handler.time_temp_dict
        times = np.array(self.gage_creation_time_array)
        for i in range(n):
            if self.final_accepted[i]:
                self.mask_valid_data[i] = True
                self.color_array[i] = "g"
                continue
            if i in sd and i in td and sd[i]:
                if self.avg_time_gap == 0 or np.min(np.abs(times - td[i])) <= 0.3 * self.avg_time_gap:
                    self.mask_valid_data[i] = True
                    self.jkam_gage_matchlist[i] = i if self.avg_time_gap == 0 else int(np.argmin(np.abs(times - td[i])))
                    self.color_array[i] = "g"
                    self.final_accepted[i] = True
                elif i not in self.gage_error_shots_reported:
                    print(f"Gage error at shot {i}")
                    self.gage_error_shots_reported.add(i)
        self.cumulative_data, last, high = [], 0, 0
        for ok in self.mask_valid_data:
            if ok:
                last = (high + 1) if not self.cumulative_data or self.cumulative_data[-1] == 0 else last + 1
                high = max(high, last)
                self.cumulative_data.append(last)
            else:
                self.cumulative_data.append(0)

    def update_chart_3(self):
        fig = self.gui.figures[3]; fig.clear()
        ax = fig.add_subplot(111)
        x = np.arange(len(self.cumulative_data))
        for i, v in enumerate(self.cumulative_data):
            ax.plot(x[i], v, marker='o', color=self.color_array[i])
        ax.plot(x, self.cumulative_data, linestyle='-', alpha=0.3)
        ax.set_title("Cumulative Accepted Files 3 (GageScope)")
        ax.set_xlabel("Shot Number"); ax.set_ylabel("Cumulative Value")
        self.gui.canvases[3].draw()

# -------------------- Red Pitaya Handler --------------------
class RedPitayaFileHandler:
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
        self.done1 = self.done2 = self.done3 = self.done4 = 0

    def download_redpitaya_files(self):
        host, username, password = "169.254.13.29", "root", "root"
        remote = "/root/RedPitaya/"
        files = ["phicav.txt","phiperp.txt","cnstperp.txt",
                 "histcav.txt","histperp.txt","lencav.txt",
                 "lenperp.txt","outcav.txt","outperp.txt"]
        local = self.gui.rp_download_dir_edit.text().strip()
        if not local:
            print("No RP download dir."); return
        os.makedirs(local, exist_ok=True)
        try:
            client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, username=username, password=password)
            sftp = client.open_sftp()
            for fn in files:
                sftp.get(os.path.join(remote, fn), os.path.join(local, fn))
            sftp.close(); client.close()
        except Exception as e:
            print(f"RP download error: {e}")

    def load_data(self, file):
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
            print(f"No such RP file: {file}")
            return
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", UserWarning)
                data = np.loadtxt(file, delimiter=',')
        except Exception as e:
            print(f"Error loading RP file {file}: {e}")
            self.rp_files.append(file); self.rp_times_list.append(None)
            self.rerun_acceptance_rp(); return
        if data.size == 0:
            print(f"Empty RP file: {file}")
            self.rp_files.append(file); self.rp_times_list.append(None)
            self.rerun_acceptance_rp(); return
        if data.ndim == 1:
            data = data.reshape(1, -1)
        times = data[:, 0]
        self.rp_files.append(file); self.rp_times_list.append(times)
        self.rerun_acceptance_rp()
        idx = len(self.rp_files) - 1
        valid = idx < len(self.mask_valid_data_rp) and self.mask_valid_data_rp[idx]
        jstr = str(self.gui.jkam_h5_file_handler.shots_dict.get(idx, "None"))
        row = self.gui.additional_table_3.rowCount()
        self.gui.additional_table_3.insertRow(row)
        for col, val in enumerate([idx, file, valid, jstr]):
            self.gui.additional_table_3.setItem(row, col, QTableWidgetItem(str(val)))
        info = ("No Data" if times is None or len(times) == 0 else f"RP Times Count: {len(times)}")
        self.gui.additional_table_3.setItem(row, 4, QTableWidgetItem(info))
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
        n = len(self.rp_files)
        if len(self.final_accepted) < n:
            self.final_accepted += [False] * (n - len(self.final_accepted))
        self.mask_valid_data_rp = [False] * n
        self.jkam_rp_matchlist = [-1] * n
        self.color_array = ["r"] * n
        self.cumulative_data = []
        high = last = 0
        sd = self.gui.jkam_h5_file_handler.shots_dict
        td = self.gui.jkam_h5_file_handler.time_temp_dict
        avg_gap = self.gui.jkam_h5_file_handler.avg_time_gap
        for i in range(n):
            if self.final_accepted[i]:
                self.mask_valid_data_rp[i] = True
                self.color_array[i] = "g"
                last = high + 1 if not self.cumulative_data or self.cumulative_data[-1] == 0 else last + 1
                high = max(high, last)
                self.cumulative_data.append(last)
                continue
            times = self.rp_times_list[i]
            if times is None or len(times) == 0:
                self.cumulative_data.append(0)
                continue
            if i not in sd or i not in td or not sd[i]:
                self.cumulative_data.append(0)
                continue
            md = np.min(np.abs(times - td[i]))
            if avg_gap != 0 and md <= 0.3 * avg_gap:
                self.mask_valid_data_rp[i] = True
                self.jkam_rp_matchlist[i] = int(np.argmin(np.abs(times - td[i])))
                self.color_array[i] = "g"
                self.final_accepted[i] = True
                last = high + 1 if not self.cumulative_data or self.cumulative_data[-1] == 0 else last + 1
                high = max(high, last)
                self.cumulative_data.append(last)
            else:
                print(f"RP error at shot {i}")
                self.cumulative_data.append(0)

    def update_chart_rp(self):
        fig = self.gui.figures[2]; fig.clear()
        ax = fig.add_subplot(111)
        x = np.arange(len(self.cumulative_data))
        for i, v in enumerate(self.cumulative_data):
            ax.plot(x[i], v, marker='o', color=self.color_array[i])
        ax.plot(x, self.cumulative_data, linestyle='-', alpha=0.3)
        ax.set_title("Cumulative Accepted Files (Red Pitaya)")
        ax.set_xlabel("Shot Number"); ax.set_ylabel("Cumulative Value")
        self.gui.canvases[2].draw()

    def update_unique_rp(self):
        if self.done1 == 0 and self.cav_len is not None and self.perp_len is not None:
            if self.cav_len.ndim == 2 and self.perp_len.ndim == 2:
                self.done1 = 1
                fig = self.gui.figures[5]; fig.clear()
                ax = fig.add_subplot(111)
                ax.plot(self.cav_len[:,0], self.cav_len[:,1], label="cav_len")
                ax.plot(self.perp_len[:,0], self.perp_len[:,1], label="perp_len")
                ax.legend()
                self.gui.canvases[5].draw()
        if self.done2 == 0 and self.cav_contrast is not None and self.perp_contrast is not None:
            if self.cav_contrast.ndim == 2 and self.perp_contrast.ndim == 2:
                self.done2 = 1
                fig = self.gui.figures[6]; fig.clear()
                ax = fig.add_subplot(111)
                ax.plot(self.cav_contrast[:,0], self.cav_contrast[:,1], label="cav_contrast")
                ax.plot(self.perp_contrast[:,0], self.perp_contrast[:,1], label="perp_contrast")
                ax.legend()
                self.gui.canvases[6].draw()
        if self.done3 == 0 and self.cav_output is not None and self.perp_output is not None:
            if self.cav_output.ndim == 2 and self.perp_output.ndim == 2:
                self.done3 = 1
                fig = self.gui.figures[7]; fig.clear()
                ax = fig.add_subplot(111)
                ax.plot(self.cav_output[:,0], self.cav_output[:,1], label="cav_output")
                ax.plot(self.perp_output[:,0], self.perp_output[:,1], label="perp_output")
                ax.set_ylim(-1.2, 1.2)
                ax.legend()
                self.gui.canvases[7].draw()
        if self.done4 == 0 and self.cav_phase is not None and self.perp_phase is not None:
            if self.cav_phase.ndim == 2 and self.perp_phase.ndim == 2:
                self.done4 = 1
                fig = self.gui.figures[8]; fig.clear()
                ax = fig.add_subplot(111)
                ax.plot(self.cav_phase[:,0], self.cav_phase[:,1], label="cav_phase")
                ax.plot(self.perp_phase[:,0], self.perp_phase[:,1], label="perp_phase")
                ax.axhline(0.11, c='k'); ax.axhline(-0.11, c='k')
                ax.axvline(self.cav_phase[0,0], c='k')
                ax.legend()
                self.gui.canvases[8].draw()

# -------------------- Main GUI --------------------
class FileProcessorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('File Processor GUI + Atom Analysis')
        self.setGeometry(100, 100, 1700, 930)
        self.inputs_accepted = False

        # Handlers
        self.jkam_h5_file_handler  = JkamH5FileHandler(self)
        self.gage_h5_file_handler  = GageScopeH5FileHandler(self)
        self.bin_handler           = BinFileHandler(self)
        self.redpitaya_handler     = RedPitayaFileHandler(self)
        self.atom_analysis_handler = AtomAnalysisHandler(self)

        # Central widget & layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_hlayout = QHBoxLayout(self.central_widget)

        # Left Dock
        self.leftDock = QDockWidget("Feature Options", self)
        self.leftDock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.leftDock)
        self._init_feature_options()

        # Right side
        self.right_side_widget = QWidget()
        self.right_side_layout = QVBoxLayout(self.right_side_widget)
        self.main_hlayout.addWidget(self.right_side_widget)
        self.threadpool = QThreadPool()

        # Tabs
        self.tabs = QTabWidget()
        self.right_side_layout.addWidget(self.tabs)
        self._init_tabs()
        self._init_stream_controls()

    def _init_feature_options(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.time_me_checkbox = QCheckBox("time_me")
        self.plot_tenth_shot_checkbox = QCheckBox("plot_tenth_shot")
        self.time_me_checkbox.setChecked(True)
        self.plot_tenth_shot_checkbox.setChecked(True)
        layout.addWidget(self.time_me_checkbox)
        layout.addWidget(self.plot_tenth_shot_checkbox)

        def fld(lbl, default):
            l = QLabel(lbl)
            i = QLineEdit(str(default))
            layout.addWidget(l)
            layout.addWidget(i)
            return i

        self.het_freq_input = fld("het_freq (MHz):", 20.000446)
        self.dds_freq_input = fld("dds_freq:", 10.000223)
        self.samp_freq_input = fld("samp_freq (MHz):", 200)
        self.averaging_time_input = fld("averaging_time (us):", 0)
        self.step_time_input = fld("step_time (us):", 1)
        self.filter_time_input = fld("filter_time (us):", 5)
        self.voltage_conversion_input = fld("voltage_conversion (mV):", 0.0305176)
        self.kappa_input = fld("kappa (MHz):", 6.9115)
        self.LO_power_input = fld("LO_power (uW):", 314)
        self.PHOTON_ENERGY_input = fld("PHOTON_ENERGY:", 2.55e-19)
        self.LO_rate_input = fld("LO_rate (count/us):", 1.23e9)
        self.photonrate_conversion_input = fld("photonrate_conversion (count/us):", 9450)

        layout.addWidget(QLabel("Window function:"))
        self.window_select = QComboBox()
        self.window_select.addItems(["hann", "flattop", "square"])
        layout.addWidget(self.window_select)

        layout.addWidget(QLabel("Red Pitaya Download Folder:"))
        self.rp_download_dir_edit = QLineEdit(os.path.join(os.getcwd(), "rp-automatic"))
        layout.addWidget(self.rp_download_dir_edit)

        self.accept_button = QPushButton("Accept Inputs")
        self.accept_button.clicked.connect(self.accept_inputs)
        layout.addWidget(self.accept_button)

        self.inputs_status_label = QLabel("PLEASE ENTER INPUTS and click 'Accept Inputs'")
        layout.addWidget(self.inputs_status_label)
        layout.addStretch()
        w.setLayout(layout)
        self.leftDock.setWidget(w)

    def _init_tabs(self):
        # Chart tab
        self.chart_tab = QWidget()
        self.chart_layout = QGridLayout(self.chart_tab)
        self.tabs.addTab(self.chart_tab, "Accept Charts")

        # JKAM table tab
        self.table_tab = QWidget()
        self.table_layout = QVBoxLayout(self.table_tab)
        self.tabs.addTab(self.table_tab, "JKAM Data")

        # FPGA table tab
        self.fpga_table_tab = QWidget()
        self.fpga_table_layout = QVBoxLayout(self.fpga_table_tab)
        self.tabs.addTab(self.fpga_table_tab, "FPGA Data")

        # GageScope table tab
        self.gage_table_tab = QWidget()
        self.gage_table_layout = QVBoxLayout(self.gage_table_tab)
        self.tabs.addTab(self.gage_table_tab, "GageScope Data")

        # Red Pitaya table tab
        self.rp_table_tab = QWidget()
        self.rp_table_layout = QVBoxLayout(self.rp_table_tab)
        self.tabs.addTab(self.rp_table_tab, "Red Pitaya Data")

        # FFT Graph tab
        self.fft_tab = QWidget()
        self.fft_layout = QVBoxLayout(self.fft_tab)
        self.tabs.addTab(self.fft_tab, "FFT Graph")

        # Red Pitaya Graphs tab
        self.rp_graph_tab = QWidget()
        self.rp_graph_layout = QGridLayout(self.rp_graph_tab)
        self.tabs.addTab(self.rp_graph_tab, "Red Pitaya Graphs")

        # FPGA Graphs tab
        self.fpga_graph_tab = QWidget()
        self.fpga_graph_layout = QVBoxLayout(self.fpga_graph_tab)
        self.tabs.addTab(self.fpga_graph_tab, "FPGA Graphs")

        # Atom Analysis tab
        self.atom_tab = QWidget()
        self.atom_layout = QVBoxLayout(self.atom_tab)
        self.tabs.addTab(self.atom_tab, "Atom Analysis")

        # Trap Status tb
        self.trap_tab = QWidget()
        self.trap_layout = QVBoxLayout(self.trap_tab)
        self.trap_table = QTableWidget()
        self.trap_table.setColumnCount(2)
        self.trap_table.verticalHeader().setVisible(False)
        self.trap_table.setHorizontalHeaderLabels(["Trap Number", "Loaded"])
        self.trap_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.trap_table.horizontalHeader().setStretchLastSection(True)
        self.trap_layout.addWidget(self.trap_table)
        self.tabs.addTab(self.trap_tab, "Trap Status")

        # JKAM table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Shot Number", "File Name", "Accepted", "Summary Statistics"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table_layout.addWidget(self.table)
        btn_table = QPushButton("Add Files")
        btn_table.clicked.connect(self.add_files)
        self.table_layout.addWidget(btn_table)

        # FPGA table
        self.additional_table_1 = QTableWidget()
        self.additional_table_1.setColumnCount(5)
        self.additional_table_1.setHorizontalHeaderLabels(
            ["Shot Number", "File Name", "Accepted", "JKAM Space Correct", "Summary Statistics"]
        )
        self.additional_table_1.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.additional_table_1.horizontalHeader().setStretchLastSection(True)
        self.fpga_table_layout.addWidget(self.additional_table_1)

        # GageScope table
        self.additional_table_2 = QTableWidget()
        self.additional_table_2.setColumnCount(5)
        self.additional_table_2.setHorizontalHeaderLabels(
            ["Shot Number", "File Name", "Accepted", "JKAM Space Correct", "Summary Statistics"]
        )
        self.additional_table_2.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.additional_table_2.horizontalHeader().setStretchLastSection(True)
        self.gage_table_layout.addWidget(self.additional_table_2)

        # Red Pitaya table
        self.additional_table_3 = QTableWidget()
        self.additional_table_3.setColumnCount(5)
        self.additional_table_3.setHorizontalHeaderLabels(
            ["Shot Number", "File Name", "Accepted", "JKAM Space Correct", "Summary Statistics"]
        )
        self.additional_table_3.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.additional_table_3.horizontalHeader().setStretchLastSection(True)
        self.rp_table_layout.addWidget(self.additional_table_3)

        # Figures & canvases
        self.figures = [Figure() for _ in range(11)]
        self.canvases = [FigureCanvas(f) for f in self.figures]

        # Place charts
        self.chart_layout.addWidget(self.canvases[0], 0, 0)
        self.chart_layout.addWidget(self.canvases[1], 0, 1)
        self.chart_layout.addWidget(self.canvases[2], 1, 0)
        self.chart_layout.addWidget(self.canvases[3], 1, 1)
        btn_charts = QPushButton("Add Files")
        btn_charts.clicked.connect(self.add_files)
        self.chart_layout.addWidget(btn_charts, 2, 0, 1, 2)

        # FFT
        self.fft_layout.addWidget(self.canvases[4])

        # RP graphs
        self.rp_graph_layout.addWidget(self.canvases[5], 0, 0)
        self.rp_graph_layout.addWidget(self.canvases[6], 0, 1)
        self.rp_graph_layout.addWidget(self.canvases[7], 1, 0)
        self.rp_graph_layout.addWidget(self.canvases[8], 1, 1)

        # FPGA graph
        self.fpga_graph_layout.addWidget(self.canvases[9])

        # Atom analysis
        self.atom_layout.addWidget(self.canvases[10])
        ax_atom = self.figures[10].add_subplot(111)
        ax_atom.set_title('Per-Tweezer Metrics (Rolling)')
        ax_atom.set_xlabel('Tweezer Freq (MHz)')
        ax_atom.set_ylabel('Probability / Brightness×1e3')
        self.canvases[10].draw()

    def _init_stream_controls(self):
        self.stream_controls_layout = QHBoxLayout()
        self.stream_dir_label = QLabel("Stream Directory:")
        self.stream_dir_edit = QLineEdit(os.getcwd())
        self.stream_start_button = QPushButton("Start Stream")
        self.stream_stop_button = QPushButton("Stop Stream")
        self.stream_status_label = QLabel("Not streaming")
        for w in [self.stream_dir_label, self.stream_dir_edit,
                  self.stream_start_button, self.stream_stop_button,
                  self.stream_status_label]:
            self.stream_controls_layout.addWidget(w)
        self.right_side_layout.addLayout(self.stream_controls_layout)
        self.stream_timer = QTimer()
        self.stream_timer.setInterval(2000)
        self.stream_timer.timeout.connect(self.check_for_new_files)
        self.stream_start_button.clicked.connect(self.start_stream)
        self.stream_stop_button.clicked.connect(self.stop_stream)
        self.stream_processed_files = set()

    def update_trap_table(self, loaded_array):
        n = len(loaded_array)
        self.trap_table.setRowCount(n)
        for i in range(n):
            self.trap_table.setItem(i, 0, QTableWidgetItem(str(i)))
            self.trap_table.setItem(i, 1, QTableWidgetItem("1" if loaded_array[i] else "0"))

    def accept_inputs(self):
        fields = [
            self.het_freq_input, self.dds_freq_input, self.samp_freq_input,
            self.averaging_time_input, self.step_time_input, self.filter_time_input,
            self.voltage_conversion_input, self.kappa_input, self.LO_power_input,
            self.PHOTON_ENERGY_input, self.LO_rate_input, self.photonrate_conversion_input
        ]
        for f in fields:
            if f.text().strip() == "":
                print("Please fill all inputs before accepting.")
                self.inputs_accepted = False
                return
        self.inputs_accepted = True
        self.inputs_status_label.setText("Inputs accepted! You may now add/stream files.")
        print("Inputs accepted!")

    def add_files(self):
        if not self.inputs_accepted:
            print("Please fill in all inputs and click 'Accept Inputs' first.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*.*)")
        for f in files:
            self._process_one_file(f)

    def _process_one_file(self, file):
        self.jkam_h5_file_handler.update_settings()
        ext = os.path.splitext(file)[-1].lower()
        name = os.path.basename(file).lower()
        if ext == '.h5' and 'jkam' in name:
            self.jkam_h5_file_handler.process_file(file)
        elif ext == '.h5' and 'gage' in name:
            self.gage_h5_file_handler.process_file(file)
        elif ext == '.bin':
            self.bin_handler.process_file(file)
        elif ext == '.txt':
            self.redpitaya_handler.process_file(file)
        else:
            print(f"Unsupported file: {file}")

    def start_stream(self):
        if not self.inputs_accepted:
            print("Please fill in all inputs before starting stream.")
            return
        self.stream_processed_files.clear()
        self.stream_timer.start()
        self.stream_status_label.setText("Streaming has started!")
        print("Stream started:", self.stream_dir_edit.text())

    def stop_stream(self):
        self.stream_timer.stop()
        self.stream_status_label.setText("Not streaming")
        print("Stream stopped.")

    def check_for_new_files(self):
        if not self.inputs_accepted:
            return
        d = self.stream_dir_edit.text()
        if not os.path.isdir(d):
            print(f"Invalid stream dir: {d}")
            return
        for sub in sorted(os.listdir(d)):
            sp = os.path.join(d, sub)
            if not os.path.isdir(sp):
                continue
            for fn in sorted(os.listdir(sp)):
                fp = os.path.join(sp, fn)
                if fp not in self.stream_processed_files:
                    self._process_one_file(fp)
                    self.stream_processed_files.add(fp)

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def cleanup(self):
        self.jkam_h5_file_handler.jkam_files.clear()
        self.gage_h5_file_handler.gage_files.clear()
        self.bin_handler.bin_files.clear()
        self.redpitaya_handler.rp_files.clear()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileProcessorGUI()
    window.show()
    sys.exit(app.exec_())
