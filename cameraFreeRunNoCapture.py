# Jason Keller
# Feb 2021
# =============================================================================
#  Program to output cameras to screen until Ctrl-C is pressed, based on
#  capture program (see for details)
# =============================================================================

import PySpin, time, threading, queue
from datetime import datetime
import tkinter as tk
from PIL import Image, ImageTk
import numpy as np


#constants
EXPOSURE_TIME = 500 #in microseconds
WAIT_TIME = 0.0001 #in seconds - this limits polling time and should be less than the frame rate period 
GAIN_VALUE = 10 #in dB, 0-40;
GAMMA_VALUE = 0.4 #0.25-1
IMAGE_HEIGHT = 500  #540 pixels default
IMAGE_WIDTH = 500 #720 pixels default
HEIGHT_OFFSET = 20 #round((540-IMAGE_HEIGHT)/2) # Y, to keep in middle of sensor
WIDTH_OFFSET = 56 #((720-IMAGE_WIDTH)/2) # X, to keep in middle of sensor
FRAMES_TO_RECORD = 600000 #frame rate * num seconds to record; this should match # expected exposure triggers from DAQ counter output
CAM_TIMEOUT = 1000 #in ms; time to wait for another image before aborting
#FRAME_RATE_OUT = 250

# generate output video directory and filename and make sure not overwriting
now = datetime.now()

# SETUP FUNCTIONS #############################################################################################################
def initCam(cam): #function to initialize camera parameters for synchronized capture
    cam.Init()
    # load default configuration
    cam.UserSetSelector.SetValue(PySpin.UserSetSelector_Default)
    cam.UserSetLoad()
    # set acquisition. Continues acquisition. Auto exposure off. Set frame rate using exposure time. 
    cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
    cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
    cam.ExposureMode.SetValue(PySpin.ExposureMode_Timed) #Timed or TriggerWidth (must comment out trigger parameters other that Line)
    cam.ExposureTime.SetValue(EXPOSURE_TIME)
    cam.AcquisitionFrameRateEnable.SetValue(False)
    # set analog. Set Gain + Gamma. 
    cam.GainAuto.SetValue(PySpin.GainAuto_Off)
    cam.Gain.SetValue(GAIN_VALUE)
    cam.GammaEnable.SetValue(True)
    cam.Gamma.SetValue(GAMMA_VALUE)
    # set ADC bit depth and image pixel depth, size
    cam.AdcBitDepth.SetValue(PySpin.AdcBitDepth_Bit10)
    cam.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
    cam.Width.SetValue(IMAGE_WIDTH)
    cam.Height.SetValue(IMAGE_HEIGHT)
    cam.OffsetX.SetValue(WIDTH_OFFSET)
    cam.OffsetY.SetValue(HEIGHT_OFFSET)
    # setup FIFO buffer
    camTransferLayerStream = cam.GetTLStreamNodeMap()
    handling_mode1 = PySpin.CEnumerationPtr(camTransferLayerStream.GetNode('StreamBufferHandlingMode'))
    handling_mode_entry = handling_mode1.GetEntryByName('OldestFirst')
    handling_mode1.SetIntValue(handling_mode_entry.GetValue())
    # set trigger input to Line0 (the black wire)
    cam.TriggerMode.SetValue(PySpin.TriggerMode_Off) #just free run
    # optionally send exposure active signal on Line 2 (the white wire)
    cam.LineSelector.SetValue(PySpin.LineSelector_Line1)
    cam.LineMode.SetValue(PySpin.LineMode_Output) 
    cam.LineSource.SetValue(PySpin.LineSource_ExposureActive) #route desired output to Line 1 (try Counter0Active or ExposureActive)
    #cam.LineSelector.SetValue(PySpin.LineSelector_Line2)
    #cam.V3_3Enable.SetValue(True) #enable 3.3V rail on Line 2 (red wire) to act as a pull up for ExposureActive - this does not seem to be necessary as long as a pull up resistor is installed between the physical lines, and actually degrades signal quality 
    
                      
