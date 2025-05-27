import os
import sys
import cv2
import numpy as np
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal, QWaitCondition, QMutex
from PyQt6.QtGui import QImage, QPixmap

try:
    from .config import NDI_SDK_PATH, NDI_LIB_PATH, NDI_INPUT_NAME
except ImportError:
    from config import NDI_SDK_PATH, NDI_LIB_PATH, NDI_INPUT_NAME

# Load NDI library
try:
    ndi_lib = ctypes.CDLL(os.path.join(NDI_SDK_PATH, "Bin", "x64", "Processing.NDI.Lib.x64.dll"))
except Exception as e:
    print(f"Error loading NDI library: {e}")
    sys.exit(1)

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
        ("show_local_sources", ctypes.c_bool)
    ]

# NDI find functions prototypes
ndi_lib.NDIlib_find_create_v2.argtypes = [ctypes.POINTER(NDIlib_find_create_t)]
ndi_lib.NDIlib_find_create_v2.restype = ctypes.c_void_p

ndi_lib.NDIlib_find_destroy.argtypes = [ctypes.c_void_p]
ndi_lib.NDIlib_find_destroy.restype = None

ndi_lib.NDIlib_find_wait_for_sources.argtypes = [ctypes.c_void_p, ctypes.c_int]
ndi_lib.NDIlib_find_wait_for_sources.restype = ctypes.c_bool

ndi_lib.NDIlib_find_get_current_sources.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(NDIlib_source_t)), ctypes.POINTER(ctypes.c_uint)]
ndi_lib.NDIlib_find_get_current_sources.restype = None

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
            if not ndi_lib.NDIlib_initialize():
                raise RuntimeError("Failed to initialize NDI")
            
            # Create receiver description
            recv_create_desc = ndi_lib.NDIlib_recv_create_v2_t()
            recv_create_desc.color_format = ndi_lib.NDIlib_recv_color_format_BGRX_BGRA
            recv_create_desc.bandwidth = ndi_lib.NDIlib_recv_bandwidth_highest
            recv_create_desc.allow_video_fields = True
            
            # Use the provided NDI source name, or default from config if not provided
            source_name_to_use = self.ndi_source_name if self.ndi_source_name else NDI_INPUT_NAME
            recv_create_desc.p_ndi_name = source_name_to_use.encode('utf-8')

            # Create NDI receiver
            self.receiver = ndi_lib.NDIlib_recv_create_v2(ctypes.byref(recv_create_desc))
            
            if not self.receiver:
                raise RuntimeError(f"Failed to create NDI receiver for source: {source_name_to_use}")
                
            # Connect to a source (this can be done dynamically later)
            # For now, we'll just wait for any source
            
        except Exception as e:
            error_msg = f"NDI receiver initialization in NDIInput failed: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
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
            
            if t == ndi_lib.NDIlib_frame_type_video:
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
            
            elif t == ndi_lib.NDIlib_frame_type_error:
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
        sources = []
        finder = None
        try:
            # Initialize NDI (idempotent)
            if not ndi_lib.NDIlib_initialize():
                logging.error("Failed to initialize NDI for source discovery.")
                return []

            find_create_desc = NDIlib_find_create_t()
            find_create_desc.show_local_sources = True
            finder = ndi_lib.NDIlib_find_create_v2(ctypes.byref(find_create_desc))
            if not finder:
                logging.error("Failed to create NDI finder. NDIlib_find_create_v2 returned NULL.")
                return []

            # Wait for sources to appear (optional, but good for initial discovery)
            # Wait up to 5 seconds for sources to appear
            if not ndi_lib.NDIlib_find_wait_for_sources(finder, 5000): # Increased timeout to 5 seconds
                logging.info("No new NDI sources found within timeout during discovery (5s).")
            
            p_sources = ctypes.POINTER(NDIlib_source_t)()
            num_sources = ctypes.c_uint(0)
            
            ndi_lib.NDIlib_find_get_current_sources(finder, ctypes.byref(p_sources), ctypes.byref(num_sources))
            
            for i in range(num_sources.value):
                source = p_sources[i]
                if source.p_ndi_name:
                    sources.append(source.p_ndi_name.decode('utf-8'))
            
            # Removed ndi_lib.NDIlib_find_free_sources(finder, p_sources)
            # as it seems not to be available or necessary with NDIlib_find_destroy

        except Exception as e:
            logging.error(f"Error listing NDI sources: {e}\n{traceback.format_exc()}")
        finally:
            if finder:
                ndi_lib.NDIlib_find_destroy(finder)
            # NDIlib_destroy() is handled globally in app.py
        return sources
