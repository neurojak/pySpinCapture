# =============================================================================
# import sys
# import os
# import subprocess
# import serial.tools.list_ports
# from zaber.serial import AsciiSerial,AsciiCommand,BinarySerial,BinaryCommand
# import logging 
# from PyQt5.QtWidgets import QApplication, QWidget, QPushButton,  QLineEdit, QCheckBox, QHBoxLayout, QGroupBox, QDialog, QVBoxLayout, QGridLayout, QComboBox, QSizePolicy, qApp, QLabel,QPlainTextEdit
# from PyQt5.QtGui import QIcon
# 
# from PyQt5.QtCore import pyqtSlot, QTimer, Qt
# 
# from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
# 
# from matplotlib.figure import Figure
# import matplotlib.pyplot as plt
# from matplotlib.gridspec import GridSpec
# import pathlib
# import numpy as np
# import datetime
# import json
# from pathlib import Path
# #from scipy import stats
# import utils_pybpod
# import threading
# =============================================================================
import sys, os
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton,  QLineEdit, QCheckBox, QHBoxLayout, QGroupBox, QDialog, QVBoxLayout, QGridLayout, QComboBox, QSizePolicy, qApp, QLabel,QPlainTextEdit,QMainWindow

from PyQt5.QtCore import  Qt
import logging 
import numpy as np
import cameraCapture
import threading, queue

config_folder = '/home/rozmar/Data/pySpinCaptureConfig/'
save_folder = '/home/rozmar/Data/Behavior_videos/'
class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)
        

class CameraDisplay(QDialog): # standalone window for each camera
    def __init__(self, parent=None,camera_idx = None):
        super(CameraDisplay, self).__init__(parent)
        self.camera_idx = camera_idx
        self.setWindowTitle('Camera {}'.format(camera_idx))
        self.setGeometry(50, 
                         50,
                         self.parent().camera_parameters_list[self.camera_idx]['IMAGE_WIDTH'], 
                         self.parent().camera_parameters_list[self.camera_idx]['IMAGE_HEIGHT'])
        
        
        self.display = QLabel()
        self.status_label = QLabel('Camera offline')
        self.grid = QGridLayout()
        self.grid.addWidget(self.display,1,0,1,3)
        self.grid.addWidget(self.status_label,0,1)
        self.startbutton = QPushButton('Start')
        self.startbutton.setFocusPolicy(Qt.NoFocus)
        self.startbutton.clicked.connect(self.start_stop_camera)
        self.grid.addWidget(self.startbutton,0,0)
        
        self.setLayout(self.grid)

        #self.setGeometry(50,50,320,200)
        self.display_handles = {'display':self.display,
                                'status_label':self.status_label}
        
    def start_stop_camera(self): 
        """
        Function that reads the text on the start/stop push button, and starts 
        the cameraCapture.MainLoop() on a separate thread, or stops the thread
        depending on the text on the button.
        """
        if self.startbutton.text() == 'Start':
            self.camThread = threading.Thread(target=cameraCapture.MainLoop, args=(self.parent().cam_list[self.camera_idx] , 
                                                                                   self.parent().camera_parameters_list[self.camera_idx],
                                                                                   self.parent().commQueue_list[self.camera_idx] ,
                                                                                   self.display_handles,))
            self.camThread.start()
            self.startbutton.setText('Stop')
        elif self.startbutton.text() == 'Stop':
            if self.camThread.is_alive():
                self.parent().commQueue_list[self.camera_idx].put('STOP') #stop acquisition
            self.startbutton.setText('Start')
        
