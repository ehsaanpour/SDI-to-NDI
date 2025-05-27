import os
import sys
import cv2
import numpy as np
import ctypes
import comtypes
import comtypes.client
from PyQt6.QtCore import QThread, pyqtSignal

# COM constants
S_OK = 0x00000000
E_FAIL = 0x80004005
CLSCTX_ALL = 0x17
try:
    from .config import DECKLINK_SDK_PATH, DECKLINK_IID, DECKLINK_MODE
except ImportError:
    from config import DECKLINK_SDK_PATH, DECKLINK_IID, DECKLINK_MODE

class VideoFrameCallback(comtypes.COMObject):
    _com_interfaces_ = ['IDeckLinkVideoInputCallback']
    
    def __init__(self, frame_callback):
        super().__init__()
        self._frame_callback = frame_callback
        
    def VideoInputFrameArrived(self, video_frame, audio_frame):
        if not video_frame:
            return S_OK
            
        try:
            # Get frame data
            frame_bytes = video_frame.GetBytes()
            height = video_frame.GetHeight()
            width = video_frame.GetWidth()
            row_bytes = video_frame.GetRowBytes()
            
            # Convert to numpy array
            frame = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame = frame.reshape((height, width, 2))  # YUY2 format
            
            # Convert YUY2 to BGR
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUY2)
            
            # Call the callback
            self._frame_callback(bgr_frame)
            
        except Exception as e:
            print(f"Error in frame callback: {e}")
            
        return S_OK
        
    def VideoInputFormatChanged(self, notification_events, format_):
        return S_OK

class SDICapture(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)
    
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

class VideoFrameCallback(comtypes.COMObject):
    _com_interfaces_ = ['IDeckLinkVideoInputCallback']
    
    def __init__(self, frame_callback):
        super().__init__()
        self._frame_callback = frame_callback
        
    def VideoInputFrameArrived(self, video_frame, audio_frame):
        if not video_frame:
            return S_OK
            
        try:
            # Get frame data
            frame_bytes = video_frame.GetBytes()
            height = video_frame.GetHeight()
            width = video_frame.GetWidth()
            row_bytes = video_frame.GetRowBytes()
            
            # Convert to numpy array
            frame = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame = frame.reshape((height, width, 2))  # YUY2 format
            
            # Convert YUY2 to BGR
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUY2)
            
            # Call the callback
            self._frame_callback(bgr_frame)
            
        except Exception as e:
            logging.error(f"Error in frame callback: {e}\n{traceback.format_exc()}")
            
        return S_OK
        
    def VideoInputFormatChanged(self, notification_events, format_):
        return S_OK

class SDICapture(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.decklink = None
        self.input = None
        self.callback = None
        self.is_running = False
        try:
            comtypes.CoInitialize()
            self._initialize_decklink()
        except Exception as e:
            error_msg = f"SDICapture initialization error: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            self.error_occurred.emit(f"SDICapture init failed. Check 'app_errors.log'.")
    
    def _initialize_decklink(self):
        """Initialize DeckLink device"""
        try:
            # Create DeckLink instance
            self.decklink = comtypes.CoCreateInstance(
                DECKLINK_IID['IDeckLink'],
                None,
                comtypes.CLSCTX_ALL,
                DECKLINK_IID['IDeckLink']
            )
            
            if not self.decklink:
                raise RuntimeError("Failed to create DeckLink instance")
            
            # Get input interface
            self.input = self.decklink.QueryInterface(DECKLINK_IID['IDeckLinkInput'])
            if not self.input:
                raise RuntimeError("Failed to get input interface")
            
            # Create and set callback
            self.callback = VideoFrameCallback(self._handle_frame)
            result = self.input.SetCallback(self.callback)
            if result != 0:
                raise RuntimeError(f"Failed to set callback: {result}")
            
            # Set video input mode
            result = self.input.EnableVideoInput(
                DECKLINK_MODE['bmdModeHD1080p60'],
                DECKLINK_MODE['bmdFormat8BitYUV'],
                DECKLINK_MODE['bmdVideoInputFlagDefault']
            )
            
            if result != 0:
                raise RuntimeError(f"Failed to enable video input: {result}")
            
        except Exception as e:
            error_msg = f"DeckLink initialization in SDICapture failed: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            self.error_occurred.emit(f"DeckLink init failed: {e}")
            self.input = None
    
    def _handle_frame(self, frame):
        """Handle incoming frames from callback"""
        if self.is_running:
            self.frame_ready.emit(frame)
    
    def start(self):
        """Start capturing"""
        if not self.input:
            self.error_occurred.emit("DeckLink not initialized")
            return False
            
        try:
            result = self.input.StartStreams()
            if result != 0:
                raise RuntimeError(f"Failed to start streams: {result}")
                
            self.is_running = True
            return True
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            return False
    
    def stop(self):
        """Stop capturing"""
        self.is_running = False
        if self.input:
            try:
                self.input.StopStreams()
                self.input.DisableVideoInput()
            except Exception as e:
                self.error_occurred.emit(f"Error stopping capture: {e}")
    
    def __del__(self):
        """Cleanup resources"""
        self.stop()
        if self.input:
            self.input.Release()
            self.input = None
        if self.decklink:
            self.decklink.Release()
            self.decklink = None
        comtypes.CoUninitialize()