def camCaptureNoTrig(camQueue, cam): #function to capture images, convert to numpy, send to queue, and release from buffer in separate process
    while True:
        try:
            image = cam.GetNextImage(CAM_TIMEOUT) #get pointer to next image in camera buffer; blocks until image arrives via USB, within CAM_TIMEOUT
        except: #PySpin will throw an exception upon timeout, so end gracefully
            break
                    
        npImage = np.array(image.GetData(), dtype="uint8").reshape( (image.GetHeight(), image.GetWidth()) ); #convert PySpin ImagePtr into numpy array
        camQueue.put(npImage)  
        image.Release() #release from camera buffer

# INITIALIZE CAMERAS & COMPRESSION ###########################################################################################
system = PySpin.System.GetInstance() # Get camera system
cam_list = system.GetCameras() # Get camera list
cam1 = cam_list[0] #0 for 'right' camera, 1 for 'left' camera
cam2 = cam_list[1]
initCam(cam1) 
initCam(cam2)
 
#setup tkinter GUI (non-blocking, i.e. without mainloop) to output images to screen quickly
window = tk.Tk()
window.title("camera free run")
geomStrWidth = str(IMAGE_WIDTH*2 + 25)
geomStrHeight = str(IMAGE_HEIGHT + 35)
window.geometry(geomStrWidth + 'x' + geomStrHeight) # 2x width+25 x height+35; large enough for frames from 2 cameras + text
textlbl = tk.Label(window, text="elapsed time: ")
textlbl.grid(column=0, row=0)
imglabel = tk.Label(window) # make Label widget to hold image
imglabel.place(x=10, y=20) #pixels from top-left
window.update() #update TCL tasks to make window appear

#############################################################################
# start main program loop ###################################################
#############################################################################    

try:
    print('Press Ctrl-C to exit early')
    i = 0
    imageWriteQueue = queue.Queue() #queue to pass images captures to separate compress and save thread
    cam1Queue = queue.Queue()  #queue to pass images from separate cam1 acquisition thread
    cam2Queue = queue.Queue()  #queue to pass images from separate cam2 acquisition thread
    # setup separate threads to accelerate image acquisition and saving, and start immediately:
    cam1Thread = threading.Thread(target=camCaptureNoTrig, args=(cam1Queue, cam1,))
    cam2Thread = threading.Thread(target=camCaptureNoTrig, args=(cam2Queue, cam2,))
    
    cam1.BeginAcquisition()
    cam2.BeginAcquisition()
    cam1Thread.start()
    cam2Thread.start()  
    
    tStart = time.time()
    print('Capture begins')

    while(True): # main acquisition loop
        camsNotReady = cam1Queue.empty() # wait for both images ready from parallel threads
        while camsNotReady: #wait until ready in a loop
            time.sleep(WAIT_TIME)
            camsNotReady = (cam1Queue.empty() or cam2Queue.empty()) # wait for both images ready

        dequeuedAcq1 = cam1Queue.get() # get images formated as numpy from separate process queues as soon as they are both ready
        dequeuedAcq2 = cam2Queue.get()
        # now concatenate images
        enqueuedImageCombined = np.concatenate((dequeuedAcq1, dequeuedAcq2), axis=1)
        
        if (i+1)%20 == 0: #update screen every X frames 
            timeElapsed = str(time.time() - tStart)
            timeElapsedStr = "elapsed time: " + timeElapsed[0:5] + " sec"
            textlbl.configure(text=timeElapsedStr)
            I = ImageTk.PhotoImage(Image.fromarray(enqueuedImageCombined))
            imglabel.configure(image=I)
            imglabel.image = I #keep reference to image
            window.update() #update on screen (this must be called from main thread)

        i = i + 1

# end aqcuisition loop #############################################################################################            
except KeyboardInterrupt: #if user hits Ctrl-C, everything should end gracefully
    tEndAcq = time.time()
    pass        
        
cam1.EndAcquisition()
cam2.EndAcquisition() 
window.update()
print('Capture ends at: {:.2f}sec'.format(tEndAcq - tStart))
window.destroy() 
    
# delete all pointers/variable/etc:
cam1.DeInit()
cam2.DeInit()
del cam1
del cam2
cam_list.Clear()
del cam_list
system.ReleaseInstance()
del system
print('Done!')
