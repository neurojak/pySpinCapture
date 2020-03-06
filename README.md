# pySpinCapture
a python wrapper to the FLIR PySpin API to capture synchronized video

cameraCapture.py is a minimal program to configure a FLIR BlackFly S camera to stream compressed video data
to disk and output it to the screen in real-time. It is based on the FLIR Spinnaker PySpin API and its examples, 
and uses skvideo to wrap FFMPEG for fast H264 compression and writing, as well as tkinter to output to the screen. 
The camera is configured to output its 'ExposureActive' signal on Line 1, which allows precise alignment with a 
separate DAQ system as long as you have a free analog input channel at ~2kHz or faster.

cameraCapture2cams.py extends functionality to 2 synchronized cameras, and uses triggering instead of freely 
running at the fastest possible frame rate.
