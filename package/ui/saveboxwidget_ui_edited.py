# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_resources\saveboxwidget.ui'
#
# Created by: PyQt5 UI code generator 5.15.0
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_SaveBoxWidget(object):
    def setupUi(self, SaveBoxWidget):
        SaveBoxWidget.setObjectName("SaveBoxWidget")
        SaveBoxWidget.resize(235, 396)
        self.gridLayout = QtWidgets.QGridLayout(SaveBoxWidget)
        self.gridLayout.setObjectName("gridLayout")
        spacerItem = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem, 0, 2, 1, 1)
        self.frame = QtWidgets.QFrame(SaveBoxWidget)
        self.frame.setFrameShape(QtWidgets.QFrame.Box)
        self.frame.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.frame.setObjectName("frame")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.frame)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.data_dir_label = QtWidgets.QLabel(self.frame)
        font = QtGui.QFont()
        font.setPointSize(8)
        self.data_dir_label.setFont(font)
        self.data_dir_label.setText("")
        self.data_dir_label.setObjectName("data_dir_label")
        self.gridLayout_2.addWidget(self.data_dir_label, 1, 0, 1, 3)
        self.save_single_pushButton = QtWidgets.QPushButton(self.frame)
        self.save_single_pushButton.setObjectName("save_single_pushButton")
        self.gridLayout_2.addWidget(self.save_single_pushButton, 5, 0, 1, 3)
        self.file_number_spinBox = QtWidgets.QSpinBox(self.frame)
        self.file_number_spinBox.setMaximumSize(QtCore.QSize(127, 16777215))
        self.file_number_spinBox.setMinimum(0)
        self.file_number_spinBox.setMaximum(100000)
        self.file_number_spinBox.setProperty("value", 0)
        self.file_number_spinBox.setObjectName("file_number_spinBox")
        self.gridLayout_2.addWidget(self.file_number_spinBox, 3, 1, 1, 2)
        self.file_number_label = QtWidgets.QLabel(self.frame)
        self.file_number_label.setObjectName("file_number_label")
        self.gridLayout_2.addWidget(self.file_number_label, 3, 0, 1, 1)
        self.file_prefix_lineEdit = QtWidgets.QLineEdit(self.frame)
        self.file_prefix_lineEdit.setMaximumSize(QtCore.QSize(127, 16777215))
        self.file_prefix_lineEdit.setObjectName("file_prefix_lineEdit")
        self.gridLayout_2.addWidget(self.file_prefix_lineEdit, 2, 1, 1, 2)
        self.tabWidget = QtWidgets.QTabWidget(self.frame)
        self.tabWidget.setObjectName("tabWidget")
        self.build_dir_tab = QtWidgets.QWidget()
        self.build_dir_tab.setObjectName("build_dir_tab")
        self.gridLayout_4 = QtWidgets.QGridLayout(self.build_dir_tab)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.daily_path_label = QtWidgets.QLabel(self.build_dir_tab)
        self.daily_path_label.setObjectName("daily_path_label")
        # self.daily_path_1_label = QtWidgets.QLabel(self.build_dir_tab)
        # self.daily_path_1_label.setObjectName("daily_path_1_label")
        self.gridLayout_4.addWidget(self.daily_path_label, 2, 0, 1, 1)
        # self.gridLayout_4.addWidget(self.daily_path_1_label, 2, 0, 1, 1)
        self.run_name_lineEdit = QtWidgets.QLineEdit(self.build_dir_tab)
        self.run_name_lineEdit.setMaximumSize(QtCore.QSize(70, 16777215))
        self.run_name_lineEdit.setObjectName("run_name_lineEdit")
        self.gridLayout_4.addWidget(self.run_name_lineEdit, 3, 1, 1, 1)
        self.data_root_value_label = QtWidgets.QLabel(self.build_dir_tab)
        self.data_root_value_label.setText("")
        self.data_root_value_label.setObjectName("data_root_value_label")
        self.gridLayout_4.addWidget(self.data_root_value_label, 0, 0, 1, 1)
        self.data_root_1_value_label = QtWidgets.QLabel(self.build_dir_tab)
        self.data_root_1_value_label.setText("")
        self.data_root_1_value_label.setObjectName("data_root_1_value_label")
        self.data_root_2_value_label = QtWidgets.QLabel(self.build_dir_tab)
        self.data_root_2_value_label.setText("")
        self.data_root_2_value_label.setObjectName("data_root_2_value_label")
        self.data_root_3_value_label = QtWidgets.QLabel(self.build_dir_tab)
        self.data_root_3_value_label.setText("")
        self.data_root_3_value_label.setObjectName("data_root_3_value_label")
        self.gridLayout_4.addWidget(self.data_root_1_value_label, 1, 0, 1, 1)
        self.run_name_label = QtWidgets.QLabel(self.build_dir_tab)
        self.run_name_label.setObjectName("run_name_label")
        self.gridLayout_4.addWidget(self.run_name_label, 3, 0, 1, 1)
        self.data_root_label = QtWidgets.QLabel(self.build_dir_tab)
        self.data_root_label.setObjectName("data_root_label")
        self.gridLayout_4.addWidget(self.data_root_label, 2, 0, 1, 1)
        self.data_root_1_label = QtWidgets.QLabel(self.build_dir_tab)
        self.data_root_1_label.setObjectName("data_root_1_label")
        self.gridLayout_4.addWidget(self.data_root_1_label, 1, 0, 1, 1)
        self.data_root_2_label = QtWidgets.QLabel(self.build_dir_tab)
        self.data_root_2_label.setObjectName("data_root_2_label")
        self.gridLayout_4.addWidget(self.data_root_2_label, 1, 0, 1, 1)
        self.data_root_3_label = QtWidgets.QLabel(self.build_dir_tab)
        self.data_root_3_label.setObjectName("data_root_3_label")
        self.gridLayout_4.addWidget(self.data_root_3_label, 1, 0, 1, 1)
        self.daily_path_value_label = QtWidgets.QLabel(self.build_dir_tab)
        self.daily_path_value_label.setText("")
        self.daily_path_value_label.setObjectName("daily_path_value_label")
        self.gridLayout_4.addWidget(self.daily_path_value_label, 2, 1, 1, 1)
        # self.daily_path_1_value_label = QtWidgets.QLabel(self.build_dir_tab)
        # self.daily_path_1_value_label.setText("")
        # self.daily_path_1_value_label.setObjectName("daily_path_1_value_label")
        # self.gridLayout_4.addWidget(self.daily_path_1_value_label, 2, 1, 1, 1)
        self.data_root_pushButton = QtWidgets.QPushButton(self.build_dir_tab)
        self.data_root_pushButton.setObjectName("data_root_pushButton")
        self.gridLayout_4.addWidget(self.data_root_pushButton, 0, 1, 1, 1)
        self.data_root_1_pushButton = QtWidgets.QPushButton(self.build_dir_tab)
        self.data_root_1_pushButton.setObjectName("data_root_1_pushButton")
        self.gridLayout_4.addWidget(self.data_root_1_pushButton, 1, 1, 1, 1)
        self.data_root_2_pushButton = QtWidgets.QPushButton(self.build_dir_tab)
        self.data_root_2_pushButton.setObjectName("data_root_2_pushButton")
        self.gridLayout_4.addWidget(self.data_root_2_pushButton, 1, 1, 1, 1)
        self.data_root_3_pushButton = QtWidgets.QPushButton(self.build_dir_tab)
        self.data_root_3_pushButton.setObjectName("data_root_3_pushButton")
        self.gridLayout_4.addWidget(self.data_root_1_pushButton, 1, 1, 1, 1)
        self.imaging_system_label = QtWidgets.QLabel(self.build_dir_tab)
        self.imaging_system_label.setObjectName("imaging_system_label")
        self.gridLayout_4.addWidget(self.imaging_system_label, 4, 0, 1, 1)
        self.imaging_system_value_label = QtWidgets.QLabel(self.build_dir_tab)
        self.imaging_system_value_label.setText("")
        self.imaging_system_value_label.setObjectName("imaging_system_value_label")
        self.gridLayout_4.addWidget(self.imaging_system_value_label, 4, 1, 1, 1)
        self.tabWidget.addTab(self.build_dir_tab, "")
        self.select_dir_tab = QtWidgets.QWidget()
        self.select_dir_tab.setObjectName("select_dir_tab")
        self.gridLayout_5 = QtWidgets.QGridLayout(self.select_dir_tab)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.select_data_pushButton = QtWidgets.QPushButton(self.select_dir_tab)
        self.select_data_pushButton.setObjectName("select_data_pushButton")
        self.select_data_1_pushButton = QtWidgets.QPushButton(self.select_dir_tab)
        self.select_data_1_pushButton.setObjectName("select_data_1_pushButton")
        self.select_data_2_pushButton = QtWidgets.QPushButton(self.select_dir_tab)
        self.select_data_2_pushButton.setObjectName("select_data_2_pushButton")
        self.select_data_3_pushButton = QtWidgets.QPushButton(self.select_dir_tab)
        self.select_data_3_pushButton.setObjectName("select_data_3_pushButton")
        self.gridLayout_5.addWidget(self.select_data_pushButton, 0, 0, 1, 1)
        self.tabWidget.addTab(self.select_dir_tab, "")
        self.gridLayout_2.addWidget(self.tabWidget, 0, 0, 1, 3)
        self.run_pushButton = QtWidgets.QPushButton(self.frame)
        self.run_pushButton.setCheckable(True)
        self.run_pushButton.setObjectName("run_pushButton")
        self.gridLayout_2.addWidget(self.run_pushButton, 6, 0, 1, 3)
        self.file_prefix_label = QtWidgets.QLabel(self.frame)
        self.file_prefix_label.setObjectName("file_prefix_label")
        self.gridLayout_2.addWidget(self.file_prefix_label, 2, 0, 1, 1)
        self.file_path_label = QtWidgets.QLabel(self.frame)
        font = QtGui.QFont()
        font.setPointSize(8)
        self.file_path_label.setFont(font)
        self.file_path_label.setObjectName("file_path_label")
        self.gridLayout_2.addWidget(self.file_path_label, 4, 0, 1, 3)
        self.gridLayout.addWidget(self.frame, 0, 0, 2, 2)
        spacerItem1 = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.gridLayout.addItem(spacerItem1, 2, 0, 1, 1)

        self.retranslateUi(SaveBoxWidget)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(SaveBoxWidget)

    def retranslateUi(self, SaveBoxWidget):
        _translate = QtCore.QCoreApplication.translate
        SaveBoxWidget.setWindowTitle(_translate("SaveBoxWidget", "Form"))
        self.save_single_pushButton.setText(_translate("SaveBoxWidget", "Save Single"))
        self.file_number_label.setText(_translate("SaveBoxWidget", "File Number:"))
        self.file_prefix_lineEdit.setText(_translate("SaveBoxWidget", "jkam_capture"))
        self.daily_path_label.setText(_translate("SaveBoxWidget", "Daily Data Path:"))
        # self.daily_path_1_label.setText(_translate("SaveBoxWidget", "Daily Data Path 1:"))
        self.run_name_lineEdit.setText(_translate("SaveBoxWidget", "run0"))
        self.run_name_label.setText(_translate("SaveBoxWidget", "Run Name:"))
        # self.data_root_label.setText(_translate("SaveBoxWidget", "Data Root:"))
        self.data_root_pushButton.setText(_translate("SaveBoxWidget", "Select Data Root"))
        # self.data_root_1_label.setText(_translate("SaveBoxWidget", "Data Root 1:"))
        self.data_root_1_pushButton.setText(_translate("SaveBoxWidget", "Select Data Root 1"))
        self.imaging_system_label.setText(_translate("SaveBoxWidget", "Imaging System:"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.build_dir_tab), _translate("SaveBoxWidget", "Build Data Dir"))
        self.select_data_pushButton.setText(_translate("SaveBoxWidget", "Select Data Directory"))
        self.select_data_1_pushButton.setText(_translate("SaveBoxWidget", "Select Data Directory 1"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.select_dir_tab), _translate("SaveBoxWidget", "Select Data Dir"))
        self.run_pushButton.setText(_translate("SaveBoxWidget", "Begin Run"))
        self.file_prefix_label.setText(_translate("SaveBoxWidget", "File Prefix:"))
        self.file_path_label.setText(_translate("SaveBoxWidget", "Next File Name: jkam_capture_00000"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    SaveBoxWidget = QtWidgets.QWidget()
    ui = Ui_SaveBoxWidget()
    ui.setupUi(SaveBoxWidget)
    SaveBoxWidget.show()
    sys.exit(app.exec_())
