import sys
import time
import ctypes
from ctypes import *
import os

# Get the absolute path to the NDI DLL
current_dir = os.path.dirname(os.path.abspath(__file__))
ndi_dll_path = os.path.join(current_dir, "lib", "Processing.NDI.Lib.x64.dll")
print(f"Looking for NDI DLL at: {ndi_dll_path}")

# Load the NDI library
try:
    ndi_lib = ctypes.CDLL(ndi_dll_path)
    print("Successfully loaded NDI library")
except Exception as e:
    print(f"Failed to load NDI library: {e}")
    sys.exit(1)

# Define NDI structures
class NDIlib_find_create_t(Structure):
    _fields_ = [
        ("show_local_sources", c_bool),
        ("p_groups", c_char_p),
        ("p_extra_ips", c_char_p),
    ]

class NDIlib_source_t(Structure):
    _fields_ = [
        ("p_ndi_name", c_char_p),
        ("p_url_address", c_char_p),
    ]

# Define function signatures
ndi_lib.NDIlib_initialize.restype = c_bool
ndi_lib.NDIlib_find_create2.restype = c_void_p
ndi_lib.NDIlib_find_get_current_sources.restype = POINTER(NDIlib_source_t)
ndi_lib.NDIlib_find_get_current_sources.argtypes = [c_void_p, c_void_p]
ndi_lib.NDIlib_find_destroy.argtypes = [c_void_p]

# Initialize NDI
print("Initializing NDI...")
if not ndi_lib.NDIlib_initialize():
    print("Failed to initialize NDI")
    sys.exit(1)
print("NDI initialized successfully")

# Create find instance
find_create = NDIlib_find_create_t()
find_create.show_local_sources = True
find_create.p_groups = None
find_create.p_extra_ips = None

print("Creating NDI find instance...")
find_instance = ndi_lib.NDIlib_find_create2(byref(find_create))
if not find_instance:
    print("Failed to create NDI find instance")
    sys.exit(1)
print("NDI find instance created successfully")

# Wait for sources to be discovered
print("Waiting for sources to be discovered...")
time.sleep(5)  # Give more time for discovery

# Get current sources
num_sources = c_int(0)
sources = ndi_lib.NDIlib_find_get_current_sources(find_instance, byref(num_sources))

print(f"\nFound {num_sources.value} NDI sources:")
for i in range(num_sources.value):
    source = sources[i]
    print(f"Source {i + 1}:")
    print(f"  Name: {source.p_ndi_name.decode('utf-8') if source.p_ndi_name else 'None'}")
    print(f"  URL: {source.p_url_address.decode('utf-8') if source.p_url_address else 'None'}")

# Cleanup
ndi_lib.NDIlib_find_destroy(find_instance)
ndi_lib.NDIlib_destroy()

print("NDI discovery test finished.")
sys.exit(0) 