# pySpinCapture
a python wrapper to the FLIR PySpin API to capture synchronized video

## Installation step by step on Ubuntu 20.04
Download and install Anaconda.
### Install Spinnaker SDK and API
- Download Spinnaker SDK and python API from https://www.flir.com/products/spinnaker-sdk/, then follow instructions in readme files to install them, in short:
   - install dependencies with:```sudo apt-get install libavcodec58 libavformat58 libswscale5 libswresample3 libavutil56 libusb-1.0-0 libpcre2-16-0 libdouble-conversion3 libxcb-xinput0 libxcb-xinerama0```
   - unzip the Spinnaker SDK files, go to the directory and install it with: ```sudo sh install_spinnaker.sh```
   - follow steps, enable everything, add user to flirusers group, and the SDK is installed
   - Create a conda environment for the python API: ```conda create -n pySpinCapture python=3.8```
   - Activate the conda environment: ```conda activate pySpinCapture```
   - Install dependencies ``pip install numpy matplotlib```
   - unzip spinnaker API you downloaded earlier, go in directory and install API with ```pip install spinnaker_python-2.6.0.156-cp38-cp38-linux_x86_64.whl``` note that you are still in the pySpinCapture environment

### Install dependencies for this package
```
pip install pyqt5 scikit-video 
```

- 


cameraCapture.py is a minimal program to configure a FLIR BlackFly S monochrome camera to stream compressed video data
to disk and output it to the screen in real-time. It is based on the FLIR Spinnaker PySpin API and its examples, 
and uses skvideo to wrap FFMPEG for fast H264 compression and writing, as well as tkinter to output to the screen. 
The camera is configured to output its 'ExposureActive' signal on Line 1, which allows precise alignment with a 
separate DAQ system as long as you have a free analog input channel at ~2x the frame rate or faster. This version
does not include triggering, so that the camera can run as fast as possible.

cameraCapture2cams.py extends functionality to 2 synchronized cameras, and uses triggering instead of freely 
running at the fastest possible frame rate. Note that this version requires a trigger to be sent to the cameras on
Line 0's, which are physically connected. 

cameraCapture2camsGpu.py is similar to cameraCapture2cams.py, but uses FFMPEG hardware encoding with NVIDIA's h264_nvenc
encoder, which is much faster and allows higher frame rates with minimal CPU/GPU and memory usage. This requires a compatible 
GPU as described at https://developer.nvidia.com/ffmpeg, https://trac.ffmpeg.org/wiki/HWAccelIntro.

cameraCapture2colorCamsGpu.py provides an example for color recording (RGB24 pixel format) using the h264_nvenc.

cameraFreeRunNoCapture.py just outputs 2 camera streams to the monitor without saving.

All versions require a pull-up resistor to be installed between camera Line 1 and 3.3V signals to drive the exposure 
signal properly (as recommended in FLIR documentation; ~1-10 kOhm seems to work well).

INSTALLATION:
Most of the dependencies in the import statements are included in a standard Anaconda installation (i.e. PIL, Numpy, Tkinter) and with your NVIDIA graphics card (i.e CUDA) for the GPU versions. PySpin and the Spinnaker API must be downloaded from the FLIR website (https://www.flir.com/products/spinnaker-sdk/); choose the appropriate version of Spinnaker and install first, then install the "Latest Python Spinnaker" version that is compatible with your version of Python (I've tested with Python 3.5 & 3.8) using the instructions in the ReadMe file. An FFMPEG executable needs to be downlaoded (https://ffmpeg.org/download.html) and placed in a folder that you can point to in the import statements, such as within the site-packages folder of your Python installation. Finally, scikit-video (http://www.scikit-video.org/stable/) can be added to your Python installation using pip.
