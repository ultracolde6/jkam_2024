from package.widgets.imagevieweditor import ImageViewEditor
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal
import numpy as np


class Multishot1013LSViewWidget(QtWidgets.QWidget):
    """
    Widget that displays multishot frames with special "1013 LS" view.
    This view is designed for 5-frame multishot and shows frame 3 minus frame 2.
    """
    analysis_complete_signal = pyqtSignal()
    first_frame_complete_signal = pyqtSignal()
    second_frame_complete_signal = pyqtSignal()
    third_frame_complete_signal = pyqtSignal()

    def __init__(self, parent=None):
        super(Multishot1013LSViewWidget, self).__init__(parent=parent)
        self.setupUi()
        
        self.tab_list = []
        self.editor_list = []
        self.frame_dict_list = []
        self.n_frames = 0
        self.curr_frame = 0

    def link_views(self, shared_view_index=0):
        """Link all views to share zoom and pan."""
        if not self.editor_list:
            return
            
        shared_editor_view = self.editor_list[shared_view_index].imageview.getView()
        for editor in self.editor_list:
            image_view = editor.imageview.getView()
            image_view.setXLink(shared_editor_view)
            image_view.setYLink(shared_editor_view)
            editor.camview.crosshair_moved_signal.connect(self.share_crosshair)

    def share_crosshair(self, evt):
        """Share crosshair position across all views."""
        for editor in self.editor_list:
            editor.camview.mouse_moved(evt, signal=False)

    def reset(self):
        """Reset the frame counter."""
        self.curr_frame = 0

    def process_frame(self, frame_dict):
        """Process a new frame and display it in the appropriate editor."""
        self.frame_dict_list[self.curr_frame] = frame_dict
        
        # Map incoming frames to the correct tabs
        if self.curr_frame == 0:  # Frame 0 -> Tab 0
            self.editor_list[0].setImage(frame_dict['frame'], autoRange=False, autoLevels=False,
                                       autoHistogramRange=False)
        elif self.curr_frame == 1:  # Frame 1 -> Tab 1
            self.editor_list[1].setImage(frame_dict['frame'], autoRange=False, autoLevels=False,
                                       autoHistogramRange=False)
        elif self.curr_frame == 2:  # Frame 2 -> Skip (not displayed)
            pass
        elif self.curr_frame == 3:  # Frame 3 -> Calculate Frame 3-2 for Tab 2
            # Calculate frame 3 - frame 2
            if (self.frame_dict_list[2] is not None and 
                self.frame_dict_list[3] is not None):
                frame2 = self.frame_dict_list[2]['frame']
                frame3 = self.frame_dict_list[3]['frame']
                
                # Ensure both frames have the same shape
                if frame2.shape == frame3.shape:
                    # Calculate difference (frame 3 - frame 2)
                    diff_frame = frame3.astype(np.float32) - frame2.astype(np.float32)
                    
                    # Display the difference in the "Frame 3-2" tab
                    self.editor_list[2].setImage(diff_frame, autoRange=False, autoLevels=False,
                                               autoHistogramRange=False)
                else:
                    # Fallback to original frame 3 if shapes don't match
                    self.editor_list[2].setImage(frame3, autoRange=False, autoLevels=False,
                                               autoHistogramRange=False)
            else:
                # Fallback to original frame 3 if frame 2 is not available
                self.editor_list[2].setImage(frame_dict['frame'], autoRange=False, autoLevels=False,
                                           autoHistogramRange=False)
        elif self.curr_frame == 4:  # Frame 4 -> Tab 3
            self.editor_list[3].setImage(frame_dict['frame'], autoRange=False, autoLevels=False,
                                       autoHistogramRange=False)
        
        self.curr_frame += 1
        
        # Emit signals for specific frame completions
        if self.curr_frame == 1:
            self.first_frame_complete_signal.emit()
        if self.curr_frame == 2:
            self.second_frame_complete_signal.emit()
        if self.curr_frame == 3:
            self.third_frame_complete_signal.emit()
        
        # Reset frame counter and emit analysis complete signal when all frames are processed
        if self.curr_frame == 5:  # All 5 frames processed
            self.curr_frame = 0
            self.analysis_complete_signal.emit()

    def setup_frames(self, num_frames):
        """Set up the specified number of frame editors with special 1013 LS layout."""
        if num_frames != 5:
            # This view is only designed for 5 frames
            return
            
        self.clear_tabs()
        # Initialize frame_dict_list for all 5 frames, even though we only display 4
        self.frame_dict_list = [None] * 5
        
        # Create only 4 tabs: Frame 0, Frame 1, Frame 3-2, Frame 4
        self.create_tab(0)  # Frame 0
        self.create_tab(1)  # Frame 1
        self.create_tab(2)  # Frame 3-2 (special)
        self.create_tab(3)  # Frame 4

    def create_tab(self, frame_index):
        """Create a new frame editor for the specified frame index."""
        self.n_frames += 1
        
        new_tab = QtWidgets.QWidget()
        self.tab_list.append(new_tab)
        gridLayout = QtWidgets.QGridLayout(new_tab)
        new_view_editor = ImageViewEditor(new_tab)
        gridLayout.addWidget(new_view_editor, 0, 0, 1, 1)
        self.editor_list.append(new_view_editor)
        # Don't append to frame_dict_list here since it's pre-initialized in setup_frames
        
        # Special labeling for 1013 LS view
        if frame_index == 2:  # 3rd tab (0-indexed) - Frame 3-2
            self.tabWidget.addTab(new_tab, 'Frame 3-2')
        elif frame_index == 0:  # 1st tab - Frame 0
            self.tabWidget.addTab(new_tab, 'Frame 0')
        elif frame_index == 1:  # 2nd tab - Frame 1
            self.tabWidget.addTab(new_tab, 'Frame 1')
        elif frame_index == 3:  # 4th tab - Frame 4
            self.tabWidget.addTab(new_tab, 'Frame 4')
        
        self.link_views()

    def clear_tabs(self):
        """Clear all frame editors."""
        self.tabWidget.clear()
        for tab in self.tab_list:
            tab.deleteLater()
        self.tab_list = []
        self.editor_list = []
        self.frame_dict_list = []  # Will be re-initialized in setup_frames
        self.n_frames = 0
        self.curr_frame = 0

    def setupUi(self):
        """Set up the UI with a tab widget for displaying frames."""
        self.gridLayout = QtWidgets.QGridLayout(self)
        self.gridLayout.setObjectName("gridLayout")
        self.tabWidget = QtWidgets.QTabWidget(self)
        self.tabWidget.setEnabled(True)
        self.gridLayout.addWidget(self.tabWidget, 0, 0, 1, 1)
        self.tabWidget.setCurrentIndex(0) 