<h1 align="center">
  <br>
  <img src="https://github.com/Ahmeds360/ClipLy/blob/main/logo.png?raw=true" alt="ClipLy Logo" width="200">
  <br>
  ClipLy
  <br>
</h1>

<h4 align="center">A powerful and user-friendly video processing tool built with Python and PyQt5.</h4>

<p align="center">
  <a href="#key-features">Key Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#build">Build</a> •
  <a href="#contributing">Contributing</a> •
  <a href="#license">License</a>
</p>

![ClipLy Demo](https://github.com/Ahmeds360/ClipLy/blob/main/demo.png?raw=true)

## Key Features

- **Drag and Drop Interface**: Easily add multiple videos to the processing queue.
- **Video Trimming**: Trim videos to specific start and end times.
- **Video Compression**: Option to compress videos for smaller file sizes.
- **GPU Acceleration**: Utilizes NVIDIA CUDA for faster processing (with CPU fallback).
- **Batch Processing**: Process multiple videos in one go.
- **Progress Tracking**: Real-time progress bar for each video being processed.

## Installation

### Option 1: Download Executable (Windows)

For Windows users, you can download the pre-built executable:

[Download ClipLy.exe](https://github.com/Ahmeds360/ClipLy/releases/download/windows/ClipLy.exe)

### Option 2: Run from Source

1. Clone the repository:
   ```
   git clone https://github.com/Ahmeds360/ClipLy.git
   cd ClipLy
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install PyQt5 ffmpeg-python
   ```

4. Run the application:
   ```
   python main.py
   ```

## Usage

1. Launch ClipLy.
2. Drag and drop video files into the application or click to select files.
3. Select videos in the list to trim if desired.
4. Check the "Compress Videos" option if you want to reduce file size.
5. Click "Process Videos" to start the operation.
6. Monitor progress in the progress bar.

## Build

To build the executable yourself:

1. Install Nuitka:
   ```
   pip install nuitka
   ```

2. Run the build command:
   ```
   python -m nuitka --standalone --follow-imports --enable-plugin=pyqt5 --windows-console-mode=disable --onefile --include-data-file=C:\ffmpeg\bin\ffmpeg.exe=ffmpeg.exe --include-data-file=C:\ffmpeg\bin\ffprobe.exe=ffprobe.exe --assume-yes-for-downloads --mingw64 --windows-icon-from-ico=logo.ico --output-filename=ClipLy.exe --show-progress --show-memory --jobs=14 main.py
   ```

   Note: Adjust the paths for ffmpeg.exe and ffprobe.exe according to your system.

## Requirements

- Python 3.6+
- PyQt5
- FFmpeg (included in the executable version)

For GPU acceleration:
- NVIDIA GPU with CUDA support

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- FFmpeg for video processing capabilities
- PyQt5 for the graphical user interface
- Nuitka for Python to executable compilation