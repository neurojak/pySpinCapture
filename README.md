# pySpinCapture
A python wrapper and GUI for the FLIR PySpin API to capture synchronized video accross multiple cameras. Originally forked from Jason Keller's repo with the same name. (https://github.com/neurojak/pySpinCapture)
### Features
- Configs are saved in .json files and can be loaded within the GUI.
- Displays frames at video rate for the user.
- Multiple cameras (2 tested)
- Online GPU accelerated compression and writing to disk.
- Trial ends are recognized by a gap in frame triggers. Each trial goes in a separate file.
- Broadcasts file names to an UDP server (which should be run separately), so pybpod can save the name of each video file.
- Frametimes and camera parameters are saved in .json files next to the movies
### Wishlist
- GUI should check if camera parameters are correct - right now it just crashes if it receives an inappropriate variable from the user
- step-by-step windows installation guide
- UDP control from bpod
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

## Installation step by step on Windows 10
### Install Spinnaker SDK and API
### Install dependencies for this package
### Install video card driver

## Set computer-specific parameters
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

### day-to-day usage
- Start the GUI.
- (optional) Create a new configuration or modify an existing one.
- Select the configuration you need from the drop-down menu.
- Click start on all cameras.
- Start the behavior.

## Data structure
### Camera parameters
A json file that contains the following fields. Saved for each recording next to the generated movies.
```
{
    "EXPOSURE_TIME": 3000,
    "WAIT_TIME": 0.001,
    "GAIN_VALUE": 10,
    "GAMMA_VALUE": 0.3,
    "IMAGE_HEIGHT": 500,
    "IMAGE_WIDTH": 900,
    "HEIGHT_OFFSET": 336,
    "WIDTH_OFFSET": 200,
    "CAM_TIMEOUT": 50,
    "MAX_FRAME_NUM": 10000,
    "RECORDING_MODE": "continuous",
    "CAMERA_IDX": 0,
    "DISPLAY_DOWNSAMPLE": 1,
    "CAMERA_NAME": "bottom",
    "SAVE_MOVIE": true,
    "SUBJECT_NAME": "test_subject",
    "COMPRESSION_LEVEL": 23,
    "COMPRESSION_THREADS": 4
}
```
### Directory structure
```
.
├── bottom                                                (Camera ID defined in "CAMERA_NAME")
│   └── test_subject                                      (Name of the mouse defined in "SUBJECT_NAME")
│       └── 2022-03-08_15-46-06                           (Date and time when the Start button was pressed)
│           ├── camera_parameters.json                    (Camera parameters used for acquisition)
│           ├── trial_00000__2022-03-08_15-46-06.json     (json file containing metadata, contents below)
│           ├── trial_00000__2022-03-08_15-46-06.mp4      (compressed video file)
│           ├── trial_00001__2022-03-08_15-46-17.json      
│           ├── trial_00001__2022-03-08_15-46-17.mp4
│           ├── trial_00002__2022-03-08_15-46-24.json     (each trial has its own video and metadata file)
│           ├── trial_00002__2022-03-08_15-46-24.mp4
│           ├── trial_00003__2022-03-08_15-46-30.json
│           └── trial_00003__2022-03-08_15-46-30.mp4

```

### Metadata contents
```
{
    "pc_movie_start_time": "2022-03-08 15:46:12.494111",  (PC time at the time of the first frame. - this has a jitter depending on the load on the PC)
    "camera_movie_start_time": 442380.775340136,          (Camera timestamp at the time of the first frame. - seconds from camera turned on)
    "frame_times": [                                      (Timestamp of each frame relative to the first frame. - seconds)
        0.0,
        0.0023845359683036804,
        0.0047846719971857965,
        0.007184135960415006,                             (The number of frames in the movie and timestamps in this list should be equal.)
        0.009587887965608388,
        0.011988159967586398,
        0.014388047973625362,
        ...
}
```
