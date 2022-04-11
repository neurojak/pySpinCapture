import PySpin, time, os, threading, queue
from datetime import datetime, timedelta
import tkinter as tk
from PIL import Image, ImageTk
from PyQt5.QtGui import QImage,QPixmap
import numpy as np
import skvideo
import skvideo.io
import socket
import json


#%
default_parameters  = {'EXPOSURE_TIME': 5000, #in microseconds
                     'WAIT_TIME' : 0.001, #in seconds - this limits polling time and should be less than the frame rate period 
                     'GAIN_VALUE' : 5, #in dB, 0-40;
                     'GAMMA_VALUE' : 0.4, #0.25-1
                     'IMAGE_HEIGHT' : 1080,  #540 pixels default; this should be divisible by 16 for H264 compressed encoding
                     'IMAGE_WIDTH' : 1420, #720 pixels default; this should be divisible by 16 for H264 compressed encoding
                     'HEIGHT_OFFSET' : 0, #round((540-IMAGE_HEIGHT)/2) # Y, to keep in middle of sensor; must be divisible by 4
                     'WIDTH_OFFSET' : 0, # round((720-IMAGE_WIDTH)/2) # X, to keep in middle of sensor; must be divisible by 4
                     'CAM_TIMEOUT' : 200, #in ms; time to wait for another image before aborting
                     'MAX_FRAME_NUM':100000,
                     'RECORDING_MODE':'continuous', #continuous / triggered
                     'CAMERA_IDX':0,
                     'DISPLAY_DOWNSAMPLE':1,
                     'CAMERA_NAME':'side',
                     'SAVE_MOVIE':False,
                     'SUBJECT_NAME' : '_full_field', # optional identifier}
                     'COMPRESSION_LEVEL':23, #0-51 bigger number means worse quality, smaller size
                     'COMPRESSION_THREADS':4
                     }

def initCam(cam,parameters_dict,restricted = False):
    """
    Function that initializes camera and sets parameters according to the parameters_dict

    Parameters
    ----------
    cam : PySpin camera instance (PySpin.System.GetInstance().GetCameras())
        camera handle
    parameters_dict : dictionary
        containing all parameters

    Returns
    -------
    None.

    """    
    if restricted:
        cam.Gain.SetValue(parameters_dict['GAIN_VALUE'])
        cam.Gamma.SetValue(parameters_dict['GAMMA_VALUE'])
        cam.ExposureTime.SetValue(parameters_dict['EXPOSURE_TIME'])
    else:
        cam.Init()
        # load default configuration
        cam.UserSetSelector.SetValue(PySpin.UserSetSelector_Default)
        cam.UserSetLoad()
        # set acquisition. Continues acquisition. Auto exposure off. Set frame rate using exposure time. 
        cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
        cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        cam.ExposureMode.SetValue(PySpin.ExposureMode_Timed) #Timed or TriggerWidth (must comment out trigger parameters other that Line)
        cam.ExposureTime.SetValue(parameters_dict['EXPOSURE_TIME'])
        cam.AcquisitionFrameRateEnable.SetValue(False)
        # set analog. Set Gain + Gamma. 
        cam.GainAuto.SetValue(PySpin.GainAuto_Off)
        cam.Gain.SetValue(parameters_dict['GAIN_VALUE'])
        cam.GammaEnable.SetValue(True)
        cam.Gamma.SetValue(parameters_dict['GAMMA_VALUE'])
        # set ADC bit depth and image pixel depth, size
        cam.AdcBitDepth.SetValue(PySpin.AdcBitDepth_Bit10)
        cam.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
        cam.Width.SetValue(parameters_dict['IMAGE_WIDTH'])
        cam.Height.SetValue(parameters_dict['IMAGE_HEIGHT'])
        cam.OffsetX.SetValue(parameters_dict['WIDTH_OFFSET'])
        cam.OffsetY.SetValue(parameters_dict['HEIGHT_OFFSET'])
        # setup FIFO buffer
        camTransferLayerStream = cam.GetTLStreamNodeMap()
        handling_mode1 = PySpin.CEnumerationPtr(camTransferLayerStream.GetNode('StreamBufferHandlingMode'))
        handling_mode_entry = handling_mode1.GetEntryByName('OldestFirst')
        handling_mode1.SetIntValue(handling_mode_entry.GetValue())
        # set trigger input to Line0 (the black wire)
        if parameters_dict['RECORDING_MODE'] == 'triggered':
            cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
            cam.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut) #Off or ReadOut to speed up
            cam.TriggerSource.SetValue(PySpin.TriggerSource_Line0)
            cam.TriggerActivation.SetValue(PySpin.TriggerActivation_RisingEdge) #LevelHigh or RisingEdge
            cam.TriggerSelector.SetValue(PySpin.TriggerSelector_FrameStart) # require trigger for each frame
        else:
            cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
        # optionally send exposure active signal on Line 2 (the white wire)
        cam.LineSelector.SetValue(PySpin.LineSelector_Line1)
        cam.LineMode.SetValue(PySpin.LineMode_Output) 
        cam.LineSource.SetValue(PySpin.LineSource_ExposureActive) #route desired output to Line 1 (try Counter0Active or ExposureActive)
        #cam.LineSelector.SetValue(PySpin.LineSelector_Line2)
        #cam.V3_3Enable.SetValue(True) #enable 3.3V rail on Line 2 (red wire) to act as a pull up for ExposureActive - this does not seem to be necessary as long as a pull up resistor is installed between the physical lines, and actually degrades signal quality 
        print('Camera {} initiated'.format(parameters_dict['CAMERA_IDX']))
    
