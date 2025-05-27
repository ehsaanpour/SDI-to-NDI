import os
import sys

# SDK Paths
DECKLINK_SDK_PATH = r"D:\Program Files\SDI\Blackmagic DeckLink SDK 14.4"
NDI_SDK_PATH = r"D:\Program Files\NDI\NDI 6 SDK"
NDI_LIB_PATH = os.path.join(NDI_SDK_PATH, "Lib", "x64", "Processing.NDI.Lib.x64.lib")

# DeckLink interface identifiers
DECKLINK_IID = {
    'IDeckLink': "{C418FBDD-0587-48ED-8FE5-640F0A14AF91}",
    'IDeckLinkInput': "{89C2E016-C7AB-4062-B33C-32BF40A3BF76}",
    'IDeckLinkOutput': "{CC5B7940-838F-4E32-8D0C-352861509567}", # Added IDeckLinkOutput
    'IDeckLinkVideoInputFrame': "{6F1EE085-F441-4E04-A839-F7B35861744A}"
}

# Video mode constants (from DeckLinkAPI_h.h)
DECKLINK_MODE = {
    'bmdModeHD1080p60': 0x6000000000000017,
    'bmdModeHD1080p59_94': 0x6000000000000016,
    'bmdModeHD1080p50': 0x6000000000000015,
    'bmdFormat8BitYUV': 0x32595559,  # '2YUY' in hex
    'bmdVideoInputFlagDefault': 0x00000000,
    'width': 1920,
    'height': 1080
}

# NDI configuration
NDI_OUTPUT_NAME = "SDI-NDI Converter"
NDI_INPUT_NAME = "NDI-SDI Converter Input" # Default name for NDI receiver
NDI_FRAME_RATE = 60000/1001  # 59.94 fps
