import sys
import os
import subprocess
import json
import re
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QListWidget,
    QCheckBox,
    QSlider,
    QDialog,
    QStyle,
    QMessageBox,
    QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent


def get_ffmpeg_path():
    if getattr(sys, "frozen", False):
        application_path = sys._MEIPASS
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    return application_path


def find_executable(name):
    path = os.path.join(get_ffmpeg_path(), name)
    if os.path.exists(path):
        return path

    path = os.path.join(os.path.dirname(sys.executable), name)
    if os.path.exists(path):
        return path

    for path in os.environ["PATH"].split(os.pathsep):
        exe_file = os.path.join(path, name)
        if os.path.isfile(exe_file):
            return exe_file

    return None


class VideoProcessorThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(float)

    def __init__(self, videos, compress, trim_values):
        super().__init__()
        self.videos = videos
        self.compress = compress
        self.trim_values = trim_values

    def run(self):
        total_videos = len(self.videos)
        for index, video in enumerate(self.videos):
            try:
                self.process_video(
                    video, self.compress, self.trim_values.get(video, None)
                )
                self.progress.emit(100)
                # If it's not the last video, reset progress for the next video
                if index < total_videos - 1:
                    self.progress.emit(0)
            except Exception as e:
                self.error.emit(str(e))
                return
        self.finished.emit()

    def process_video(self, video, compress, trim):
        output = os.path.splitext(video)[0] + "_processed.mp4"

        ffmpeg_path = find_executable("ffmpeg.exe")
        if not ffmpeg_path:
            raise FileNotFoundError(
                "FFmpeg not found. Please ensure it's installed and in your PATH."
            )

        cuda_command = [
            ffmpeg_path,
            "-hwaccel",
            "cuda",
            "-hwaccel_output_format",
            "cuda",
            "-extra_hw_frames",
            "3",
            "-threads",
            "8",
            "-i",
            video,
            "-progress",
            "pipe:1",
            "-nostats",
        ]

        if trim:
            start = trim["start"]
            end = trim["end"]
            duration = end - start
            cuda_command.extend(["-ss", str(start), "-t", str(duration)])

        if compress:
            cuda_command.extend(
                [
                    "-c:v",
                    "h264_nvenc",
                    "-preset",
                    "p2",
                    "-tune",
                    "hq",
                    "-cq",
                    "28",
                    "-b:v",
                    "0",
                    "-maxrate",
                    "10M",
                    "-bufsize",
                    "20M",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "96k",
                ]
            )
        else:
            cuda_command.extend(
                [
                    "-c:v",
                    "h264_nvenc",
                    "-preset",
                    "p2",
                    "-tune",
                    "hq",
                    "-cq",
                    "15",
                    "-b:v",
                    "0",
                    "-maxrate",
                    "130M",
                    "-bufsize",
                    "260M",
                    "-c:a",
                    "copy",
                ]
            )

        cuda_command.append(output)

        try:
            process = subprocess.Popen(
                cuda_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )

            duration = self.get_video_duration(video)
            last_progress = 0
            for line in process.stdout:
                progress = self.parse_progress(line, duration)
                if progress is not None:
                    # Limit progress to 99% to leave room for final processing
                    progress = min(progress, 99)
                    if progress > last_progress:
                        self.progress.emit(progress)
                        last_progress = progress

            process.wait()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cuda_command)

        except subprocess.CalledProcessError:
            print("CUDA acceleration failed. Falling back to CPU encoding.")

            cpu_command = [ffmpeg_path, "-i", video, "-progress", "pipe:1", "-nostats"]

            if trim:
                cpu_command.extend(["-ss", str(start), "-t", str(duration)])

            if compress:
                cpu_command.extend(
                    [
                        "-c:v",
                        "libx264",
                        "-preset",
                        "medium",
                        "-crf",
                        "23",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                    ]
                )
            else:
                cpu_command.extend(
                    ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-c:a", "copy"]
                )

            cpu_command.append(output)

            process = subprocess.Popen(
                cpu_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )

            last_progress = 0
            for line in process.stdout:
                progress = self.parse_progress(line, duration)
                if progress is not None:
                    # Limit progress to 99% to leave room for final processing
                    progress = min(progress, 99)
                    if progress > last_progress:
                        self.progress.emit(progress)
                        last_progress = progress

            process.wait()
            if process.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg command failed with return code {process.returncode}"
                )

        # Ensure progress reaches 100% after processing is complete
        self.progress.emit(100)

    def get_video_duration(self, video):
        ffprobe_path = find_executable('ffprobe.exe')
        if not ffprobe_path:
            raise FileNotFoundError(
                "FFprobe not found. Please ensure it's installed and in your PATH."
            )

        command = [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            video,
        ]
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFprobe failed: {result.stderr}")

        output = json.loads(result.stdout)
        return float(output["format"]["duration"])

    def parse_progress(self, line, duration):
        time_match = re.search(r'out_time_ms=(\d+)', line)
        if time_match:
            time_ms = int(time_match.group(1))
            progress = (time_ms / 1000000) / duration * 100
            return min(progress, 100)
        return None

    def get_video_duration(self, video):
        ffprobe_path = find_executable("ffprobe.exe")
        if not ffprobe_path:
            raise FileNotFoundError(
                "FFprobe not found. Please ensure it's installed and in your PATH."
            )

        command = [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            video,
        ]
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFprobe failed: {result.stderr}")

        output = json.loads(result.stdout)
        return float(output["format"]["duration"])

    def parse_progress(self, line, duration):
        time_match = re.search(r"out_time_ms=(\d+)", line)
        if time_match:
            time_ms = int(time_match.group(1))
            progress = (time_ms / 1000000) / duration * 100
            return min(progress, 100)
        return None