def saveImage(imageWriteQueue, writer):
    """
    Function to save video frames from the queue in a separate process

    Parameters
    ----------
    imageWriteQueue : queue.Queue()
        Queue that countains the images to be written to disk.
    writer : skvideo.io.FFmpegWriter() instance
        Writer with pointer to the file.
    Returns
    -------
    None.

    """
    
    while True:
        dequeuedImage = imageWriteQueue.get()
        if dequeuedImage is None:
            break
        else:
            writer.writeFrame(dequeuedImage) #call to ffmpeg
            imageWriteQueue.task_done()
                      
def camCapture(camQueue,frameTimeQueue,commQueue_, cam, k,max_frames = 100000, cam_timeout = 100): 
    """
    Function to capture images and timestamps, convert to numpy, send to queue, and release from buffer in separate process

    Parameters
    ----------
    camQueue : queue.Queue()
        Queue that countains the images read from the camera.
    frameTimeQueue : queue.Queue()
        Queue that countains the timestamps read from the camera.
    cam : PySpin camera instance (PySpin.System.GetInstance().GetCameras())
        camera handle
    k : int
        current frame number 
    max_frames : int
        After this amount of expected frames, the acquisition will stop. The default is 100000.
    cam_timeout : float, optional
        Time to wait for the next frame from the camera in seconds (blocking). The default is .5.

    Returns
    -------
    None.

    """
    command = None
    while True:
        if not commQueue_.empty():
            command = commQueue_.get()
        if k == 0: #wait infinitely for trigger for first image
            while True: 
                try:
                    image = cam.GetNextImage(cam_timeout) #get pointer to next image in camera buffer; blocks until image arrives via USB, within infinite timeout for first frame while waiting for DAQ to start sending triggers    
                    break
                except:
                    if not commQueue_.empty():
                        command = commQueue_.get()
                        if command == 'STOP':
                            break
            if command == 'STOP':
                break
        elif k == max_frames or command == 'STOP' :
            print('cam done ')
            break #stop loop and function when expected # frames found
        else:
            try:
                image = cam.GetNextImage(cam_timeout) #get pointer to next image in camera buffer; blocks until image arrives via USB, within CAM_TIMEOUT
            except: #PySpin will throw an exception upon timeout, so end gracefully
                print('Timeout waiting for trigger - end of trial.')
                print(str(k-1) + ' frames captured on image queue')
                camQueue.put([])   #puts an empty list in the queue to end acquisition
                #commQueue_.put('STOP')  # stopping MainLoop
                break
                    
        npImage = np.array(image.GetData(), dtype="uint8").reshape( (image.GetHeight(), image.GetWidth()) ); #convert PySpin ImagePtr into numpy array; use uint8 for Mono8 images, uint16 for Mono16
        frameTimeQueue.put(image.GetTimeStamp()/1000000000)
        camQueue.put(npImage)  
        image.Release() #release from camera buffer
        k = k + 1

