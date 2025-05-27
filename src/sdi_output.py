import os
import sys
import cv2
import numpy as np
import ctypes
import comtypes
import comtypes.client
from PyQt6.QtCore import QObject, pyqtSignal

# COM constants
S_OK = 0x00000000
E_FAIL = 0x80004005
CLSCTX_ALL = 0x17

try:
    from .config import DECKLINK_SDK_PATH, DECKLINK_IID, DECKLINK_MODE
except ImportError:
    from config import DECKLINK_SDK_PATH, DECKLINK_IID, DECKLINK_MODE

class SDIOutput(QObject):
    error_occurred = pyqtSignal(str)
    
import logging
import traceback

import logging
import traceback

# COM constants
S_OK = 0x00000000
E_FAIL = 0x80004005
CLSCTX_ALL = 0x17

try:
    from .config import DECKLINK_SDK_PATH, DECKLINK_IID, DECKLINK_MODE
except ImportError:
    from config import DECKLINK_SDK_PATH, DECKLINK_IID, DECKLINK_MODE

class SDIOutput(QObject):
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.decklink = None
        self.output = None
        self.is_running = False
        try:
            comtypes.CoInitialize()
            logging.info("COM initialized in SDIOutput.")
            self._initialize_decklink()
        except Exception as e:
            error_msg = f"SDIOutput initialization error: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            self.error_occurred.emit(f"SDIOutput init failed. Check 'app_errors.log'.")
    
    def _initialize_decklink(self):
        """Initialize DeckLink device for output"""
        try:
            # Create DeckLink instance
            self.decklink = comtypes.CoCreateInstance(
                DECKLINK_IID['IDeckLink'],
                None,
                comtypes.CLSCTX_ALL,
                DECKLINK_IID['IDeckLink']
            )
            logging.info("DeckLink instance created in SDIOutput.")
            
            if not self.decklink:
                raise RuntimeError("Failed to create DeckLink instance")
            
            # Get output interface
            self.output = self.decklink.QueryInterface(DECKLINK_IID['IDeckLinkOutput'])
            logging.info("DeckLink output interface obtained in SDIOutput.")
            if not self.output:
                raise RuntimeError("Failed to get output interface")
            
            # Set video output mode
            result = self.output.EnableVideoOutput(
                DECKLINK_MODE['bmdModeHD1080p60'],
                DECKLINK_MODE['bmdVideoOutputFlagDefault']
            )
            
            if result != S_OK:
                raise RuntimeError(f"Failed to enable video output: {result}")
            logging.info("Video output enabled in SDIOutput.")
            
        except Exception as e:
            error_msg = f"DeckLink initialization in SDIOutput failed: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            self.error_occurred.emit(f"DeckLink init failed: {e}")
            self.output = None
    
    def start(self):
        """Start SDI output"""
        if not self.output:
            self.error_occurred.emit("DeckLink output not initialized")
            return False
            
        try:
            result = self.output.StartScheduledPlayback(0, 100, 1.0) # Start immediately
            if result != S_OK:
                raise RuntimeError(f"Failed to start scheduled playback: {result}")
                
            self.is_running = True
            return True
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            return False
    
    def stop(self):
        """Stop SDI output"""
        self.is_running = False
        if self.output:
            try:
                self.output.StopScheduledPlayback(0)
                self.output.DisableVideoOutput()
            except Exception as e:
                self.error_occurred.emit(f"Error stopping output: {e}")
    
    def send_frame(self, frame):
        """Send a frame through SDI output"""
        if not self.is_running or frame is None or self.output is None:
            return False
        
        try:
            # Convert BGR to YUV (YUY2)
            yuv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_YUY2)
            
            # Allocate frame buffer
            frame_buffer = ctypes.create_string_buffer(yuv_frame.tobytes())
            
            # Create video frame
            video_frame = self.output.CreateVideoFrame(
                DECKLINK_MODE['width'],
                DECKLINK_MODE['height'],
                DECKLINK_MODE['width'] * 2, # line_stride_in_bytes (2 bytes per pixel for YUY2)
                DECKLINK_MODE['bmdFormat8BitYUV'],
                DECKLINK_MODE['bmdFrameFlagDefault']
            )
            
            if not video_frame:
                raise RuntimeError("Failed to create video frame")
            
            # Copy data to frame buffer
            ctypes.memmove(video_frame.GetBytes(), frame_buffer, len(frame_buffer))
            
            # Schedule frame for playback
            result = self.output.ScheduleVideoFrame(video_frame, 0, 100, 1.0)
            if result != S_OK:
                raise RuntimeError(f"Failed to schedule video frame: {result}")
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Error sending SDI frame: {e}")
            return False
    
    def __del__(self):
        """Cleanup resources"""
        self.stop()
        if self.output:
            self.output.Release()
            self.output = None
        if self.decklink:
            self.decklink.Release()
            self.decklink = None
        comtypes.CoUninitialize()
