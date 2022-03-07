# pySpinCapture
A python wrapper and GUI for the FLIR PySpin API to capture synchronized video accross multiple cameras. Originally forked from Jason Keller's repo with the same name. (https://github.com/neurojak/pySpinCapture)

## Installation step by step on Ubuntu 20.04
Download and install Anaconda.
### Install Spinnaker SDK and API
- Download Spinnaker SDK and python API from https://flir.app.boxcn.net/v/SpinnakerSDK/folder/156995360267 - download version 2.5 because it works, 2.6 doesn't work for some reason in my hands
- Follow instructions in readme files to install them, in short:
   - install dependencies with:```sudo apt-get install libavcodec58 libavformat58 libswscale5 libswresample3 libavutil56 libusb-1.0-0 libpcre2-16-0 libdouble-conversion3 libxcb-xinput0 libxcb-xinerama0```
   - unzip the Spinnaker SDK files, go to the directory and install it with: ```sudo sh install_spinnaker.sh```
   - follow steps, enable everything, add user to flirusers group, and the SDK is installed
   - Create a conda environment for the python API: ```conda create -n pySpinCapture python=3.8```
   - Activate the conda environment: ```conda activate pySpinCapture```
   - Install dependencies ```pip install numpy matplotlib```
   - unzip spinnaker API you downloaded earlier, go in directory and install API with ```pip install spinnaker_python-2.5.0.156-cp38-cp38-linux_x86_64.whl``` note that you are still in the pySpinCapture environment

### Install dependencies for this package
```
pip install pyqt5 scikit-video 
```
### Install video card driver
FFMPEG hardware encoding with NVIDIA's h264_nvenc encoder, which is much faster and allows higher frame rates with minimal CPU/GPU and memory usage. This requires a compatible GPU as described at https://developer.nvidia.com/ffmpeg, https://trac.ffmpeg.org/wiki/HWAccelIntro.</br>
It worked out of the box with a GeForce GTX 970.

### Set computer-specific parameters
find the following lines in the pySpinCapture_GUI.py file and edit them:
```
skvideo.setFFmpegPath('/usr/bin/') #set path to ffmpeg installation before importing io
config_folder = '/home/labadmin/Data/pySpinCaptureConfig/' # folder where the config files will be saved
save_folder = '/home/labadmin/Data/Behavior_videos/' # folder where the movies will be saved
camera_names_in_order = ['bottom','side','body'] # user-defined camera names 
bpod_address = ('10.128.54.244',1001) # optional - IP address of bpod computer that runs the UDP server to receive the video names
```
## Usage
![image](https://user-images.githubusercontent.com/6236396/157129502-b13277c7-5e2d-4819-8aee-ba1f5b26e76c.png)
### Main window - pySpinCapture GUI
- Use the drop-down menu on the top-left to select a previously saved setting (e.g. one for each mouse).
- To add a new subject enter a name in the edit box on the upper right and hit enter. This will create a new subject with the currently active settings.
- To change the camera parameters, edit the boxes below, hit enter for your change to take effect. Note that for now the correct settings are not double-checked, if a setting is incorrect, it might crash the software.

### Camera windows - camera # - ####
- You can start/stop acquisition with the button on the top left of the window.
- By checking the preview checkbox, you can disable triggering and recording, so it's easier to set the camera parameters or just look at the mouse.
