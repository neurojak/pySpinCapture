
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
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton,  QLineEdit, QCheckBox, QHBoxLayout, QGroupBox, QDialog, QVBoxLayout, QGridLayout, QComboBox, QSizePolicy, qApp, QLabel,QPlainTextEdit,QMainWindow

from PyQt5.QtCore import  Qt
import logging 
import numpy as np
import cameraCapture
import threading, queue


class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)
        

class CameraDisplay(QDialog):
    def __init__(self, parent=None,camera_idx = None):
        super(CameraDisplay, self).__init__(parent)
        self.camera_idx = camera_idx
        self.setWindowTitle('Camera {}'.format(camera_idx))
        
        
        
        self.display = QLabel()
        self.status_label = QLabel('Camera offline')
        self.grid = QGridLayout()
        self.grid.addWidget(self.display,1,1)
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
        
        
        
class App(QDialog):
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
        
        
        self.system = cameraCapture.PySpin.System.GetInstance() # Get camera system
        self.cam_list = self.system.GetCameras() # Get camera list
        self.camera_displays = []
        self.commQueue_list = []
        self.camThread_list = []
        self.camera_parameters_list = []
        parameters_camera = cameraCapture.default_parameters
        for camera_idx, cam in enumerate(self.cam_list):
            camcommQueue = queue.Queue()
            self.commQueue_list.append(camcommQueue )
            cam.Init()
            self.camera_parameters_list.append(parameters_camera)
            
            camera_display = CameraDisplay(self,camera_idx = camera_idx)
            self.camera_displays.append(camera_display)
            camera_display.show()
        #print(camera_display.display_handles)

# =============================================================================
#         self.properties = {'zaber':zaber_properties,
#                            'arduino':arduino_properties,
#                            'bpod':None,
#                            'teensy':{}}
# =============================================================================
        
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.createGridLayout()
        
        windowLayout = QVBoxLayout()
        windowLayout.addWidget(self.horizontalGroupBox_videos)

        self.setLayout(windowLayout)
        self.show()
    
    def createGridLayout(self):
        self.horizontalGroupBox_videos = QGroupBox("Camera parameters")
        
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
    



if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())   