class MainWindow(QDialog):
    def __init__(self):
        super().__init__()
        print('started')
        self.dirs = dict()
        self.handles = dict()
        self.title = 'pySpinCapture GUI'
        self.left = 20 # 10
        self.top = 30 # 10
        self.width = 800    # 1024
        self.height = 600  # 768
        self.config_folder =  config_folder
        self.save_folder = save_folder
        
        self.system = cameraCapture.PySpin.System.GetInstance() # Get camera system
        self.cam_list = self.system.GetCameras() # Get camera list
        self.handles = {}
        self.camera_displays = []
        self.commQueue_list = []
        self.camThread_list = []
        self.camera_parameters_list = []
        
        
        parameters_camera = cameraCapture.default_parameters
        for camera_idx, cam in enumerate(self.cam_list):
            self.commQueue_list.append(queue.Queue() )
            cam.Init()
            self.camera_parameters_list.append(parameters_camera)
            
            camera_display = CameraDisplay(self,camera_idx = camera_idx)
            self.camera_displays.append(camera_display)
            camera_display.show()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        
        self.horizontalGroupBox_selector = QGroupBox("Subject / Camera")
        layout = QGridLayout()
        self.handles['subject_select'] = QComboBox(self)
        self.handles['subject_select'].setFocusPolicy(Qt.NoFocus)  
        subject_names = os.listdir(config_folder)
        self.handles['subject_select'].addItems(subject_names)
        self.handles['subject_select'].currentIndexChanged.connect(lambda: self.update_subject())
        
        layout.addWidget(self.handles['subject_select'],1, 1)
        self.handles['camera_select'] = QComboBox(self)
        self.handles['camera_select'].setFocusPolicy(Qt.NoFocus)  
        layout.addWidget(self.handles['camera_select'],1, 3)
        self.horizontalGroupBox_selector.setLayout(layout)
        
        
        self.horizontalGroupBox_videos = QGroupBox("Camera parameters")
        
        windowLayout = QVBoxLayout()
        windowLayout.addWidget(self.horizontalGroupBox_selector)
        windowLayout.addWidget(self.horizontalGroupBox_videos)

        self.setLayout(windowLayout)
        self.show()
    

    def update_subject(self):
        pass
    
# =============================================================================
#         self.horizontalGroupBox_subject_config = QGroupBox("Mouse")
#         layout = QGridLayout()
#         self.handles['subject_select'] = QComboBox(self)
#         self.handles['subject_select'].setFocusPolicy(Qt.NoFocus)
#         subjects = os.listdir(os.path.join(self.base_dir,'subjects'))
#         self.handles['subject_select'].addItems(subjects)
#         self.handles['subject_select'].currentIndexChanged.connect(lambda: self.update_subject())  
#         layout.addWidget(QLabel('Mouse ID'),0,0)
#         layout.addWidget(self.handles['subject_select'],1, 0)
# =============================================================================
    
