import os
import sys
import cv2
import numpy as np
import ctypes
import logging
import traceback
import time # Import time for sleep
from PyQt6.QtCore import QThread, pyqtSignal, QWaitCondition, QMutex
from PyQt6.QtGui import QImage, QPixmap

try:
    from .config import NDI_SDK_PATH, NDI_LIB_PATH, NDI_INPUT_NAME
except ImportError:
    from config import NDI_SDK_PATH, NDI_LIB_PATH, NDI_INPUT_NAME

# Configure logging (if not already configured by main app)
if not logging.getLogger().handlers:
    logging.basicConfig(filename='app_errors.log', level=logging.ERROR, 
                        format='%(asctime)s - %(levelname)s - %(message)s')

# Load NDI library
ndi_lib = None # Initialize to None
try:
    dll_path = os.path.join(NDI_SDK_PATH, "Bin", "x64", "Processing.NDI.Lib.x64.dll")
    if not os.path.exists(dll_path):
        raise FileNotFoundError(f"NDI DLL not found at: {dll_path}")
    
    logging.info(f"Attempting to load NDI library from: {dll_path}")
    ndi_lib = ctypes.CDLL(dll_path)
    logging.info("NDI library loaded successfully")
except Exception as e:
    error_msg = f"Error loading NDI library in NDIInput: {e}\n{traceback.format_exc()}"
    logging.error(error_msg)
    # The application will handle ndi_lib being None if initialization fails

# NDI video frame structure (re-using from NDIOutput for consistency)
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

# NDI source structure for discovery
class NDIlib_source_t(ctypes.Structure):
    _fields_ = [
        ("p_ndi_name", ctypes.c_char_p),
        ("p_url_address", ctypes.c_char_p)
    ]

# NDI find create structure
class NDIlib_find_create_t(ctypes.Structure):
    _fields_ = [
        ("show_local_sources", ctypes.c_bool),
        ("p_groups", ctypes.c_char_p),
        ("p_extra_ips", ctypes.c_char_p)
    ]

# NDI receiver create structure
class NDIlib_recv_create_v2_t(ctypes.Structure):
    _fields_ = [
        ("p_ndi_name", ctypes.c_char_p),
        ("p_groups", ctypes.c_char_p),
        ("p_extra_ips", ctypes.c_char_p),
        ("color_format", ctypes.c_int),
        ("bandwidth", ctypes.c_int),
        ("allow_video_fields", ctypes.c_bool)
    ]

# NDI constants (from NDI SDK)
NDIlib_recv_color_format_BGRX_BGRA = 101
NDIlib_recv_bandwidth_highest = 0
NDIlib_frame_type_video = 1
NDIlib_frame_type_error = 4

# NDI find functions prototypes
ndi_lib.NDIlib_find_create2.argtypes = [ctypes.POINTER(NDIlib_find_create_t)]
ndi_lib.NDIlib_find_create2.restype = ctypes.c_void_p

ndi_lib.NDIlib_recv_create_v2.argtypes = [ctypes.POINTER(NDIlib_recv_create_v2_t)]
ndi_lib.NDIlib_recv_create_v2.restype = ctypes.c_void_p

ndi_lib.NDIlib_recv_capture_v2.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIVideoFrame), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
ndi_lib.NDIlib_recv_capture_v2.restype = ctypes.c_int

ndi_lib.NDIlib_recv_free_video_v2.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIVideoFrame)]
ndi_lib.NDIlib_recv_free_video_v2.restype = None

ndi_lib.NDIlib_recv_destroy.argtypes = [ctypes.c_void_p]
ndi_lib.NDIlib_recv_destroy.restype = None

ndi_lib.NDIlib_initialize.argtypes = []
ndi_lib.NDIlib_initialize.restype = ctypes.c_bool

ndi_lib.NDIlib_find_destroy.argtypes = [ctypes.c_void_p]
ndi_lib.NDIlib_find_destroy.restype = None

ndi_lib.NDIlib_find_wait_for_sources.argtypes = [ctypes.c_void_p, ctypes.c_int]
ndi_lib.NDIlib_find_wait_for_sources.restype = ctypes.c_bool

ndi_lib.NDIlib_find_get_current_sources.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
ndi_lib.NDIlib_find_get_current_sources.restype = ctypes.POINTER(NDIlib_source_t)

