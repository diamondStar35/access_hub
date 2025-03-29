import wx
import threading
from speech import speak
import yt_dlp
import os
import re
from pydub import AudioSegment
import shutil

class DownloadDialog(wx.Dialog):
    def __init__(self, parent, title,  is_audio=False):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.is_audio=is_audio
        self.parent_frame = parent
        self.downloading = True
        self.dl_process = None
        self.current_task=None
        self.success=False

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(panel, label="Initializing...")
        vbox.Add(self.status_label, 0, wx.ALL | wx.CENTER, 10)

        self.progress_bar = wx.Gauge(panel, range=100, size=(250, 20), style=wx.GA_HORIZONTAL)
        vbox.Add(self.progress_bar, 0, wx.ALL | wx.CENTER, 10)

        cancel_button = wx.Button(panel, label="Cancel")
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        vbox.Add(cancel_button, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(vbox)
        vbox.Fit(panel)

        self.Centre()
        self.Show()
        self.SetFocus()


    def download_task(self, url, title, download_path):
        self.url = url
        self.title = title
        self.download_path=download_path
        self.dl_process = threading.Thread(target=self.start_download)
        self.dl_process.start()

    def start_download(self):
        try:
            if not self.downloading:
              return
            if self.is_audio:
                self.current_task = "audio"
                self._download_audio()
            else:
                self.current_task = "video"
                self._download_video()
        except Exception as e:
             wx.CallAfter(self.update_status, f"Error during {self.current_task} download: {e}")
             wx.CallAfter(self.progress_bar.SetValue, 0)

    def _download_video(self):
        try:
            wx.CallAfter(self.update_status, "Downloading Video...")
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': os.path.join(self.download_path, f'{self.title}.%(ext)s'),
                'quiet': True,
                'noplaylist': True,
                'progress_hooks': [self.download_progress_hook],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            if self.downloading:
                wx.CallAfter(self.update_status, "Video Download Complete")
                self.success=True
        except Exception as e:
            if self.downloading:
                wx.CallAfter(self.update_status, f"Error while downloading video:{e}")
        finally:
            wx.CallAfter(self.on_finish)

    def _download_audio(self):
        try:
            wx.CallAfter(self.update_status, "Downloading Audio...")
            safe_title = re.sub(r'[|\\/:"*?<>]', '_', self.title)
            output_video = os.path.join(self.download_path, f"{safe_title}.mp4")
            output_mp3 = os.path.join(self.download_path, f"{safe_title}.mp3")

            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': output_video,
                'quiet': True,
                'noplaylist': True,
                'progress_hooks': [self.download_progress_hook],
                'http_headers': {'User-Agent': 'Mozilla/5.0'},
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            if self.downloading:
                wx.CallAfter(self.update_status, "Converting Audio...")
                self.convert_audio(output_video, output_mp3)
                if self.downloading:
                    wx.CallAfter(self.update_status, "Audio Download Complete")
                    self.success=True
        except Exception as e:
            if self.downloading:
                wx.CallAfter(self.update_status, f"Error while downloading audio:{e}")
        finally:
             wx.CallAfter(self.on_finish)

    def convert_audio(self, input_path, output_path):
        try:
            os.environ["PATH"] += os.pathsep + os.path.dirname(self.parent_frame.ffmpeg_path)
            # Load the video file using pydub
            video = AudioSegment.from_file(input_path, "mp4")
            # Export the audio as MP3
            video.export(output_path, format="mp3", codec="libmp3lame")
        except Exception as e:
            if self.downloading:
                wx.CallAfter(self.update_status, f"Conversion Failed: {e}")
        finally:
             if os.path.exists(input_path):
                os.remove(input_path)

    def download_progress_hook(self, d):
        if d['status'] == 'downloading':
            if self.downloading:
                # Calculate the percentage based on downloaded bytes and total bytes
                if 'total_bytes' in d and d['total_bytes'] is not None:
                    percentage = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    wx.CallAfter(self.progress_bar.SetValue, int(percentage))
                elif 'total_bytes_estimate' in d and d['total_bytes_estimate'] is not None:
                    percentage = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                    wx.CallAfter(self.progress_bar.SetValue, int(percentage))

    def update_status(self, status):
        self.status_label.SetLabel(status)
        speak(status)

    def on_cancel(self, event):
        dlg = wx.MessageDialog(self, "Are you sure you want to cancel?", "Confirm Cancel", wx.YES_NO | wx.ICON_QUESTION)
        result = dlg.ShowModal()
        dlg.Destroy()
        if result == wx.ID_YES:
             self.downloading = False
             if self.dl_process and self.dl_process.is_alive():
                 self.dl_process = None
             self.Destroy()
             self.parent_frame.results_listbox.SetFocus()

    def on_finish(self):
        if self.downloading:
            wx.CallAfter(self.progress_bar.SetValue, 100)
            if self.success:
                wx.CallAfter(self.show_success_message_dialog)
            else:
                wx.CallAfter(self.Destroy)
        elif not self.downloading:
            wx.CallAfter(self.Destroy)

    def show_success_message_dialog(self):
        if self.downloading:
             wx.MessageBox(f"Download Complete", "Success", wx.OK | wx.ICON_INFORMATION)
             self.Destroy()