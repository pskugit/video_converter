import os
import sys
import time
from pathlib import Path
from os.path import isfile, join

# External packages
import cv2
import tqdm
import imageio
from PyQt5 import QtWidgets, QtCore, QtGui, uic


class Worker(QtCore.QObject):
    """
    Worker thread that handles the major program load, allowing the GUI to remain responsive.
    """
    progress = QtCore.pyqtSignal(int)  # Change to int type
    finished = QtCore.pyqtSignal()

    def __init__(self, filenames, config):
        super(Worker, self).__init__()
        self.filenames = filenames
        self.config = config

    @QtCore.pyqtSlot()
    def images(self):
        """
        Function to convert the video to an image folder.
        """
        try:
            cap = cv2.VideoCapture(self.filenames)
            length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if length == 0 or fps == 0:
                raise ValueError("Invalid video file.")
            print("Video FPS:", fps)
            print("Number of frames:", length)

            # Create directory for images
            dir_path = os.path.join(
                os.path.dirname(self.filenames),
                f"{Path(self.filenames).stem}_images"
            )
            print("Creating folder:", dir_path)

            if not os.path.exists(dir_path):
                os.mkdir(dir_path)
            else:
                print("Folder already exists. Continuing frame extraction...")

            ret = True
            i = 1
            width = len(str(length))

            # Extract frames and save them as images
            while ret:
                ret, frame = cap.read()
                if ret:
                    filename = os.path.join(dir_path, f"{str(i).zfill(width)}.png")
                    cv2.imwrite(filename, frame)
                    print("Saved", filename)
                    self.progress.emit(int(100 * (i / length)))  # Ensure emitting int value
                    i += 1

            cap.release()
        except Exception as e:
            print(f"Error during frame extraction: {e}")
        finally:
            self.finished.emit()

    @QtCore.pyqtSlot()
    def video(self):
        """
        Function to convert an image folder into a video.
        """
        try:
            container = ".mp4"
            codec = "HEVC"
            max_length = self.config["max_length"] or len(self.filenames)
            size = self.config["size"]
            repeatframe = self.config["repeatframe"]
            fps = self.config["fps"]

            output_path = Path("videos") / f"video_{time.strftime('%y_%m_%d_%H-%M-%S')}{container}"
            output_path.parent.mkdir(exist_ok=True)

            if size == (0, 0):
                size = cv2.imread(self.filenames[0]).shape[1::-1]

            print("Video Format")
            print(f"Resolution: {size}, Container: {container}, Codec: {codec}, Output: {output_path}")

            output = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*codec), fps, size)
            for idx, file in tqdm.tqdm(enumerate(self.filenames[:max_length])):
                frame = cv2.imread(file)
                if frame is None:
                    print("Skipped invalid file:", file)
                    continue
                frame = cv2.resize(frame, size)
                for _ in range(repeatframe):
                    output.write(frame)
                self.progress.emit(int(100 * ((idx + 1) / max_length)))  # Emit progress as int

            output.release()
            print(f"Saved video in {output_path}")
        except Exception as e:
            print(f"Error during video creation: {e}")
        finally:
            self.finished.emit()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("mv3_gui.ui", self)
        self.setWindowTitle("Video Maker")
        self.config = {
            "max_length": 0,
            "size": (0, 0),
            "repeatframe": 1,
            "fps": 30,
        }
        self.filenames = []
        self.setup_ui()

    def setup_ui(self):
        self.set_defaults()
        self.setup_connections()
        self.change_mode(0)
        self.progress.setValue(0)

    def setup_connections(self):
        self.data_button.clicked.connect(self.filedialog_folder)
        self.mv_button.clicked.connect(self.action)
        self.mode_slider.valueChanged.connect(self.change_mode)

    def filedialog_folder(self):
        dlg = QtWidgets.QFileDialog()
        if self.mode == "f2v":
            folder = dlg.getExistingDirectory(self, "Select Image Folder", os.getcwd())
            if folder:
                self.filenames = [join(folder, f) for f in sorted(os.listdir(folder)) if isfile(join(folder, f))]
        else:
            video_file, _ = dlg.getOpenFileName(self, "Select Video File", os.getcwd(), "Video Files (*.mp4 *.avi)")
            if video_file:
                self.filenames = video_file

        self.mv_button.setEnabled(bool(self.filenames))

    def action(self):
        self.mv_button.setEnabled(False)
        self.data_button.setEnabled(False)
        self.mode_slider.setEnabled(False)

        self.worker = Worker(self.filenames, self.config)
        self.worker_thread = QtCore.QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.on_finish)

        if self.mode == "f2v":
            self.worker_thread.started.connect(self.worker.video)
        else:
            self.worker_thread.started.connect(self.worker.images)

        self.worker_thread.start()

    def on_finish(self):
        self.mv_button.setEnabled(True)
        self.data_button.setEnabled(True)
        self.mode_slider.setEnabled(True)

    def set_defaults(self):
        self.max_length_le.setText(str(self.config["max_length"]))
        self.size1_le.setText(str(self.config["size"][0]))
        self.size2_le.setText(str(self.config["size"][1]))
        self.repeatframe_le.setText(str(self.config["repeatframe"]))
        self.fps_le.setText(str(self.config["fps"]))

    def update_config(self):
        try:
            self.config = {
                "max_length": int(self.max_length_le.text()),
                "size": (int(self.size1_le.text()), int(self.size2_le.text())),
                "repeatframe": int(self.repeatframe_le.text()),
                "fps": float(self.fps_le.text()),
            }
        except ValueError:
            print("Invalid configuration.")

    def change_mode(self, value):
        self.mode = "f2v" if value == 0 else "v2f"
        self.data_label.setText("Select Folder" if self.mode == "f2v" else "Select Video")
        self.mv_button.setText("Make Video" if self.mode == "f2v" else "Make Images")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())