# Add missing function prototypes
ndi_lib.NDIlib_recv_connect.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIlib_source_t)]
ndi_lib.NDIlib_recv_connect.restype = ctypes.c_bool

# Remove prototype definitions for functions causing AttributeError
# ndi_lib.NDIlib_recv_queue.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIVideoFrame)]
# ndi_lib.NDIlib_recv_queue.restype = ctypes.c_bool

# ndi_lib.NDIlib_recv_get_queue.argtypes = [ctypes.c_void_p]
# ndi_lib.NDIlib_recv_get_queue.restype = ctypes.c_int

# ndi_lib.NDIlib_recv_clear.argtypes = [ctypes.c_void_p]
# ndi_lib.NDIlib_recv_clear.restype = None

# Add missing constants
NDIlib_recv_color_format_RGBX_RGBA = 100
NDIlib_recv_color_format_BGRX_BGRA = 101
NDIlib_recv_color_format_RGBX_RGBA_Flipped = 200
NDIlib_recv_color_format_BGRX_BGRA_Flipped = 201

NDIlib_recv_bandwidth_highest = 0
NDIlib_recv_bandwidth_lowest = 100

NDIlib_frame_type_none = 0
NDIlib_frame_type_video = 1
NDIlib_frame_type_audio = 2
NDIlib_frame_type_metadata = 3
NDIlib_frame_type_error = 4

