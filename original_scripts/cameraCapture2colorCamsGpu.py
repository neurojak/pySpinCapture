# Jason Keller
# September 2021
# =============================================================================
#  Program to set BlackFly S camera settings and acquire frames from 2 synchronized cameras and 
#  write them to a compressed video file. Based on FLIR Spinnaker API example code. This 
#  example uses color cameras with 24-bit RGB pixel format, and also checks camera serial
#  numbers to ensure correct enumeration.
# 
#  The intent is that this program started first, then will wait for triggers
#  on Line 0 (OPTO_IN) from the DAQ system. It is assumed that the DAQ system will provide
#  a specified number of triggers, and that the Line 0 black wires of both cameras are
#  soldered together and driven simultaneously. Both cameras output their "exposure active"
#  signal on Line 1 (OPTO_OUT, the white wire, which is pulled up to 3.3V via a 1.8kOhm resistor 
#  for each camera) so that each frame can be synchronized (DAQ should sample this at ~1kHz+).
#
#  Tkinter is used to provide a simple GUI to display the images, and skvideo 
#  is used as a wrapper to ffmpeg to write H.264 compressed video quickly, using
#  mostly default parameters.
#
#  To setup, you must download an FFMPEG executable and set an environment 
#  variable path to it (as well as setFFmpegPath function below). Other nonstandard
#  dependencies are the FLIR Spinnaker camera driver and PySpin package (see 
#  Spinnaker downloads), and the skvideo package. In this version, hardware encoding is used
#  which requires a compatible NVIDIA GPU with the drives installed before FFMPEG is compiled.
#  See: https://developer.nvidia.com/ffmpeg, https://trac.ffmpeg.org/wiki/HWAccelIntro
#  
#  NOTE: currently there is no check to see if readout can keep up with triggering
#  other that a timeout warning. It is up to the user to determine if the correct number
#  of frames are captured.
#
# TO DO:
# (1) report potential # missed frames (maybe use counter to count Line 1 edges and write to video file)
# (2) fix yellow artifact on first 14 frames
# =============================================================================

import PySpin, time, os, threading, queue
from datetime import datetime
import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
import skvideo
skvideo.setFFmpegPath('C:/Anaconda3/Lib/site-packages/ffmpeg') #set path to ffmpeg installation before importing io
import skvideo.io

#constants
SAVE_FOLDER_ROOT = 'C:/video'
FILENAME_ROOT = 'mj_' # optional identifier
EXPOSURE_TIME = 2001 #in microseconds
WAIT_TIME = 0.0001 #in seconds - this limits polling time and should be less than the frame rate period 
GAIN_VALUE = 0 #in dB, 0-40;
GAMMA_VALUE = 0.3 #0.25-1
IMAGE_HEIGHT = 512  #540 pixels default; this should be divisible by 16 for H264 compressed encoding
IMAGE_WIDTH = 512 #720 pixels default; this should be divisible by 16 for H264 compressed encoding
HEIGHT_OFFSET = 16 #round((540-IMAGE_HEIGHT)/2) # Y, to keep in middle of sensor; must be divisible by 4
WIDTH_OFFSET = 104# round((720-IMAGE_WIDTH)/2) # X, to keep in middle of sensor; must be divisible by 4
FRAMES_PER_SECOND = 100 #this is determined by triggers sent from behavior controller
FRAMES_TO_RECORD = 300*FRAMES_PER_SECOND #frame rate * num seconds to record; this should match # expected exposure triggers from DAQ counter output
CAM_TIMEOUT = 1000 #in ms; time to wait for another image before aborting
#FRAME_RATE_OUT = FRAMES_PER_SECOND #can alter ouput frame rate if necessary, but note that H264 limits this for playback, and this slows down video FFMPEG encoding dramatically

# generate output video directory and filename and make sure not overwriting
now = datetime.now()
mouseStr = input("Enter mouse ID: ") 
#groupStr = 'test_'
folderStr = '2021_09_test'
dateStr = now.strftime("_%Y_%m_%d") #save folder ex: 2020_01_01
timeStr = now.strftime("_%H_%M_%S") #filename ex: mj_09_30_59.mp4
#saveFolder = SAVE_FOLDER_ROOT + '/' + dateStr
saveFolder = SAVE_FOLDER_ROOT + '/' + folderStr
if not os.path.exists(saveFolder):
    os.mkdir(saveFolder)
os.chdir(saveFolder)
#movieName = FILENAME_ROOT + timeStr + '_' + groupStr + mouseStr + '.mp4'
movieName =  mouseStr + dateStr + timeStr + '.mp4'
fullFilePath = [saveFolder + '/' + movieName]
print('Video will be saved to: {}'.format(fullFilePath))
# get frame rate and query for video length based on this
print('# frames = {:d}'.format(FRAMES_TO_RECORD))

