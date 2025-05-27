from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter
import cv2
import numpy as np

class PreviewWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.setMinimumSize(640, 360)
        self.frame = None
        self.qimage = None
        
    def update_frame(self, frame):
        """Update the preview with a new frame"""
        if frame is not None:
            # Convert frame to RGB for display
            if len(frame.shape) == 2:
                # If grayscale, convert to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
            else:
                # If BGR (from OpenCV) or YUV, convert to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            height, width = rgb_frame.shape[:2]
            bytes_per_line = width * 3
            
            # Create QImage from the frame
            self.qimage = QImage(
                rgb_frame.data,
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_RGB888
            )
            self.frame = frame
            self.update()
        
    def paintEvent(self, event):
        if self.qimage is not None:
            painter = QPainter(self)
            
            # Calculate aspect ratio preserved scaling
            widget_ratio = self.width() / self.height()
            image_ratio = self.qimage.width() / self.qimage.height()
            
            if widget_ratio > image_ratio:
                # Widget is wider than image
                h = self.height()
                w = int(h * image_ratio)
                x = (self.width() - w) // 2
                y = 0
            else:
                # Widget is taller than image
                w = self.width()
                h = int(w / image_ratio)
                x = 0
                y = (self.height() - h) // 2
            
            # Draw the image centered and scaled
            painter.drawImage(x, y, self.qimage.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio))