# =============================================================================
#     def load_camera_parameters(self):
#         maxcol = 4 # number of columns
#         subject_now = self.handles['subject_select'].currentText()
#         if subject_now != '?':
#             subject_var_file = os.path.join(self.pybpod_dir,project_now,'subjects',subject_now,'variables.json')
#             setup_var_file = os.path.join(self.pybpod_dir,project_now,'experiments',experiment_now,'setups',setup_now,'variables.json')
#             with open(subject_var_file) as json_file:
#                 variables_subject = json.load(json_file)
#             with open(setup_var_file) as json_file:
#                 variables_setup = json.load(json_file)
#                 
#             if self.properties['bpod'] is None:
#                 
#                 layout = QGridLayout()
#                 self.horizontalGroupBox_bpod_variables_setup = QGroupBox("Setup: "+setup_now)
#                 self.horizontalGroupBox_bpod_variables_subject = QGroupBox("Subject: "+subject_now)
#                 layout.addWidget(self.horizontalGroupBox_bpod_variables_setup ,0,0)
#                 layout.addWidget(self.horizontalGroupBox_bpod_variables_subject ,1,0)
#                 self.horizontalGroupBox_bpod_variables.setLayout(layout)
#                 
#                 self.handles['bpod_variables_subject']=dict()
#                 self.handles['bpod_variables_subject']=dict()
#                 
#                 layout_setup = QGridLayout()
#                 row = 0
#                 col = -1
#                 self.handles['bpod_variables_setup']=dict()
#                 self.handles['bpod_variables_subject']=dict()
#                 for idx,key in enumerate(variables_setup.keys()):
#                     if key in self.pybpod_variables_to_display:
#                         col +=1
#                         if col > maxcol*2:
#                             col = 0
#                             row += 1
#                         layout_setup.addWidget(QLabel(key+':') ,row,col)
#                         col +=1
#                         self.handles['bpod_variables_setup'][key] =  QLineEdit(str(variables_setup[key]))
#                         self.handles['bpod_variables_setup'][key].returnPressed.connect(self.bpod_save_parameters)
#                         self.handles['bpod_variables_setup'][key].textChanged.connect(self.bpod_check_parameters)
#                         layout_setup.addWidget(self.handles['bpod_variables_setup'][key] ,row,col)
#                 self.horizontalGroupBox_bpod_variables_setup.setLayout(layout_setup)
#                 
#                 
#                 layout_subject = QGridLayout()
#                 row = 0
#                 col = -1
#                 for idx,key in enumerate(variables_subject.keys()):   # Read all variables in json file
#                     if key in self.pybpod_variables_to_display:   # But only show part of them
#                         col +=1
#                         if col > maxcol*2:
#                             col = 0
#                             row += 1
#                         layout_subject.addWidget(QLabel(key+':') ,row,col)
#                         col +=1
#                         self.handles['bpod_variables_subject'][key] =  QLineEdit(str(variables_subject[key]))
#                         self.handles['bpod_variables_subject'][key].returnPressed.connect(self.bpod_save_parameters)
#                         self.handles['bpod_variables_subject'][key].textChanged.connect(self.bpod_check_parameters)
#                         layout_subject.addWidget(self.handles['bpod_variables_subject'][key] ,row,col)
#                         
#                 self.horizontalGroupBox_bpod_variables_subject.setLayout(layout_subject)
#                 self.properties['bpod']=dict()
#             else:
#                 self.horizontalGroupBox_bpod_variables_subject.setTitle("Subject: "+subject_now)
#                 self.horizontalGroupBox_bpod_variables_setup.setTitle("Setup: "+setup_now)
#                 for key in self.handles['bpod_variables_subject'].keys():
#                     if key in variables_subject.keys():
#                         self.handles['bpod_variables_subject'][key].setText(str(variables_subject[key]))
#                     else:  # Just in case there are missing parameters (due to updated parameter tables) 
#                         self.handles['bpod_variables_subject'][key].setText("NA")
#                         self.handles['bpod_variables_subject'][key].setStyleSheet('QLineEdit {background: grey;}')
#                 for key in self.handles['bpod_variables_setup'].keys():
#                     self.handles['bpod_variables_setup'][key].setText(str(variables_setup[key]))
# 
#             self.properties['bpod']['subject'] = variables_subject
#             self.properties['bpod']['setup'] = variables_setup
#             self.properties['bpod']['subject_file'] = subject_var_file
#             self.properties['bpod']['setup_file'] = setup_var_file
#             
#     def bpod_check_parameters(self):
#         project_now = self.handles['bpod_filter_project'].currentText()
#         experiment_now = self.handles['bpod_filter_experiment'].currentText()
#         setup_now = self.handles['bpod_filter_setup'].currentText()
#         subject_now = self.handles['subject_select'].currentText()
#         subject_var_file = os.path.join(self.pybpod_dir,project_now,'subjects',subject_now,'variables.json')
#         setup_var_file = os.path.join(self.pybpod_dir,project_now,'experiments',experiment_now,'setups',setup_now,'variables.json')
#         with open(subject_var_file) as json_file:
#             variables_subject = json.load(json_file)
#         with open(setup_var_file) as json_file:
#             variables_setup = json.load(json_file)
#             
#         self.properties['bpod']['subject'] = variables_subject
#         self.properties['bpod']['setup'] = variables_setup
#         for dicttext in ['subject','setup']:
#             for key in self.handles['bpod_variables_'+dicttext].keys(): 
#                 valuenow = None
#                 
#                 # Auto formatting
#                 if key in self.properties['bpod'][dicttext].keys():  # If json file has the parameter in the GUI (backward compatibility). HH20200730
#                     if type(self.properties['bpod'][dicttext][key]) == bool:
#                         if 'true' in self.handles['bpod_variables_'+dicttext][key].text().lower() or '1' in self.handles['bpod_variables_'+dicttext][key].text():
#                             valuenow = True
#                         else:
#                             valuenow = False
#                     elif type(self.properties['bpod'][dicttext][key]) == float:
#                         try:
#                             valuenow = float(self.handles['bpod_variables_'+dicttext][key].text())
#                         except:
#                             print('not proper value')
#                             valuenow = None
#                     elif type(self.properties['bpod'][dicttext][key]) == int:                   
#                         try:
#                             valuenow = int(round(float(self.handles['bpod_variables_'+dicttext][key].text())))
#                         except:
#                             print('not proper value')
#                             valuenow = None
#                     elif type(self.properties['bpod'][dicttext][key]) == str:   
#                         if self.handles['bpod_variables_'+dicttext][key].text().lower() in ['left','right','any','none'] and key == 'WaitForLick':
#                             valuenow = self.handles['bpod_variables_'+dicttext][key].text().lower()
#                         elif self.handles['bpod_variables_'+dicttext][key].text().lower() in ['left','right'] and key == 'RewardLickPortOnNoLick':
#                              valuenow = self.handles['bpod_variables_'+dicttext][key].text().lower()
#                         else:
#                              valuenow = None
#                             
#                     # Turn the newly changed parameters to red            
#                     if valuenow == self.properties['bpod'][dicttext][key]:
#                         self.handles['bpod_variables_'+dicttext][key].setStyleSheet('QLineEdit {color: black;}')
#                     else:
#                         self.handles['bpod_variables_'+dicttext][key].setStyleSheet('QLineEdit {color: red;}')
#                 else:   # If json file has missing parameters (backward compatibility). HH20200730
#                     # self.handles['variables_subject'][key].setText("NA")
#                     self.handles['bpod_variables_subject'][key].setStyleSheet('QLineEdit {background: grey;}')
#                     
#                     
#         qApp.processEvents()
#         
#     def bpod_save_parameters(self):
#         project_now = self.handles['bpod_filter_project'].currentText()
#         experiment_now = self.handles['bpod_filter_experiment'].currentText()
#         setup_now = self.handles['bpod_filter_setup'].currentText()
#         subject_now = self.handles['subject_select'].currentText()
#         subject_var_file = os.path.join(self.pybpod_dir,project_now,'subjects',subject_now,'variables.json')
#         setup_var_file = os.path.join(self.pybpod_dir,project_now,'experiments',experiment_now,'setups',setup_now,'variables.json')
#         with open(subject_var_file) as json_file:
#             variables_subject = json.load(json_file)
#         with open(setup_var_file) as json_file:
#             variables_setup = json.load(json_file)
#         self.properties['bpod']['subject'] = variables_subject
#         self.properties['bpod']['setup'] = variables_setup
#         print('save')
#         for dicttext in ['subject','setup']:
#             for key in self.handles['bpod_variables_'+dicttext].keys(): 
#                 
#                 # Auto formatting
#                 if key in self.properties['bpod'][dicttext].keys():  # If json file has the parameter in the GUI (backward compatibility). HH20200730
#                     if type(self.properties['bpod'][dicttext][key]) == bool:
#                         if 'true' in self.handles['bpod_variables_'+dicttext][key].text().lower() or '1' in self.handles['bpod_variables_'+dicttext][key].text():
#                             self.properties['bpod'][dicttext][key] = True
#                         else:
#                             self.properties['bpod'][dicttext][key] = False
#                     elif type(self.properties['bpod'][dicttext][key]) == float:
#                         try:
#                             self.properties['bpod'][dicttext][key] = float(self.handles['bpod_variables_'+dicttext][key].text())
#                         except:
#                             print('not proper value')
#                     elif type(self.properties['bpod'][dicttext][key]) == int:                   
#                         try:
#                             self.properties['bpod'][dicttext][key] = int(round(float(self.handles['bpod_variables_'+dicttext][key].text())))
#                         except:
#                             print('not proper value')
#                     elif type(self.properties['bpod'][dicttext][key]) == str:   
#                         if self.handles['bpod_variables_'+dicttext][key].text().lower() in ['left','right','any','none'] and key == 'WaitForLick':
#                             self.properties['bpod'][dicttext][key] = self.handles['bpod_variables_'+dicttext][key].text().lower()
#                         elif self.handles['bpod_variables_'+dicttext][key].text().lower() in ['left','right'] and key == 'RewardLickPortOnNoLick':
#                              self.properties['bpod'][dicttext][key] = self.handles['bpod_variables_'+dicttext][key].text().lower()
#                             
#                 else:   # If json file has missing parameters, we add this new parameter (backward compatibility). HH20200730
#                     self.properties['bpod'][dicttext][key] = int(self.handles['bpod_variables_'+dicttext][key].text())   # Only consider int now
#                         
#         with open(self.properties['bpod']['setup_file'], 'w') as outfile:
#             json.dump(self.properties['bpod']['setup'], outfile, indent=4)
#         with open(self.properties['bpod']['subject_file'], 'w') as outfile:
#             json.dump(self.properties['bpod']['subject'], outfile, indent=4)
#             
#         self.bpod_load_parameters()
#         self.bpod_check_parameters()
# =============================================================================



if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MainWindow()
    sys.exit(app.exec_())   