# SETUP FUNCTIONS #############################################################################################################
def initCam(cam): #function to initialize camera parameters for synchronized capture
    cam.Init()
    # load default configuration
    cam.UserSetSelector.SetValue(PySpin.UserSetSelector_Default)
    cam.UserSetLoad()
    # set acquisition. Continuous acquisition. Auto exposure off. Set frame rate using exposure time. 
    cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
    cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
    cam.ExposureMode.SetValue(PySpin.ExposureMode_Timed) #Timed or TriggerWidth (must comment out trigger parameters other that Line)
    cam.ExposureTime.SetValue(EXPOSURE_TIME)
    cam.AcquisitionFrameRateEnable.SetValue(False)
    #cam.AcquisitionFrameRate.SetValue(FRAMES_PER_SECOND)
    # set analog. Set Gain + Gamma. 
    cam.GainAuto.SetValue(PySpin.GainAuto_Off)
    cam.Gain.SetValue(GAIN_VALUE)
    cam.GammaEnable.SetValue(True)
    cam.Gamma.SetValue(GAMMA_VALUE)
    # set ADC bit depth and image pixel depth, size
    cam.AdcBitDepth.SetValue(PySpin.AdcBitDepth_Bit12) #use higher bit depth for better color image
    cam.PixelFormat.SetValue(PySpin.PixelFormat_RGB8Packed) #24 bits total; 8x R then G then B
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
    cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
    cam.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut) #Off or ReadOut to speed up
    cam.TriggerSource.SetValue(PySpin.TriggerSource_Line0)
    cam.TriggerActivation.SetValue(PySpin.TriggerActivation_RisingEdge) #LevelHigh or RisingEdge
    cam.TriggerSelector.SetValue(PySpin.TriggerSelector_FrameStart) # require trigger for each frame
    # optionally send exposure active signal on Line 2 (the white wire)
    cam.LineSelector.SetValue(PySpin.LineSelector_Line1)
    cam.LineMode.SetValue(PySpin.LineMode_Output) 
    cam.LineSource.SetValue(PySpin.LineSource_ExposureActive) #route desired output to Line 1 (try Counter0Active or ExposureActive)
    #cam.LineSelector.SetValue(PySpin.LineSelector_Line2)
    #cam.V3_3Enable.SetValue(True) #enable 3.3V rail on Line 2 (red wire) to act as a pull up for ExposureActive - this does not seem to be necessary as long as a pull up resistor is installed between the physical lines, and actually degrades signal quality 
    
def saveImage(imageWriteQueue, writer): #function to save video frames from the queue in a separate process
    while True:
        dequeuedImage = imageWriteQueue.get()
        if dequeuedImage is None:
            break
        else:
            writer.writeFrame(dequeuedImage) #call to ffmpeg
            imageWriteQueue.task_done()
                      
def camCapture(camQueue, cam, k): #function to capture images, convert to numpy, send to queue, and release from buffer in separate process
    while True:
        if k == 0: #wait infinitely for trigger for first image
            image = cam.GetNextImage() #get pointer to next image in camera buffer; blocks until image arrives via USB, within infinite timeout for first frame while waiting for DAQ to start sending triggers    
        elif (k) == (FRAMES_TO_RECORD):
            print('cam done ')
            break #stop loop and function when expected # frames found
        else:
            try:
                image = cam.GetNextImage(CAM_TIMEOUT) #get pointer to next image in camera buffer; blocks until image arrives via USB, within CAM_TIMEOUT
            except: #PySpin will throw an exception upon timeout, so end gracefully
                print('WARNING: timeout waiting for trigger! Aborting...press Ctrl-C to stop')
                print(str(k) + ' frames captured')
                break
                    
        npImage = np.array(image.GetData(), dtype="uint8").reshape(image.GetHeight(), image.GetWidth(), 3); #convert PySpin ImagePtr into numpy array; use uint8 for color channels x3
        camQueue.put(npImage)  
        image.Release() #release from camera buffer
        k = k + 1

# INITIALIZE CAMERAS & COMPRESSION ###########################################################################################
system = PySpin.System.GetInstance() # Get camera system
cam_list = system.GetCameras() # Get camera list
for i in range(cam_list.GetSize()): #hardcode serial numbers to ensure cameras enumerate in order
    camCurrent = cam_list[i]
    camSN = camCurrent.TLDevice.DeviceSerialNumber.ToString()
    if camSN == "21253509":
        camTop = camCurrent
    elif camSN == "21253501":
        camSide = camCurrent
del camCurrent
initCam(camTop) 
initCam(camSide) 
 