def MainLoop(cam,parameters_dict, commQueue, output_handles= None, directoryName=''):
    """
    Main camera loop that initializes a single camera, starts acquisition, 
    displays images and write images to disk.
    The MainLoop is two embedded loops, one for trials and an inner loop
    for frames.

    Parameters
    ----------
    cam : PySpin camera instance (PySpin.System.GetInstance().GetCameras())
        camera handle
    parameters_dict : dictionary
        containing all parameters
    commQueue : queue.Queue()
        Queue that countains commands from the main program.

    Returns
    -------
    None.

    """
    if parameters_dict['SAVE_MOVIE']:
        with open(os.path.join(directoryName,'camera_parameters.json'), 'w') as outfile:
            json.dump(parameters_dict , outfile, indent=4)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # initialize UDP connection
    initCam(cam,parameters_dict)
    end_acquisition = False 
    trial_num = -1
    while not end_acquisition: # iterate over trials
        trial_num += 1
        movieName = os.path.join(directoryName, 
                                 'trial_{}_{}.mp4'.format(str(trial_num).zfill(5),
                                                          datetime.now().strftime("_%Y-%m-%d_%H-%M-%S")))
        if parameters_dict['SAVE_MOVIE']:
            # setup output video file parameters (can try H265 in future for better compression):  
            # for some reason FFMPEG takes exponentially longer to write at nonstandard frame rates, so just use default 25fps and change elsewhere if needed
            crfOut = 22 #controls tradeoff between quality and storage, see https://trac.ffmpeg.org/wiki/Encode/H.264 
            ffmpegThreads = 6 #this controls tradeoff between CPU usage and memory usage; video writes can take a long time if this value is low
            #crfOut = 18 #this should look nearly lossless
            #writer = skvideo.io.FFmpegWriter(movieName, outputdict={'-r': str(FRAME_RATE_OUT), '-vcodec': 'libx264', '-crf': str(crfOut)}) # with frame rate
            writer = skvideo.io.FFmpegWriter(movieName, outputdict={'-vcodec': 'h264_nvenc', '-crf': str(crfOut), '-threads': str(ffmpegThreads)})
            
            
       
        if output_handles ==None:
            #setup tkinter GUI (non-blocking, i.e. without mainloop) to output images to screen quickly
            window = tk.Tk()
            window.title("{} camera - {} acquisif parameters_dict['SAVE_MOVIE']:ition".format(parameters_dict['CAMERA_NAME'],parameters_dict['RECORDING_MODE']))
            geomStrWidth = str(parameters_dict['IMAGE_WIDTH'] + 25)
            geomStrHeight = str(parameters_dict['IMAGE_HEIGHT']+ 35)
            window.geometry(geomStrWidth + 'x' + geomStrHeight) # 2x width+25 x height+35; large enough for frames from 2 cameras + text
            #textlbl = tk.Label(window, text="elapsed time: ")
            textlbl = tk.Label(window, text="waiting for trigger...")
            textlbl.grid(column=0, row=0)
            imglabel = tk.Label(window) # make Label widget to hold image
            imglabel.place(x=10, y=20) #pixels from top-left
            window.update() #update TCL tasks to make window appear
        else:
            if parameters_dict['SAVE_MOVIE']:
                output_handles['filename_label'].setText(movieName)
            else:
                output_handles['filename_label'].setText('NOT RECORDING')
        
       
        
        camQueue = queue.Queue()  #queue to pass images from separate cam1 acquisition thread
        frameTimeQueue = queue.Queue()
        commQueue_ = queue.Queue()
        # setup separate threads to accelerate image acquisition and saving, and start immediately:
        imageWriteQueue = queue.Queue() #queue to pass images captures to separate compress and save thread
        if parameters_dict['SAVE_MOVIE']:
            
            saveThread = threading.Thread(target=saveImage, args=(imageWriteQueue, writer,))
            saveThread.start()  
        
        frame_i = 0
        camThread = threading.Thread(target=camCapture, args=(camQueue,
                                                              frameTimeQueue, 
                                                              commQueue_, 
                                                              cam, 
                                                              frame_i, 
                                                              parameters_dict['MAX_FRAME_NUM'],
                                                              parameters_dict['CAM_TIMEOUT'],))
        cam.BeginAcquisition()
        camThread.start()
        command = None
        framerate_i_last = 0
        framerate_t_last = 0
        framerate = 0
        t_now = 0
        tStart = t_now
        tStart_pc = t_now
        frame_times = []
        bpod_message_sent = False
        logtext = 'Camera {} waiting for frame triggers'.format( parameters_dict['CAMERA_IDX'])
        output_handles['signal_communicate'].log_message.emit(logtext)
        for frame_i in range(parameters_dict['MAX_FRAME_NUM']): # main acquisition loop - iterate over frames
            while camQueue.empty() and commQueue.empty() and commQueue_.empty(): #wait until ready in a loop
                time.sleep(parameters_dict['WAIT_TIME'])
            if not commQueue.empty(): # commands from main window - this can stop the outer loop
                command = commQueue.get()
                if command == 'STOP':
                    end_acquisition = True
