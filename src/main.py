import sys
import logging
import traceback
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox
from PyQt6.QtCore import Qt

# Configure logging
logging.basicConfig(filename='app_errors.log', level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

from .preview_widget import PreviewWidget
from .sdi_capture import SDICapture
from .ndi_output import NDIOutput
from .ndi_input import NDIInput
from .sdi_output import SDIOutput

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SDI/NDI Converter")
        self.setMinimumSize(800, 600)
        
        # Create the main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Add preview widget
        self.preview = PreviewWidget()
        layout.addWidget(self.preview)
        
        # Input/Output selection
        io_layout = QHBoxLayout()
        
        # Input selection
        input_label = QLabel("Input:")
        self.input_selector = QComboBox()
        self.input_selector.addItem("SDI Capture")
        self.input_selector.addItem("NDI Input")
        io_layout.addWidget(input_label)
        io_layout.addWidget(self.input_selector)
        
        # NDI Source selection (initially hidden)
        self.ndi_source_selector = QComboBox()
        self.ndi_source_selector.hide() # Hide by default
        io_layout.addWidget(self.ndi_source_selector)

        # Output selection
        output_label = QLabel("Output:")
        self.output_selector = QComboBox()
        self.output_selector.addItem("NDI Output")
        self.output_selector.addItem("SDI Output")
        io_layout.addWidget(output_label)
        io_layout.addWidget(self.output_selector)
        
        layout.addLayout(io_layout)
        
        # Create control buttons
        controls = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        
        # Initialize status label
        self.status_label = QLabel("Ready")
        controls.addWidget(self.status_label)
        
        layout.addLayout(controls)
        
        # Connect signals
        self.start_button.clicked.connect(self.start_conversion)
        self.stop_button.clicked.connect(self.stop_conversion)
        
        # Initialize capture and output objects (will be instantiated dynamically)
        self.current_input = None
        self.current_output = None
        
        # Initialize all possible input/output modules
        self.sdi_capture = None
        self.ndi_input = None
        self.ndi_output = None
        self.sdi_output = None

        self._initialize_modules() # This will now only initialize SDI and NDIOutput
        self._connect_signals()

        # Connect input selector signal after all widgets are initialized
        self.input_selector.currentIndexChanged.connect(self._on_input_type_changed)
        # Set initial state based on default selection
        self._on_input_type_changed(self.input_selector.currentIndex())
    
    def _initialize_modules(self):
        """Initialize all input/output modules that are not dynamically created"""
        try:
            self.sdi_capture = SDICapture()
            # NDIInput will be initialized dynamically in start_conversion
            self.ndi_input = None 
            self.ndi_output = NDIOutput()
            self.sdi_output = SDIOutput()
        except Exception as e:
            error_msg = f"Module initialization error: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            self.handle_error(f"Module initialization error. Check 'app_errors.log' for details.")
            self.start_button.setEnabled(False)

    def _connect_signals(self):
        """Connect error signals from all modules"""
        if self.sdi_capture:
            self.sdi_capture.error_occurred.connect(self.handle_error)
        # NDIInput error signal will be connected when it's instantiated in start_conversion
        if self.ndi_output:
            self.ndi_output.error_occurred.connect(self.handle_error)
        if self.sdi_output:
            self.sdi_output.error_occurred.connect(self.handle_error)

    def _on_input_type_changed(self, index):
        """Handle changes in the input type selector"""
        input_type = self.input_selector.itemText(index)
        if input_type == "NDI Input":
            self.ndi_source_selector.clear()
            sources = NDIInput.list_sources()
            if sources:
                self.ndi_source_selector.addItems(sources)
                self.ndi_source_selector.show()
            else:
                self.ndi_source_selector.addItem("No NDI sources found")
                self.ndi_source_selector.show()
                logging.warning("No NDI sources found.")
        else:
            self.ndi_source_selector.hide()

    def handle_error(self, error_msg):
        """Handle error messages from components"""
        self.status_label.setText(f"Error: {error_msg}")
        print(f"Error: {error_msg}")  # Also log to console
        logging.error(error_msg) # Log to file as well
        
    def start_conversion(self):
        """Start the conversion process based on selected input/output"""
        self.status_label.setText("Starting...")
        
        # Stop any currently running conversion first
        self.stop_conversion()

        # Determine selected input
        input_type = self.input_selector.currentText()
        if input_type == "SDI Capture":
            self.current_input = self.sdi_capture
        elif input_type == "NDI Input":
            selected_ndi_source = self.ndi_source_selector.currentText()
            if selected_ndi_source == "No NDI sources found":
                self.handle_error("Cannot start NDI input: No NDI sources selected or found.")
                return
            try:
                # Re-instantiate NDIInput with the selected source name
                self.ndi_input = NDIInput(ndi_source_name=selected_ndi_source)
                self.ndi_input.error_occurred.connect(self.handle_error) # Re-connect signal
                self.current_input = self.ndi_input
            except Exception as e:
                self.handle_error(f"Failed to initialize NDI Input for '{selected_ndi_source}': {e}")
                return
        
        # Determine selected output
        output_type = self.output_selector.currentText()
        if output_type == "NDI Output":
            self.current_output = self.ndi_output
        elif output_type == "SDI Output":
            self.current_output = self.sdi_output
            
        if not self.current_input or not self.current_output:
            self.handle_error("Input or Output module not initialized correctly.")
            return

        # Connect frame_ready signal from current input to handle_frame
        try:
            self.current_input.frame_ready.disconnect() # Disconnect previous connections
        except TypeError:
            pass # No previous connection
        self.current_input.frame_ready.connect(self.handle_frame)

        if self.current_input.start():
            if self.current_output.start():
                self.status_label.setText(f"Running: {input_type} to {output_type}")
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
            else:
                self.current_input.stop()
                self.status_label.setText(f"Failed to start {output_type}")
        else:
            self.status_label.setText(f"Failed to start {input_type}")
    
    def stop_conversion(self):
        """Stop the current conversion process"""
        if self.current_input:
            self.current_input.stop()
        if self.current_output:
            self.current_output.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")
        
    def handle_frame(self, frame):
        """Handle incoming frames from the current input"""
        # Update preview
        self.preview.update_frame(frame)
        
        # Send to current output
        self.current_output.send_frame(frame)
        
    def closeEvent(self, event):
        """Handle window close"""
        self.stop_conversion()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
