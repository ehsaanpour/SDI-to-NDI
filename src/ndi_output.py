import os
import sys
import cv2
import numpy as np
import ctypes
from PyQt6.QtCore import QObject, pyqtSignal
try:
    from .config import NDI_SDK_PATH, NDI_LIB_PATH, NDI_OUTPUT_NAME
except ImportError:
    from config import NDI_SDK_PATH, NDI_LIB_PATH, NDI_OUTPUT_NAME

# Load NDI library
try:
    ndi_lib = ctypes.CDLL(os.path.join(NDI_SDK_PATH, "Bin", "x64", "Processing.NDI.Lib.x64.dll"))
except Exception as e:
    print(f"Error loading NDI library: {e}")
    sys.exit(1)

# NDI video frame structure
class NDIVideoFrame(ctypes.Structure):
    _fields_ = [
        ("xres", ctypes.c_int),
        ("yres", ctypes.c_int),
        ("FourCC", ctypes.c_int),
        ("frame_rate_N", ctypes.c_int),
        ("frame_rate_D", ctypes.c_int),
        ("picture_aspect_ratio", ctypes.c_float),
        ("frame_format_type", ctypes.c_int),
        ("timecode", ctypes.c_longlong),
        ("p_data", ctypes.POINTER(ctypes.c_ubyte)),
        ("line_stride_in_bytes", ctypes.c_int),
        ("p_metadata", ctypes.c_char_p),
        ("timestamp", ctypes.c_longlong)
    ]

class NDIOutput(QObject):
    error_occurred = pyqtSignal(str)
    
import logging
import traceback

try:
    from .config import NDI_SDK_PATH, NDI_LIB_PATH, NDI_OUTPUT_NAME
except ImportError:
    from config import NDI_SDK_PATH, NDI_LIB_PATH, NDI_OUTPUT_NAME

# Load NDI library
try:
    ndi_lib = ctypes.CDLL(os.path.join(NDI_SDK_PATH, "Bin", "x64", "Processing.NDI.Lib.x64.dll"))
    logging.info("NDI library loaded successfully in NDIOutput.")
except Exception as e:
    error_msg = f"Error loading NDI library in NDIOutput: {e}\n{traceback.format_exc()}"
    logging.error(error_msg)
    sys.exit(1)

# NDI video frame structure
class NDIVideoFrame(ctypes.Structure):
    _fields_ = [
        ("xres", ctypes.c_int),
        ("yres", ctypes.c_int),
        ("FourCC", ctypes.c_int),
        ("frame_rate_N", ctypes.c_int),
        ("frame_rate_D", ctypes.c_int),
        ("picture_aspect_ratio", ctypes.c_float),
        ("frame_format_type", ctypes.c_int),
        ("timecode", ctypes.c_longlong),
        ("p_data", ctypes.POINTER(ctypes.c_ubyte)),
        ("line_stride_in_bytes", ctypes.c_int),
        ("p_metadata", ctypes.c_char_p),
        ("timestamp", ctypes.c_longlong)
    ]

class NDIOutput(QObject):
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.sender = None
        self.is_running = False
        try:
            self._initialize_ndi()
        except Exception as e:
            error_msg = f"NDIOutput initialization error: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            self.error_occurred.emit(f"NDIOutput init failed. Check 'app_errors.log'.")
    
    def _initialize_ndi(self):
        """Initialize NDI sender"""
        try:
            # Initialize NDI
            if not ndi_lib.NDIlib_initialize():
                raise RuntimeError("Failed to initialize NDI")
            
            # Create sender description
            sender_desc = ndi_lib.NDIlib_send_create_t()
            sender_desc.p_ndi_name = NDI_OUTPUT_NAME.encode('utf-8')
            sender_desc.p_groups = None
            sender_desc.clock_video = True
            sender_desc.clock_audio = False
            
            # Create NDI sender
            self.sender = ndi_lib.NDIlib_send_create(ctypes.byref(sender_desc))
            
            if not self.sender:
                raise RuntimeError("Failed to create NDI sender")
                
        except Exception as e:
            error_msg = f"NDI sender initialization in NDIOutput failed: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            self.error_occurred.emit(f"NDI sender init failed: {e}")
            self.sender = None
    
    def start(self):
        """Start NDI output"""
        if not self.sender:
            self.error_occurred.emit("NDI not initialized")
            return False
        
        self.is_running = True
        return True
    
    def stop(self):
        """Stop NDI output"""
        self.is_running = False
        if self.sender:
            ndi_lib.NDIlib_send_destroy(self.sender)
            self.sender = None
    
    def send_frame(self, frame):
        """Send a frame through NDI"""
        if not self.is_running or frame is None or self.sender is None:
            return False
        
        try:
            # Convert BGR to BGRA
            bgra = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
            
            # Create NDI video frame
            video_frame = NDIVideoFrame()
            video_frame.xres = frame.shape[1]
            video_frame.yres = frame.shape[0]
            video_frame.FourCC = ndi_lib.NDIlib_FourCC_type_BGRA
            video_frame.frame_rate_N = 60000
            video_frame.frame_rate_D = 1001  # ~59.94 fps
            video_frame.picture_aspect_ratio = float(frame.shape[1]) / frame.shape[0]
            video_frame.frame_format_type = ndi_lib.NDIlib_frame_format_type_progressive
            video_frame.timecode = ndi_lib.NDIlib_send_timecode_synthesize
            video_frame.p_data = bgra.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
            video_frame.line_stride_in_bytes = frame.strides[0]
            video_frame.p_metadata = None
            
            # Send the frame
            ndi_lib.NDIlib_send_send_video_v2(self.sender, ctypes.byref(video_frame))
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Error sending NDI frame: {e}")
            return False
    
    def __del__(self):
        """Cleanup NDI resources"""
        self.stop()
        ndi_lib.NDIlib_destroy()