class NDIInput(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, ndi_source_name=None): # Added ndi_source_name parameter
        super().__init__()
        self.receiver = None
        self.is_running = False
        self.wait_condition = QWaitCondition()
        self.mutex = QMutex()
        self.ndi_source_name = ndi_source_name # Store the selected source name
        try:
            self._initialize_ndi()
        except Exception as e:
            error_msg = f"NDIInput initialization error: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            self.error_occurred.emit(f"NDIInput init failed. Check 'app_errors.log'.")
    
    def _initialize_ndi(self):
        """Initialize NDI receiver"""
        try:
            # Initialize NDI
            logging.info("Calling NDIlib_initialize()...")
            if not ndi_lib.NDIlib_initialize():
                logging.error("NDIlib_initialize() failed!")
                raise RuntimeError("Failed to initialize NDI")
            logging.info("NDIlib_initialize() succeeded.")
            
            # Create receiver description
            recv_create_desc = NDIlib_recv_create_v2_t()
            recv_create_desc.color_format = NDIlib_recv_color_format_BGRX_BGRA
            recv_create_desc.bandwidth = NDIlib_recv_bandwidth_highest
            recv_create_desc.allow_video_fields = True
            recv_create_desc.p_groups = None
            recv_create_desc.p_extra_ips = None
            
            # Use the provided NDI source name, or default from config if not provided
            source_name_to_use = self.ndi_source_name if self.ndi_source_name else NDI_INPUT_NAME
            logging.info(f"NDIInput: Using source name: {source_name_to_use}")
            recv_create_desc.p_ndi_name = source_name_to_use.encode('utf-8')

            # Create NDI receiver
            logging.info("Calling NDIlib_recv_create_v2()...")
            self.receiver = ndi_lib.NDIlib_recv_create_v2(ctypes.byref(recv_create_desc))
            if not self.receiver:
                logging.error(f"NDIlib_recv_create_v2 failed for source: {source_name_to_use}")
                raise RuntimeError(f"Failed to create NDI receiver for source: {source_name_to_use}")
            logging.info("NDIlib_recv_create_v2 succeeded.")
            
            # Create source structure for connection
            source = NDIlib_source_t()
            source.p_ndi_name = source_name_to_use.encode('utf-8')
            source.p_url_address = None
            logging.info(f"NDIInput: Connecting to source: {source_name_to_use}")
            
            # Connect to the source
            result = ndi_lib.NDIlib_recv_connect(self.receiver, ctypes.byref(source))
            if not result:
                logging.error(f"NDIlib_recv_connect failed for source: {source_name_to_use}")
                raise RuntimeError(f"Failed to connect to NDI source: {source_name_to_use}")
            logging.info(f"Successfully connected to NDI source: {source_name_to_use}")
        except Exception as e:
            error_msg = f"NDI receiver initialization in NDIInput failed: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            print(error_msg)
            self.error_occurred.emit(f"NDI receiver init failed: {e}")
            self.receiver = None
    
    def run(self):
        """Main loop for receiving NDI frames"""
        if not self.receiver:
            self.error_occurred.emit("NDI receiver not initialized")
            return
            
        self.is_running = True
        video_frame = NDIVideoFrame()
        
        while self.is_running:
            # Wait for a frame
            t = ndi_lib.NDIlib_recv_capture_v2(
                self.receiver,
                ctypes.byref(video_frame),
                None, # audio_frame
                None, # metadata_frame
                1000 # timeout_ms
            )
            
            if t == NDIlib_frame_type_video:
                if video_frame.p_data:
                    try:
                        # Convert NDI frame to numpy array (BGRA)
                        frame_data = ctypes.cast(video_frame.p_data, ctypes.POINTER(ctypes.c_ubyte * (video_frame.yres * video_frame.line_stride_in_bytes)))
                        np_frame = np.frombuffer(frame_data.contents, dtype=np.uint8)
                        
                        # Reshape to BGRA
                        bgra_frame = np_frame.reshape((video_frame.yres, video_frame.xres, 4))
                        
                        # Convert BGRA to BGR for consistency with other modules
                        bgr_frame = cv2.cvtColor(bgra_frame, cv2.COLOR_BGRA2BGR)
                        
                        self.frame_ready.emit(bgr_frame)
                        
                    except Exception as e:
                        self.error_occurred.emit(f"Error processing NDI frame: {e}")
                    finally:
                        ndi_lib.NDIlib_recv_free_video_v2(self.receiver, ctypes.byref(video_frame))
            
            elif t == NDIlib_frame_type_error:
                self.error_occurred.emit("NDI receiver error")
                break
            
            # Add a small sleep to prevent busy-waiting if no frames are coming
            self.msleep(1)
            
        self.is_running = False
        
    def start(self):
        """Start receiving NDI frames"""
        if not self.receiver:
            self.error_occurred.emit("NDI receiver not initialized")
            return False
        
        if not self.isRunning():
            super().start()
            self.is_running = True
            return True
        return False
    
    def stop(self):
        """Stop receiving NDI frames"""
        self.is_running = False
        if self.isRunning():
            self.wait() # Wait for the thread to finish

    def __del__(self):
        """Cleanup NDI resources"""
        if self.receiver:
            ndi_lib.NDIlib_recv_destroy(self.receiver)
            self.receiver = None
        # NDIlib_destroy() should be called once at application exit, not per object

    @staticmethod
    def list_sources():
        """List available NDI sources"""
        try:
            logging.info("Starting NDI source discovery...")
            
            # Create find instance
            find_create = NDIlib_find_create_t()
            find_create.show_local_sources = True
            find_create.p_groups = None
            find_create.p_extra_ips = None

            logging.info("Creating NDI find instance...")
            find_instance = ndi_lib.NDIlib_find_create2(ctypes.byref(find_create))
            if not find_instance:
                logging.error("Failed to create NDI find instance")
                return []

            logging.info("Waiting for sources to be discovered...")
            time.sleep(2)  # Give time for discovery

            # Get current sources
            num_sources = ctypes.c_int(0)
            logging.info("Getting current sources...")
            sources = ndi_lib.NDIlib_find_get_current_sources(find_instance, ctypes.byref(num_sources))
            
            if not sources:
                logging.warning("No sources returned from NDIlib_find_get_current_sources")
                ndi_lib.NDIlib_find_destroy(find_instance)
                return []

            logging.info(f"Found {num_sources.value} NDI sources")
            source_list = []
            for i in range(num_sources.value):
                source = sources[i]
                source_name = source.p_ndi_name.decode('utf-8') if source.p_ndi_name else "Unknown"
                source_url = source.p_url_address.decode('utf-8') if source.p_url_address else "Unknown"
                logging.info(f"Source {i + 1}: {source_name} ({source_url})")
                source_list.append(source_name)

            # Cleanup
            logging.info("Cleaning up NDI find instance...")
            ndi_lib.NDIlib_find_destroy(find_instance)
            return source_list

        except Exception as e:
            error_msg = f"Error listing NDI sources: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            return []
