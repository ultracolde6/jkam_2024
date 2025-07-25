from package.widgets.imagevieweditor import ImageViewEditor
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal


class MultishotVerticalViewWidget(QtWidgets.QWidget):
    """
    Widget that displays all multishot frames vertically in a single view.
    This provides an alternative to the tabbed view for seeing all frames at once.
    """
    analysis_complete_signal = pyqtSignal()
    first_frame_complete_signal = pyqtSignal()
    second_frame_complete_signal = pyqtSignal()
    third_frame_complete_signal = pyqtSignal()
    
    def __init__(self, parent=None):
        super(MultishotVerticalViewWidget, self).__init__(parent=parent)
        self.setupUi()
        
        self.editor_list = []
        self.frame_dict_list = []
        self.n_frames = 0
        self.curr_frame = 0

    def setupUi(self):
        """Set up the UI with a vertical scroll area for displaying frames."""
        self.gridLayout = QtWidgets.QGridLayout(self)
        self.gridLayout.setObjectName("gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)  # Remove margins for more space
        self.gridLayout.setSpacing(0)  # No spacing
        
        # Create scroll area for vertical layout
        self.scrollArea = QtWidgets.QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        
        # Create scroll area widget
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        
        # Create vertical layout for frames
        self.verticalLayout = QtWidgets.QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        self.verticalLayout.setSpacing(1)  # Minimal spacing between frames
        
        # Add spacer at the end to push frames to the top
        self.verticalSpacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(self.verticalSpacer)
        
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.gridLayout.addWidget(self.scrollArea, 0, 0, 1, 1)

    def setup_frames(self, num_frames):
        """Set up the specified number of frame editors."""
        self.clear_frames()
        for ind in range(num_frames):
            self.create_frame_editor(ind)

    def create_frame_editor(self, frame_index):
        """Create a new frame editor for the specified frame index."""
        self.n_frames += 1
        
        # Create frame container
        frame_container = QtWidgets.QWidget()
        frame_container.setObjectName(f"frame_container_{frame_index}")
        
        # Create frame layout
        frame_layout = QtWidgets.QVBoxLayout(frame_container)
        frame_layout.setObjectName(f"frame_layout_{frame_index}")
        frame_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for more space
        frame_layout.setSpacing(2)  # Minimal spacing between frames
        
        # Create image view editor (no label)
        new_view_editor = ImageViewEditor(frame_container)
        new_view_editor.setObjectName(f"frame_editor_{frame_index}")
        frame_layout.addWidget(new_view_editor)
        
        # Add frame container to vertical layout (before the spacer)
        self.verticalLayout.insertWidget(frame_index, frame_container)
        
        # Store references
        self.editor_list.append(new_view_editor)
        self.frame_dict_list.append(None)

    def clear_frames(self):
        """Clear all frame editors."""
        # Remove all widgets except the spacer
        while self.verticalLayout.count() > 1:
            item = self.verticalLayout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()
        
        self.editor_list = []
        self.frame_dict_list = []
        self.n_frames = 0
        self.curr_frame = 0

    def process_frame(self, frame_dict):
        """Process a new frame and display it in the appropriate editor."""
        self.frame_dict_list[self.curr_frame] = frame_dict
        self.editor_list[self.curr_frame].setImage(frame_dict['frame'], autoRange=False, autoLevels=False,
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
        if self.curr_frame == self.n_frames:
            self.curr_frame = 0
            self.analysis_complete_signal.emit()

    def reset(self):
        """Reset the frame counter."""
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