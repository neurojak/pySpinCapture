
import sys, os, json
from datetime import datetime, timedelta

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton,  QLineEdit, QCheckBox, QHBoxLayout, QGroupBox, QDialog, QVBoxLayout, QGridLayout, QComboBox, QSizePolicy, qApp, QLabel,QPlainTextEdit,QMainWindow

from PyQt5.QtCore import  Qt, QObject, pyqtSignal
from PyQt5.QtGui import QPixmap
import logging 
import numpy as np
import cameraCapture
import threading, queue
from pathlib import Path
import skvideo

skvideo.setFFmpegPath('/usr/bin/') #set path to ffmpeg installation before importing io
config_folder = '/home/labadmin/Data/pySpinCaptureConfig/'
save_folder = '/home/labadmin/Data/Behavior_videos/'
camera_names_in_order = ['bottom','side','body']
bpod_address = ('10.128.54.244',1001)


#%

class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)
        
class Logger(QDialog):# simple logger
    def __init__(self, parent=None,camera_idx = None):
        super(Logger, self).__init__(parent)  
        
        windowLayout = QVBoxLayout()
        
        self.horizontalGroupBox_log = QGroupBox("logs")
        
        logTextBox = QTextEditLogger(self)
        # You can format what is printed to text box
        logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(logTextBox)
        # You can control the logging level
        logging.getLogger().setLevel(logging.DEBUG)
        layout =  QGridLayout()#QVBoxLayout()
        layout.addWidget(logTextBox.widget)
        self.setLayout(layout)
        
        self.horizontalGroupBox_log.setLayout(layout)
        windowLayout.addWidget(self.horizontalGroupBox_log)
        self.setLayout(windowLayout)
        self.show()
        
        
class SignalCommunicate(QObject):
    # https://stackoverflow.com/a/45620056
    data_to_display = pyqtSignal(QPixmap, str, int)    # image, string, camera ID
    log_message = pyqtSignal( str)
    
        