class DragDropBox(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setText("Drag and drop videos here\nor click to select")
        self.setStyleSheet(
            """
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 10px;
                padding: 40px;
                background-color: #f0f0f0;
                font-size: 18px;
            }
        """
        )
        self.setAcceptDrops(True)
        self.setMinimumHeight(200)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        files = [
            url.toLocalFile()
            for url in urls
            if url.toLocalFile().endswith((".mp4", ".avi", ".mov"))
        ]
        self.parent().add_videos(files)

    def mousePressEvent(self, event):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Videos", "", "Video Files (*.mp4 *.avi *.mov)"
        )
        if files:
            self.parent().add_videos(files)


class VideoProcessor(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.drag_drop_box = DragDropBox()
        layout.addWidget(self.drag_drop_box)

        self.video_list = QListWidget()
        self.video_list.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: #fff;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
            }
        """
        )
        layout.addWidget(self.video_list)

        options_layout = QHBoxLayout()
        self.compress_checkbox = QCheckBox("Compress Videos")
        self.compress_checkbox.setStyleSheet(
            """
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #999;
                background-color: #fff;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
            }
        """
        )
        options_layout.addWidget(self.compress_checkbox)

        self.trim_button = QPushButton("Trim Selected Video")
        self.trim_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """
        )
        self.trim_button.clicked.connect(self.show_trim_dialog)
        options_layout.addWidget(self.trim_button)

        layout.addLayout(options_layout)

        self.process_button = QPushButton("Process Videos")
        self.process_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """
        )
        self.process_button.clicked.connect(self.process_videos)
        layout.addWidget(self.process_button)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)
        self.setWindowTitle("ClipLy")
        self.setGeometry(100, 100, 800, 900)
        self.setStyleSheet(
            """
            QWidget {
                background-color: #f5f5f5;
                font-family: Arial, sans-serif;
            }
        """
        )

        self.trim_values = {}

    def add_videos(self, files):
        for file in files:
            if file not in [
                self.video_list.item(i).text() for i in range(self.video_list.count())
            ]:
                self.video_list.addItem(file)

    def show_trim_dialog(self):
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return

        video = selected_items[0].text()
        dialog = TrimDialog(video, self)
        if dialog.exec_() == QDialog.Accepted:
            self.trim_values[video] = dialog.get_trim_values()

    def process_videos(self):
        videos = [
            self.video_list.item(i).text() for i in range(self.video_list.count())
        ]
        if not videos:
            return

        self.process_button.setEnabled(False)
        self.process_button.setText("Processing...")
        self.progress_bar.setValue(0)
        self.thread = VideoProcessorThread(
            videos, self.compress_checkbox.isChecked(), self.trim_values
        )
        self.thread.finished.connect(self.on_processing_finished)
        self.thread.error.connect(self.on_processing_error)
        self.thread.progress.connect(self.update_progress)
        self.thread.start()

    def update_progress(self, progress):
        self.progress_bar.setValue(int(progress))

    def on_processing_finished(self):
        self.process_button.setEnabled(True)
        self.process_button.setText("Process Videos")
        QMessageBox.information(
            self, "Processing Complete", "All videos have been processed successfully!"
        )

    def on_processing_error(self, error_message):
        self.process_button.setEnabled(True)
        self.process_button.setText("Process Videos")
        QMessageBox.critical(
            self,
            "Processing Error",
            f"An error occurred during processing:\n\n{error_message}",
        )


class TrimDialog(QDialog):
    def __init__(self, video, parent=None):
        super().__init__(parent)
        self.video = video
        self.video_length = self.get_video_length()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.start_slider = self.create_slider("Start Time")
        self.end_slider = self.create_slider("End Time")
        self.end_slider.findChild(QSlider).setValue(100)

        for slider in [self.start_slider, self.end_slider]:
            layout.addWidget(slider)

        buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)

        layout.addLayout(buttons_layout)

        self.setLayout(layout)
        self.setWindowTitle(f"Trim {os.path.basename(self.video)}")
        self.setGeometry(200, 200, 600, 200)

    def create_slider(self, name):
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(10)

        label = QLabel(f"{name}: 0:00")
        slider.valueChanged.connect(
            lambda value, l=label, n=name: l.setText(f"{n}: {self.format_time(value)}")
        )

        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.addWidget(label)
        container_layout.addWidget(slider)
        container.setLayout(container_layout)

        return container

    def format_time(self, value):
        time_in_seconds = int(value / 100 * self.video_length)
        minutes = time_in_seconds // 60
        seconds = time_in_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def get_video_length(self):
        try:
            ffprobe_path = find_executable("ffprobe.exe")
            if not ffprobe_path:
                raise FileNotFoundError(
                    "FFprobe not found. Please ensure it's installed and in your PATH."
                )

            command = [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                self.video,
            ]
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"FFprobe failed: {result.stderr}")

            output = json.loads(result.stdout)
            duration = float(output["format"]["duration"])
            return duration
        except Exception as e:
            print(f"Error getting video duration: {str(e)}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"FFprobe path attempted: {ffprobe_path}")
            print(f"Video file: {self.video}")
            return 300  # Default to 5 minutes if there's an error

    def get_trim_values(self):
        start_value = self.start_slider.findChild(QSlider).value()
        end_value = self.end_slider.findChild(QSlider).value()
        return {
            'start': start_value / 100 * self.video_length,
            'end': end_value / 100 * self.video_length
        }

def get_trim_values(self):
        start_value = self.start_slider.findChild(QSlider).value()
        end_value = self.end_slider.findChild(QSlider).value()
        return {
            'start': start_value / 100 * self.video_length,
            'end': end_value / 100 * self.video_length
        }

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = VideoProcessor()
    ex.show()
    sys.exit(app.exec_())