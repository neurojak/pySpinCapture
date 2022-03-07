
import sys, os, json
from datetime import datetime

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton,  QLineEdit, QCheckBox, QHBoxLayout, QGroupBox, QDialog, QVBoxLayout, QGridLayout, QComboBox, QSizePolicy, qApp, QLabel,QPlainTextEdit,QMainWindow

from PyQt5.QtCore import  Qt
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


#%%

class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)
        
class Logger(QDialog): # standalone window for each camera
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
        
        
        
        
class CameraDisplay(QDialog): # standalone window for each camera
    def __init__(self, parent=None,camera_idx = None):
        super(CameraDisplay, self).__init__(parent)
        self.camera_idx = camera_idx
        self.setWindowTitle('Camera {} - {}'.format(camera_idx,self.parent().camera_parameters_list[self.camera_idx]['CAMERA_NAME']))
        self.setGeometry(50, 
                         50,
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
        self.display_handles = {'display':self.display,
                                'status_label':self.status_label,
                                'start_button':self.startbutton,
                                'filename_label':self.filename_edit,
                                'bpod_address':bpod_address}
        
    def start_stop_camera(self): 
        """
        Function that reads the text on the start/stop push button, and starts 
        the cameraCapture.MainLoop() on a separate thread, or stops the thread
        depending on the text on the button.
        """
        if self.startbutton.text() == 'Start':
            dir_name = os.path.join(self.parent().save_folder,
                                    self.parent().camera_parameters_list[self.camera_idx]['CAMERA_NAME'],
                                    self.parent().camera_parameters_list[self.camera_idx]['SUBJECT_NAME'],
                                    datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
            Path(dir_name).mkdir( parents=True, exist_ok=True )
            camera_parameters = self.parent().camera_parameters_list[self.camera_idx].copy()
            if self.preview_checkbox.isChecked():
                camera_parameters['SAVE_MOVIE'] = False
                camera_parameters['RECORDING_MODE'] = 'continuous'
                
                
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
        new_subject = self.handles['new_subject'].text()
        self.camera_save_parameters(new_subject)
        self.load_subjects(new_subject)
        
    
    def load_subjects(self,new_subject = None):
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

    def camera_save_parameters(self,new_subject_name = None):
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

            
# =============================================================================
#         self.bpod_load_parameters()
#         self.bpod_check_parameters()
# =============================================================================
    def camera_check_parameters(self):
       pass 
    
# =============================================================================
#     #%%
#     with open(os.path.join(config_folder,'{}.json'.format(subject_name)), 'w') as outfile:
#         json.dump(lista, outfile, indent=4)
#     #%%
# =============================================================================

    
# =============================================================================
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
# =============================================================================
        
    



if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MainWindow()
    sys.exit(app.exec_())   