# =============================================================================
#             if not commQueue_.empty(): # commands from camera thread
#                 command = commQueue_.get()
#                 print('STOPPED')
# =============================================================================
            if frame_i == parameters_dict['MAX_FRAME_NUM'] or command == 'STOP':
                print('Complete ' + str(frame_i+1) + ' frames captured')
                break
            
            dequeuedAcq = camQueue.get() # get images formated as numpy from separate process queues as soon as they are both ready
            if len(dequeuedAcq) == 0:
                print('Complete ' + str(frame_i+1) + ' frames captured')
                break
                
            frameTime = frameTimeQueue.get() 
            
            t_now = frameTime
            if frame_i == 0:
                tStart = t_now
                tStart_pc = datetime.now()
                tLastFrame = tStart
                logtext = 'Camera {} capture begins'.format( parameters_dict['CAMERA_IDX'])
                output_handles['signal_communicate'].log_message.emit(logtext)
                #print('Capture begins')
            elif not bpod_message_sent and frame_i > 1+100*parameters_dict['CAMERA_IDX'] and parameters_dict['SAVE_MOVIE'] and not output_handles ==  None:
                sock.sendto(bytes(movieName, "utf-8"), output_handles['bpod_address']) # send bpod the filename before finalizing on disk
                bpod_message_sent = True
            
            if parameters_dict['SAVE_MOVIE']:
                imageWriteQueue.put(dequeuedAcq) #put next combined image in saving queue
                frame_times.append(frameTime-tStart)
            if (frame_i+1)%100 == 0: # calculate framerate every 100 frames
                framerate = round((frame_i-framerate_i_last)/(t_now-framerate_t_last),2)
                framerate_i_last = frame_i
                framerate_t_last = frameTime
                
            if t_now - tLastFrame >.03: #update screen every 30 ms
                if output_handles == None:
                    textlbl.configure(text="frame #: {} @ {} HZ".format(frame_i+1,framerate) )
                    I = ImageTk.PhotoImage(Image.fromarray(dequeuedAcq))
                    imglabel.configure(image=I)
                    imglabel.image = I #keep reference to image
                    window.update() #update on screen (this must be called from main thread)
                else:
                    downsampled_image = dequeuedAcq[::parameters_dict['DISPLAY_DOWNSAMPLE'],::parameters_dict['DISPLAY_DOWNSAMPLE']]
                    dequeuedAcq_qt = np.require(downsampled_image, np.uint8, 'C')
                    im = QImage(dequeuedAcq_qt,dequeuedAcq_qt.shape[1],dequeuedAcq_qt.shape[0],QImage.Format_Grayscale8)
                    px = QPixmap(im)
                    text = "frame #: {} @ {} HZ - queue: {}".format(str(frame_i+1).zfill(6),str(framerate).zfill(5),imageWriteQueue.qsize())
# =============================================================================
#                     output_handles['display'].setPixmap(px)
#                     output_handles['status_label'].setText(text)
# =============================================================================
                    output_handles['signal_communicate'].data_to_display.emit(px,text, parameters_dict['CAMERA_IDX'])
                tLastFrame = frameTime
                
                          
        commQueue_.put('STOP')#stop acquisition queue
        
        cam.EndAcquisition() 
        if output_handles ==None:
            textlbl.configure(text='Capture complete, still writing to disk...') 
            window.update()
        #print('Capture ended')
        logtext = 'Camera {} capture ended. {} frames captured.'.format( parameters_dict['CAMERA_IDX'],frame_i)
        output_handles['signal_communicate'].log_message.emit(logtext)
        #   print('calculated frame rate: {:.2f}FPS'.format(numImages/(t2 - t1)))
        if parameters_dict['SAVE_MOVIE'] and frame_i>0: # save files only if there are frames to write
            
            imageWriteQueue.join() #wait until compression and saving queue is done writing to disk
            writer.close() #close to FFMPEG writer
            #print('File written')
            logtext = 'Camera {} file written to disk'.format( parameters_dict['CAMERA_IDX'])
            output_handles['signal_communicate'].log_message.emit(logtext)
            frametime_json_file = movieName[:movieName.find('.')]+'.json'   
            frame_times_dict = {'pc_movie_start_time':str(tStart_pc),
                                'camera_movie_start_time':tStart,
                                'frame_times':frame_times}
            with open(frametime_json_file, 'w') as outfile:
                json.dump(frame_times_dict , outfile, indent=4)
    if output_handles ==None:
        window.destroy() 
    else:
        output_handles['start_button'].setText('Start')
        #%
    # delete all pointers/variable/etc:
    
