import wx
import threading
import subprocess
import os
import re
import sys
from speech import speak
import urllib.parse
import uuid


def normalize_filename(filename):
    """
    Cleans a string to be suitable for use as a filename.
    Removes invalid characters, control characters, and characters
    outside the Basic Multilingual Plane (common for emojis).
    """
    # 1. Remove standard invalid filesystem characters for most OSes
    #    Replace with underscore '_'
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)

    # 2. Remove non-printable control characters (ASCII C0 and C1 controls)
    #    Replace with empty string ''
    safe_name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe_name)

    # 3. Remove characters outside the Basic Multilingual Plane (U+0000 to U+FFFF)
    #    This removes many emojis and symbols that cause issues in filenames.
    #    Replace with empty string ''
    safe_name = "".join(c for c in safe_name if ord(c) <= 0xFFFF)

    # 4. Collapse sequences of multiple underscores to a single underscore.
    safe_name = re.sub(r'_+', '_', safe_name)
    # 5. Collapse sequences of multiple spaces to a single space.
    safe_name = re.sub(r' +', ' ', safe_name)
    safe_name = safe_name.strip('_ ')

    # Ensure filename is not empty after cleaning
    if not safe_name:
        safe_name = filename
    return safe_name

class DownloadDialog(wx.Dialog):
    def __init__(self, parent, title, is_audio=False):
        super().__init__(parent, title=title, size=(600, 300), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.is_audio = is_audio
        self.parent_frame = parent
        self.downloading = True
        self.process = None
        self.output_reader_thread = None
        self.success = False
        self.last_status_message = ""

        if getattr(sys, 'frozen', False):
             self.project_root = os.path.dirname(sys.executable)
        else:
             self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.yt_dlp_exe_path = os.path.join(self.project_root, 'yt-dlp.exe')
        self.ffmpeg_path = getattr(parent, 'ffmpeg_path', os.path.join(self.project_root, 'ffmpeg.exe'))
        self.ffmpeg_dir = os.path.dirname(self.ffmpeg_path)

        self.panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.percent_label = wx.StaticText(self.panel, label="")
        self.size_label = wx.StaticText(self.panel, label="")
        self.speed_label = wx.StaticText(self.panel, label="")
        self.eta_label = wx.StaticText(self.panel, label="")
        vbox.Add(self.percent_label, 0, wx.ALL | wx.EXPAND, 2) # Less border for labels
        vbox.Add(self.size_label, 0, wx.ALL | wx.EXPAND, 2)
        vbox.Add(self.speed_label, 0, wx.ALL | wx.EXPAND, 2)
        vbox.Add(self.eta_label, 0, wx.ALL | wx.EXPAND, 2)

        self.percent_label.Hide()
        self.size_label.Hide()
        self.speed_label.Hide()
        self.eta_label.Hide()

        self.status_details_text = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.status_details_text.SetValue("Initializing download...")
        vbox.Add(self.status_details_text, 1, wx.ALL | wx.EXPAND, 5)

        self.progress_bar = wx.Gauge(self.panel, range=1000, size=(350, 20), style=wx.GA_HORIZONTAL)
        vbox.Add(self.progress_bar, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        cancel_button = wx.Button(self.panel, label="Cancel")
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        vbox.Add(cancel_button, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.panel.SetSizer(vbox)
        self.Layout()
        self.Fit()
        self.Centre()
        self.Show()

        self.progress_regex = re.compile(
            r"\[download\]\s+"
            r"(?P<percent>[\d.]+)%\s+of\s+"
            r"(?:~?\s*)?"
            r"(?P<size>[\d.]+[KMGTP]?i?B)\s+"
            r"at\s+"
            r"(?P<speed>[\d.]+[KMGTP]?i?B/s)\s+"
            r"ETA\s+"
            r"(?P<eta>[\d:]+)"
        )

    def download_task(self, url, title, download_path):
        self.url = url
        # self.safe_title = re.sub(r'[<>:"/\\|?*]', '_', title).strip()
        self.safe_title = normalize_filename(title)
        if not self.safe_title:
            self.safe_title = "download"

        self.download_path = download_path

        if not os.path.exists(self.yt_dlp_exe_path):
             wx.CallAfter(self.update_status, f"Error: yt-dlp.exe not found at {self.yt_dlp_exe_path}", speak_msg=True)
             wx.CallAfter(self.on_finish)
             return

        if not os.path.exists(self.ffmpeg_path):
            wx.CallAfter(self.update_status, f"Error: ffmpeg.exe not found at {self.ffmpeg_path}. yt-dlp requires it for conversion.", speak_msg=True)
            wx.CallAfter(self.on_finish)
            return

        self.dl_thread = threading.Thread(target=self.start_download_process)
        self.dl_thread.start()
        wx.CallAfter(self.SetFocus)

    def extract_video_id(self, url):
        """Extracts YouTube video ID from various URL formats."""

        try:
            parsed_url = urllib.parse.urlparse(url)
            if parsed_url.hostname == 'youtu.be':
                return parsed_url.path[1:]
            if parsed_url.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
                if parsed_url.path == '/watch':
                    query = urllib.parse.parse_qs(parsed_url.query)
                    return query.get('v', [None])[0]
                if parsed_url.path.startswith('/embed/'):
                    return parsed_url.path.split('/embed/')[1]
                if parsed_url.path.startswith('/v/'):
                    return parsed_url.path.split('/v/')[1]
        except Exception as e:
            print(f"Error parsing video ID from URL '{url}': {e}")
        return str(uuid.uuid4())

    def start_download_process(self):
        """Prepares and starts the yt-dlp subprocess."""
        try:
            if not self.downloading:
                return

            self.video_id = self.extract_video_id(self.url)
            if not self.video_id:
                 error_msg = "Could not determine video ID for temporary filename."
                 wx.CallAfter(self.update_status, error_msg, speak_msg=True)
                 wx.CallAfter(self.on_finish)
                 return

            self.temp_filename_base = self.video_id
            temp_output_template = os.path.join(self.download_path, f'{self.temp_filename_base}.%(ext)s')
            temp_output_template = os.path.normpath(temp_output_template)

            cmd = [self.yt_dlp_exe_path]
            cmd.extend(['--no-warnings', '--progress', '--no-playlist'])
            cmd.extend(['--ffmpeg-location', self.ffmpeg_dir])
            cmd.extend(['-P', self.download_path])
            cmd.extend(['-o', temp_output_template])

            if self.is_audio:
                # Download best audio and use yt-dlp's post-processor to convert
                self.final_extension = ".mp3"
                cmd.extend(['-f', 'bestaudio/best'])
                cmd.extend(['-x'])
                cmd.extend(['--audio-format', 'mp3'])
                cmd.extend(['--audio-quality', '128K'])
                cmd.extend(['--add-metadata'])
                cmd.extend(['--embed-thumbnail'])
            else:
                self.final_extension = ".mp4"
                cmd.extend(['-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'])
                cmd.extend(['--merge-output-format', 'mp4'])

            cmd.append(self.url)

            self._run_download_process(cmd)

        except Exception as e:
            error_msg = f"Error preparing download: {e}"
            print(error_msg)
            wx.CallAfter(self.update_status, error_msg, speak_msg=True)
            wx.CallAfter(self.on_finish)

    def _run_download_process(self, cmd):
        """Executes the command using subprocess and starts the output reader."""
        if not self.downloading:
            return

        wx.CallAfter(self.update_status, "Starting download...", speak_msg=True)

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                bufsize=1
            )

            self.output_reader_thread = threading.Thread(target=self.read_output, daemon=True)
            self.output_reader_thread.start()
            self.process.wait() # Wait for yt-dlp to finish

            if self.downloading:
                if self.process.returncode == 0:
                    self.success = True
                    wx.CallAfter(self.update_status, "Download process finished. Finalizing...", speak_msg=False)

                    try:
                        temp_file_path = os.path.join(self.download_path, f"{self.temp_filename_base}{self.final_extension}")
                        temp_file_path = os.path.normpath(temp_file_path)
                        final_file_path = os.path.join(self.download_path, f"{self.safe_title}{self.final_extension}")
                        final_file_path = os.path.normpath(final_file_path)

                        # Check if the temporary file exists before renaming
                        if os.path.exists(temp_file_path):
                            if os.path.exists(final_file_path) and temp_file_path != final_file_path:
                                os.remove(final_file_path)
                            os.rename(temp_file_path, final_file_path)
                            wx.CallAfter(self.update_status, "Download finished successfully.", speak_msg=True)
                        else:
                            if os.path.exists(final_file_path):
                                wx.CallAfter(self.update_status, "Download finished successfully.", speak_msg=True)
                            else:
                                self.success = False
                                error_msg = f"Download finished, but expected file '{os.path.basename(temp_file_path)}' or '{os.path.basename(final_file_path)}' not found."
                                wx.CallAfter(self.update_status, error_msg, speak_msg=True)

                    except OSError as e:
                        self.success = False
                        error_msg = f"Error during file finalization/rename: {e}"
                        wx.CallAfter(self.update_status, error_msg, speak_msg=True)
                    except Exception as e:
                        self.success = False
                        error_msg = f"Unexpected error during file finalization: {e}"
                        wx.CallAfter(self.update_status, error_msg, speak_msg=True)

                else:
                    self.success = False
                    error_msg = f"Download failed. yt-dlp exited with code {self.process.returncode}."
                    print(error_msg)
                    # Try reading stderr in the reader thread first
                    wx.CallAfter(self.update_status, error_msg, speak_msg=True)

        except FileNotFoundError:
            error_msg = f"Error: Command not found - {cmd[0]}"
            print(error_msg)
            wx.CallAfter(self.update_status, error_msg, speak_msg=True)
        except Exception as e:
            error_msg = f"Error running subprocess: {e}"
            print(error_msg)
            wx.CallAfter(self.update_status, error_msg, speak_msg=True)
        finally:
            wx.CallAfter(self.on_finish)

    def read_output(self):
        """Reads stdout/stderr line by line from the subprocess."""
        stderr_lines = []

        try:
            for line in iter(self.process.stdout.readline, ''):
                if not self.downloading: break
                line = line.strip()
                if line:
                    match = self.progress_regex.match(line)
                    if match:
                        progress_data = match.groupdict()
                        wx.CallAfter(self.update_progress, progress_data)
                    elif line.startswith('[ExtractAudio]') or line.startswith('[Merger]'):
                        # Show post-processing status, but don't speak it
                        wx.CallAfter(self.update_status, line, speak_msg=False)
                    elif line.startswith('Deleting original file'):
                         # Often follows successful conversion
                         wx.CallAfter(self.update_status, "Cleaning up...", speak_msg=False)

            # Close stdout pipe when done reading
            if self.process and self.process.stdout:
                try: self.process.stdout.close()
                except Exception: pass

        except Exception as e:
            if self.downloading:
                 print(f"Error reading stdout: {e}")

        try:
            for line in iter(self.process.stderr.readline, ''):
                 if not self.downloading: break
                 line = line.strip()
                 if line:
                    print(f"stderr: {line}")
                    stderr_lines.append(line)
                    if len(stderr_lines) > 10:
                         stderr_lines.pop(0)

            # Close stderr pipe when done reading
            if self.process and self.process.stderr:
                 try: self.process.stderr.close()
                 except Exception: pass

        except Exception as e:
             if self.downloading:
                 print(f"Error reading stderr: {e}")

        # Update status if failed and stderr has info
        if self.process and self.process.poll() != 0 and stderr_lines and self.downloading:
             error_msg = f"Download failed (Code: {self.process.poll()}).\nErrors:\n" + "\n".join(stderr_lines)
             wx.CallAfter(self.update_status, error_msg, speak_msg=True)

    def update_progress(self, progress_data):
        """Updates the progress bar, status labels, and text control."""
        if not self.downloading:
             return

        try:
            percent = float(progress_data.get('percent', 0))
            size = progress_data.get('size', 'N/A')
            speed = progress_data.get('speed', 'N/A')
            eta = progress_data.get('eta', 'N/A')
            self.progress_bar.SetValue(int(percent * 10))

            percent_str = f"Percent: {percent:.1f}%"
            size_str = f"Size: {size}"
            speed_str = f"Speed: {speed}"
            eta_str = f"ETA: {eta}"

            labels_updated = False
            if self.percent_label:
                self.percent_label.SetLabel(percent_str)
                if not self.percent_label.IsShown():
                    self.percent_label.Show()
                    labels_updated = True
            if self.size_label:
                self.size_label.SetLabel(size_str)
                if not self.size_label.IsShown():
                    self.size_label.Show()
                    labels_updated = True
            if self.speed_label:
                self.speed_label.SetLabel(speed_str)
                if not self.speed_label.IsShown():
                    self.speed_label.Show()
                    labels_updated = True
            if self.eta_label:
                self.eta_label.SetLabel(eta_str)
                if not self.eta_label.IsShown():
                    self.eta_label.Show()
                    labels_updated = True

            if self.status_details_text:
                details_string = f"{percent_str}\n{size_str}\n{speed_str}\n{eta_str}"
                self.status_details_text.SetValue(details_string)

            if labels_updated:
                self.panel.Layout()

            speak_interval = 20
            if abs(round(percent / speak_interval) * speak_interval - percent) < 0.5 and percent > 1:
                 current_percent_int = int(round(percent / speak_interval) * speak_interval)
                 if current_percent_int > 0 and str(current_percent_int) not in self.last_status_message:
                     speak(f"{current_percent_int} percent", interrupt=False)
                     self.last_status_message = f"{current_percent_int} percent"

        except Exception as e:
            print(f"Error updating progress UI: {e}")

    def update_status(self, status, speak_msg=False):
        """Updates the status text control, hides labels for general messages, and optionally speaks."""
        current_value = self.status_details_text.GetValue() if self.status_details_text else ""
        if status != self.last_status_message and status != current_value:

            labels_hidden = False
            if not status.startswith("Percent:") and not status.startswith("Downloading:"):
                 if self.percent_label and self.percent_label.IsShown():
                      self.percent_label.Hide()
                      labels_hidden = True
                 if self.size_label and self.size_label.IsShown():
                      self.size_label.Hide()
                      labels_hidden = True
                 if self.speed_label and self.speed_label.IsShown():
                      self.speed_label.Hide()
                      labels_hidden = True
                 if self.eta_label and self.eta_label.IsShown():
                      self.eta_label.Hide()
                      labels_hidden = True

            if self.status_details_text:
                 self.status_details_text.SetValue(status)

            # Update layout if labels were hidden
            if labels_hidden:
                 self.panel.Layout()

            if speak_msg:
                speak(status, interrupt=True)
            if speak_msg:
                self.last_status_message = status

    def on_cancel(self, event):
        """Handles the cancel button click."""
        dlg = wx.MessageDialog(self, "Are you sure you want to cancel the download?", "Confirm Cancel", wx.YES_NO | wx.ICON_QUESTION)
        result = dlg.ShowModal()
        dlg.Destroy()

        if result == wx.ID_YES:
             if self.downloading:
                 self.downloading = False
                 wx.CallAfter(self.update_status, "Cancelling...", speak_msg=True)
                 if self.process and self.process.poll() is None:
                     try:
                         self.process.terminate()
                         try:
                             self.process.wait(timeout=2)
                         except subprocess.TimeoutExpired:
                             print("Process did not terminate, killing...")
                             self.process.kill()
                     except ProcessLookupError:
                         print("Process already finished.")
                     except Exception as e:
                         print(f"Error terminating process: {e}")
                 self.process = None

                 if self.output_reader_thread and self.output_reader_thread.is_alive():
                     try:
                         self.output_reader_thread.join(timeout=1)
                     except Exception as e:
                         print(f"Error joining reader thread: {e}")

             if not self.IsBeingDeleted():
                 wx.CallAfter(self.Destroy)

    def on_finish(self):
        """Called when the download process completes or fails (if not cancelled)."""
        if self.downloading:
            if self.success:
                 wx.CallAfter(self.progress_bar.SetValue, 1000)
                 wx.CallAfter(self.show_success_message_dialog)
            else:
                 wx.CallAfter(self.progress_bar.SetValue, 0)
                 if not self.IsBeingDeleted():
                     wx.CallAfter(self.Destroy)

    def show_success_message_dialog(self):
        """Shows the final success message and closes."""
        if self.downloading and not self.IsBeingDeleted():
             wx.MessageBox("Download Complete!", "Success", wx.OK | wx.ICON_INFORMATION, parent=self.GetParent())
             self.Destroy()

    def Destroy(self):
        """Overrides Destroy to ensure cleanup."""
        self.downloading = False
        if self.process and self.process.poll() is None:
            try:
                self.process.kill()
                self.process.wait(timeout=1)
            except Exception as e:
                print(f"Error killing process during Destroy: {e}")
        self.process = None
        # Attempt to join thread if it's still alive
        if self.output_reader_thread and self.output_reader_thread.is_alive():
            try:
                self.output_reader_thread.join(timeout=1)
            except Exception as e:
                print(f"Error joining reader thread in Destroy: {e}")

        if not hasattr(self, '_already_destroying'): # Prevent recursion
             self._already_destroying = True
             super().Destroy()