# setup output video file parameters (first make sure latencies are OK with conservative parameters, then try to optimize):  
# for now just use default h264_nvenc options
writer = skvideo.io.FFmpegWriter(movieName, outputdict={'-vcodec': 'h264_nvenc'}) # encoder is h264_nvenc or libx264
#writer = skvideo.io.FFmpegWriter(movieName, inputdict={'-pixel_format': 'rgb24'}, outputdict={'-vcodec': 'h264_nvenc'}) #can explicitly set input format, although FFMPEG will infer

#setup tkinter GUI (non-blocking, i.e. without mainloop) to output images to screen quickly
window = tk.Tk()
window.title("camera acquisition")
geomStrWidth = str(IMAGE_WIDTH*2 + 25)
geomStrHeight = str(IMAGE_HEIGHT + 35)
window.geometry(geomStrWidth + 'x' + geomStrHeight) # 3x width+25 x height+35; large enough for frames from 3 cameras + text
#textlbl = tk.Label(window, text="elapsed time: ")
textlbl = tk.Label(window, text="waiting for trigger...")
textlbl.grid(column=0, row=0)
imglabel = tk.Label(window) # make Label widget to hold image
imglabel.place(x=10, y=20) #pixels from top-left
window.update() #update TCL tasks to make window appear

#############################################################################
# start main program loop ###################################################
#############################################################################    

try:
    print('Press Ctrl-C to exit early and save video')
    i = 0
    imageWriteQueue = queue.Queue() #queue to pass images captures to separate compress and save thread
    camTopQueue = queue.Queue()  #queue to pass images from separate camTop acquisition thread
    camSideQueue = queue.Queue()  #queue to pass images from separate camSide acquisition thread
    # setup separate threads to accelerate image acquisition and saving, and start immediately:
    saveThread = threading.Thread(target=saveImage, args=(imageWriteQueue, writer,))
    camTopThread = threading.Thread(target=camCapture, args=(camTopQueue, camTop, i,))
    camSideThread = threading.Thread(target=camCapture, args=(camSideQueue, camSide, i,))
    saveThread.start()  
    
    camTop.BeginAcquisition()
    camSide.BeginAcquisition()
    camTopThread.start()
    camSideThread.start()   

    for i in range(FRAMES_TO_RECORD): # main acquisition loop
        camsNotReady = (camTopQueue.empty() or camSideQueue.empty()) # wait for all images ready from parallel threads
        while camsNotReady: #wait until ready in a loop
            time.sleep(WAIT_TIME)
            camsNotReady = (camTopQueue.empty() or camSideQueue.empty()) # wait for all images ready
           
        if i == 0:
            tStart = time.time()
            print('Capture begins')
        dequeuedAcq1 = camTopQueue.get() # get images formated as numpy from separate process queues as soon as they are both ready
        dequeuedAcq2 = camSideQueue.get()
        
        # now send concatenated image to FFMPEG saving queue
        enqueuedImageCombined = np.concatenate((dequeuedAcq1, dequeuedAcq2), axis=1)
        imageWriteQueue.put(enqueuedImageCombined) #put next combined image in saving queue
        
        if (i+1)%5 == 0: #update screen every X frames 
#            timeElapsed = str(time.time() - tStart)
#            timeElapsedStr = "elapsed time: " + timeElapsed[0:5] + " sec"
            framesElapsedStr = "frame #: " + str(i+1) + " of " + str(FRAMES_TO_RECORD)
            textlbl.configure(text=framesElapsedStr)
            I = ImageTk.PhotoImage(Image.fromarray(enqueuedImageCombined))
            imglabel.configure(image=I)
            imglabel.image = I #keep reference to image
            window.update() #update on screen (this must be called from main thread)

        if (i+1) == (FRAMES_TO_RECORD):
            print('Complete ' + str(i+1) + ' frames captured')
            tEndAcq = time.time()

# end aqcuisition loop #############################################################################################            
except KeyboardInterrupt: #if user hits Ctrl-C, everything should end gracefully
    tEndAcq = time.time()
    pass        
        
camTop.EndAcquisition() 
camSide.EndAcquisition()
textlbl.configure(text='Capture complete, still writing to disk...') 
window.update()
print('Capture ends at: {:.2f}sec'.format(tEndAcq - tStart))
#   print('calculated frame rate: {:.2f}FPS'.format(numImages/(t2 - t1)))
imageWriteQueue.join() #wait until compression and saving queue is done writing to disk
tEndWrite = time.time()
print('File written at: {:.2f}sec'.format(tEndWrite - tStart))
writer.close() #close to FFMPEG writer
window.destroy() 
    
# delete all pointers/variable/etc:
camTop.DeInit()
camSide.DeInit()
del camTop
del camSide
cam_list.Clear()
del cam_list
system.ReleaseInstance()
del system
print('Done!')