class CameraDisplay(QDialog): # standalone window for each camera
    def __init__(self, parent=None,camera_idx = None):
        super(CameraDisplay, self).__init__(parent)
        self.camera_idx = camera_idx
        self.setWindowTitle('Camera {} - {}'.format(camera_idx,self.parent().camera_parameters_list[self.camera_idx]['CAMERA_NAME']))
        self.setGeometry(1, 
                         500*camera_idx,
                         100,
                         100)  
        
        self.display = QLabel()
        self.status_label = QLabel('Camera offline')
        self.preview_checkbox = QCheckBox(self)
        self.preview_checkbox.setText('Preview')
        self.filename_label = QLabel('file path:')
        self.filename_edit = QLabel(os.path.join(self.parent().save_folder,
                                                 self.parent().camera_parameters_list[self.camera_idx]['CAMERA_NAME'],
                                                 self.parent().camera_parameters_list[self.camera_idx]['SUBJECT_NAME']))
        self.grid = QGridLayout()
        self.grid.addWidget(self.display,2,0,1,3)
        self.grid.addWidget(self.status_label,0,1)
        self.grid.addWidget(self.preview_checkbox,0,2)
        self.startbutton = QPushButton('Start')
        self.startbutton.setFocusPolicy(Qt.NoFocus)
        self.startbutton.clicked.connect(self.start_stop_camera)
        self.grid.addWidget(self.startbutton,0,0)
        self.grid.addWidget(self.filename_label,1,0)
        self.grid.addWidget(self.filename_edit,1,1)
        self.setLayout(self.grid)

        #self.setGeometry(50,50,320,200)
        sc = SignalCommunicate()
        sc.data_to_display.connect(self.display_frame)
        sc.log_message.connect(self.display_log)
        self.display_handles = {'display':self.display,
                                'status_label':self.status_label,
                                'start_button':self.startbutton,
                                'filename_label':self.filename_edit,
                                'bpod_address':bpod_address,
                                'signal_communicate':sc}
    def display_frame(self, px,text,camera_id):
        self.display.setPixmap(px)
        self.status_label.setText(text)
    def display_log(self,logtext):
        logging.info(logtext) 
        
    def start_stop_camera(self): 
        """
        Function that reads the text on the start/stop push button, and starts 
        the cameraCapture.MainLoop() on a separate thread, or stops the thread
        depending on the text on the button.
        Starting a camera creates a new directory where each trial will be saved
        as a separate file.
        """
        if self.startbutton.text() == 'Start':
            dir_name = os.path.join(self.parent().save_folder,
                                    self.parent().camera_parameters_list[self.camera_idx]['CAMERA_NAME'],
                                    self.parent().camera_parameters_list[self.camera_idx]['SUBJECT_NAME'],
                                    datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
            
            camera_parameters = self.parent().camera_parameters_list[self.camera_idx].copy()
            if self.preview_checkbox.isChecked():
                camera_parameters['SAVE_MOVIE'] = False
                camera_parameters['RECORDING_MODE'] = 'continuous'
                camera_parameters['MAX_FRAME_NUM'] = 5000
            
            if camera_parameters['SAVE_MOVIE']:
                Path(dir_name).mkdir( parents=True, exist_ok=True )
            self.camThread = threading.Thread(target=cameraCapture.MainLoop, args=(self.parent().cam_list[self.camera_idx] , 
                                                                                   camera_parameters,
                                                                                   self.parent().commQueue_list[self.camera_idx] ,
                                                                                   self.display_handles,
                                                                                   dir_name))
            self.camThread.start()
            self.startbutton.setText('Stop')
            logging.info('Camera {} armed'.format(self.camera_idx)) 
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
        self.left = 900 # 10
        self.top = 1 # 10
        self.width = 500    # 1024
        self.height = 800  # 768
        self.config_folder =  config_folder
        self.save_folder = save_folder
        
        self.system = cameraCapture.PySpin.System.GetInstance() # Get camera system
        self.cam_list = self.system.GetCameras() # Get camera list
        self.handles = {}
        self.camera_displays = []
        self.commQueue_list = []
        self.camThread_list = []
        self.camera_parameters_list = []
        
        self.initUI()
        
        for camera_idx, cam in enumerate(self.cam_list):
            self.commQueue_list.append(queue.Queue() )
            cam.Init()
            camera_display = CameraDisplay(self,camera_idx = camera_idx)
            self.camera_displays.append(camera_display)
            camera_display.show()
        self.logger = Logger(self)
        self.logger.show()
        
    def initUI(self):
        """
        Generates user interface, loads subject information for the first time.
        """
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        
        self.horizontalGroupBox_selector = QGroupBox("Subject / Camera")
        layout = QGridLayout()
        self.handles['subject_select'] = QComboBox(self)
        self.handles['subject_select'].setFocusPolicy(Qt.NoFocus)  
        self.load_subjects()
        
        
        layout.addWidget(QLabel('Subject'),0,1)
        layout.addWidget(self.handles['subject_select'],1, 1)
        self.handles['new_subject'] = QLineEdit('new subject comes here')
        self.handles['new_subject'].returnPressed.connect(self.add_new_subject)
        layout.addWidget(QLabel('New subject'),0,3)
        layout.addWidget(self.handles['new_subject'],1, 3)
        self.horizontalGroupBox_selector.setLayout(layout)
        
        
        self.horizontalGroupBox_videos = QGroupBox("Camera parameters")
        
        windowLayout = QVBoxLayout()
        windowLayout.addWidget(self.horizontalGroupBox_selector)
        windowLayout.addWidget(self.horizontalGroupBox_videos)

        self.setLayout(windowLayout)
        self.load_camera_parameters()
        self.show()
    
    def add_new_subject(self):
        """
        Reads out text from the new subject edit box and adds it as a new 
        subject. Uses the currently loaded configuration.
        """
        new_subject = self.handles['new_subject'].text()
        self.camera_save_parameters(new_subject)
        self.load_subjects(new_subject)
        
    
    def load_subjects(self,new_subject = None):
        """
        Finds the config files in self.config_folder and creates an entry
        in the GUI for each subject.
        """
        subject_names = []
        for subject_ in os.listdir(self.config_folder):
            if subject_.endswith('.json'):
                subject_names.append(subject_[:-5])
        try:
            self.handles['subject_select'].currentIndexChanged.disconnect()
        except:
            pass
        self.handles['subject_select'].clear()
        self.handles['subject_select'].addItems(subject_names)
        if not new_subject == None:
            self.handles['subject_select'].setCurrentText(new_subject)
        self.handles['subject_select'].currentIndexChanged.connect(lambda: self.load_camera_parameters())
        
        
        
    def load_camera_parameters(self):
        """
        This function loads camera parameters in the gui, also initializes
        the parameters gui when run at the first time. The number of columns 
        in the GUI can be set here.
        """
        maxcol = 3 # number of columns
        subject_now = self.handles['subject_select'].currentText()
        if subject_now == '':#no subject in the system
            self.camera_parameters_list = []
            for i in range(len(self.cam_list)):
                parameters_now = cameraCapture.default_parameters.copy()
                parameters_now['CAMERA_IDX']=i
                parameters_now['CAMERA_NAME']=camera_names_in_order[i]
                self.camera_parameters_list.append(parameters_now)
            subject_var_file = os.path.join(self.config_folder,'{}.json'.format(parameters_now['SUBJECT_NAME']))                       
            with open(subject_var_file, 'w') as outfile:
                json.dump(self.camera_parameters_list, outfile, indent=4)
        else:
            subject_var_file = os.path.join(self.config_folder,'{}.json'.format(subject_now))
            with open(subject_var_file) as json_file:
                self.camera_parameters_list = json.load(json_file)
        if 'camera_variables' not in self.handles.keys(): # GUI has to be initialized
            
            self.horizontalGroupbox_camera_variables =[]
            self.handles['camera_variables']= []
            layout = QGridLayout()
            for i,camera_parameters in enumerate(self.camera_parameters_list):
                
                horizontalGroupbox_camera_variables = QGroupBox("Camera: {} - {}".format(camera_parameters['CAMERA_IDX'],camera_parameters['CAMERA_NAME']))
                
                layout.addWidget(horizontalGroupbox_camera_variables ,i,0)
                layout_setup = QGridLayout()
                row = 0
                col = -1
                handles_camera_variables=dict()
                for idx,key in enumerate(camera_parameters.keys()):
                    if key in camera_parameters.keys():#self.pybpod_variables_to_display: # restrict entries here
                        col +=1
                        if col > maxcol:
                            col = 0
                            row += 1
                        layout_setup.addWidget(QLabel(key+':') ,row,col)
                        col +=1
                        handles_camera_variables[key] =  QLineEdit(str(camera_parameters[key]))
                        handles_camera_variables[key].returnPressed.connect(self.camera_save_parameters)
                        handles_camera_variables[key].textChanged.connect(self.camera_check_parameters)
                        layout_setup.addWidget(handles_camera_variables[key] ,row,col)
                horizontalGroupbox_camera_variables.setLayout(layout_setup)
                self.horizontalGroupbox_camera_variables.append(horizontalGroupbox_camera_variables)
                self.handles['camera_variables'].append(handles_camera_variables)
                #break
            self.horizontalGroupBox_videos.setLayout(layout)
                
        else:
            for i,camera_parameters in enumerate(self.camera_parameters_list):
                self.horizontalGroupbox_camera_variables[i].setTitle("Camera: {} - {}".format(camera_parameters['CAMERA_IDX'],camera_parameters['CAMERA_NAME']))
                for idx,key in enumerate(camera_parameters.keys()):
                    self.handles['camera_variables'][i][key].setText(str(camera_parameters[key]))
        logging.info('Subject parameters loaded for {}'.format(subject_now)) 

    def camera_save_parameters(self,new_subject_name = None):
        """
        This function checks if the variables of the parameters file line up 
        with the variables entered in the GUI. E.G. if the user enters string
        that should be int, it ignores that field.
        """
        camera_parameters_list_new = []
        for cam,parameters_dict,handles_camera_variables in zip(self.cam_list,self.camera_parameters_list,self.handles['camera_variables']):
            cameraCapture.initCam(cam,parameters_dict,True)
            if not new_subject_name == None:
                parameters_dict['SUBJECT_NAME'] = new_subject_name
            for key in parameters_dict.keys(): 
                
                # Auto formatting
                if type(parameters_dict[key]) == bool:
                    if 'true' in handles_camera_variables[key].text().lower() or '1' in handles_camera_variables[key].text():
                        parameters_dict[key] = True
                    else:
                        parameters_dict[key] = False
                elif type(parameters_dict[key]) == float:
                    try:
                        parameters_dict[key] = float(handles_camera_variables[key].text())
                    except:
                        print('not proper value')
                elif type(parameters_dict[key]) == int:                   
                    try:
                        parameters_dict[key] = int(round(float(handles_camera_variables[key].text())))
                    except:
                        print('not proper value')
                elif type(parameters_dict[key]) == str: 
                    if handles_camera_variables[key].text().lower().startswith('c') and key == 'RECORDING_MODE':
                        parameters_dict[key] = 'continuous'
                    elif handles_camera_variables[key].text().lower().startswith('t') and key == 'RECORDING_MODE':
                        parameters_dict[key] = 'triggered'
                    elif handles_camera_variables[key].text().lower() in ['side','bottom','body'] and key == 'CAMERA_NAME':
                         parameters_dict[key] = handles_camera_variables[key].text().lower()
                    elif key == 'CAMERA_NAME':
                        pass
                    else:
                        parameters_dict[key] = handles_camera_variables[key].text().lower()
                
                        
                         
            camera_parameters_list_new.append(parameters_dict)
        if new_subject_name == None:
            subject_now = self.handles['subject_select'].currentText()
        else:
            subject_now=new_subject_name
        subject_var_file = os.path.join(self.config_folder,'{}.json'.format(subject_now))                       
        with open(subject_var_file, 'w') as outfile:
            json.dump(camera_parameters_list_new, outfile, indent=4)
        self.camera_parameters_list = camera_parameters_list_new
        self.load_camera_parameters()

    def camera_check_parameters(self):
        """
        function that highlights a changed variable on the GUI to the user if 
        it is not saved yet. Useful but not crucial to have.

        """
        #TODO - to be implemented
        pass 
 


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MainWindow()
    sys.exit(app.exec_())   