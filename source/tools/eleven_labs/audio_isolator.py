import wx
import requests
import concurrent.futures
import io
from pydub import AudioSegment
import os

class AudioIsolation(wx.Panel):
    def __init__(self, parent, api_key, ffmpeg_path):
        super().__init__(parent)
        self.api_key = api_key
        self.audio_file_path = ""
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.ffmpeg_path= ffmpeg_path

        file_path_label = wx.StaticText(self, label="Audio File Path:")
        file_path_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.file_path_textbox = wx.TextCtrl(self, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.HSCROLL)
        browse_button = wx.Button(self, label="Browse")
        browse_button.Bind(wx.EVT_BUTTON, self.on_browse)
        file_path_sizer.Add(self.file_path_textbox, 1, wx.EXPAND | wx.ALL, 5)
        file_path_sizer.Add(browse_button, 0, wx.ALL, 5)

        self.usage_button = wx.Button(self, label="Usage Info")
        self.usage_button.Bind(wx.EVT_BUTTON, self.on_usage_info)
        self.convert_button = wx.Button(self, label="Isolate Audio")
        self.convert_button.Bind(wx.EVT_BUTTON, self.on_convert)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(file_path_label, 0, wx.ALL, 5)
        sizer.Add(file_path_sizer, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.usage_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        sizer.Add(self.convert_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        self.SetSizer(sizer)
        self.Layout()

    def on_browse(self, event):
        with wx.FileDialog(self, "Choose audio file", wildcard="Audio files (*.mp3;*.wav)|*.mp3;*.wav", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_OK:
                self.audio_file_path = fileDialog.GetPath()
                self.file_path_textbox.SetValue(self.audio_file_path)

    def on_usage_info(self, event):
        if not self.audio_file_path:
            wx.MessageBox("Please select an audio file first.", "Error", wx.OK | wx.ICON_ERROR)
            return

        future = self.executor.submit(self.fetch_and_calculate_usage)
        future.add_done_callback(self.show_usage_dialog)

    def fetch_and_calculate_usage(self):
        try:
            audio = AudioSegment.from_file(self.audio_file_path)
            duration_seconds = audio.duration_seconds
            chars_needed = int(duration_seconds * (1000/60)) # 1000 characters per minute

            headers = {'xi-api-key': self.api_key}
            url = "https://api.elevenlabs.io/v1/user/subscription"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            subscription_info = response.json()

            remaining_chars = subscription_info.get("character_count", 0)
            chars_after = remaining_chars - chars_needed
            return audio, chars_needed, remaining_chars, chars_after

        except requests.exceptions.RequestException as e:
            wx.CallAfter(wx.MessageBox, f"Error getting usage info: {e}", "Error", wx.OK | wx.ICON_ERROR)
            return None
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Error processing audio: {e}", "Error", wx.OK | wx.ICON_ERROR)
            return None

    def show_usage_dialog(self, future):
        wx.CallAfter(self.show_dialog, future)

    def show_dialog(self, future):
        usage_info = future.result()
        if usage_info:
            audio, chars_needed, remaining_chars, chars_after = usage_info
            usage_text = f"""Audio Duration: {audio.duration_seconds:.2f} seconds
Characters needed: {chars_needed}
Your character balance: {remaining_chars}
Characters after isolation: {chars_after}"""

            dlg = wx.Dialog(self, title="Usage Information", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            usage_textbox = wx.TextCtrl(dlg, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
            usage_textbox.SetValue(usage_text)

            dlg_sizer = wx.BoxSizer(wx.VERTICAL)
            dlg_sizer.Add(usage_textbox, 1, wx.EXPAND | wx.ALL, 10)
            button_sizer = wx.StdDialogButtonSizer()
            ok_button = wx.Button(dlg, wx.ID_OK)
            button_sizer.AddButton(ok_button)
            button_sizer.Realize()
            dlg_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
            dlg.SetSizer(dlg_sizer)
            dlg.Fit()
            dlg.ShowModal()
            dlg.Destroy()

    def on_convert(self, event):
        if not self.audio_file_path:
            wx.MessageBox("Please select an audio file.", "Error", wx.OK | wx.ICON_ERROR)
            return

        self.loading_dialog = wx.GenericProgressDialog("Isolating Audio", "Please wait...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
        self.loading_dialog.Show()
        future = self.executor.submit(self.isolate_audio_worker) # Use executor
        future.add_done_callback(self.on_isolation_complete)

    def isolate_audio_worker(self):
        headers = {'xi-api-key': self.api_key}
        url = "https://api.elevenlabs.io/v1/audio-isolation"
        try:
            with open(self.audio_file_path, 'rb') as audio_file:
                files = {'audio': audio_file}
                response = requests.post(url, headers=headers, files=files, stream=True)  # Stream the response
                response.raise_for_status()
                total_length = response.headers.get('content-length')
                if total_length is not None:
                    total_length = int(total_length)
                isolated_audio_data = bytearray()
                for chunk in response.iter_content(chunk_size=4096):
                    isolated_audio_data.extend(chunk)
                    if total_length is not None:
                        wx.CallAfter(self.loading_dialog.Update, int(len(isolated_audio_data) / total_length * 100), "Isolating...")

            wx.CallAfter(self.loading_dialog.Update, int(100), newmsg="Isolation Complete.")
            return bytes(isolated_audio_data)
        except requests.exceptions.RequestException as e:
            wx.CallAfter(wx.MessageBox, f"Error isolating audio: {e}", "Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.loading_dialog.Update, int(100), newmsg=f"Error: {e}")
            return None

    def on_isolation_complete(self, future):
        try:
            audio_data = future.result()
            if audio_data:
                wx.CallAfter(self.save_audio, audio_data)
            else:
                wx.CallAfter(wx.MessageBox, "Audio Isolation failed.", "Isolation Failed", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"An error occurred: {e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            wx.CallAfter(self.loading_dialog.Destroy)
            wx.CallAfter(self.convert_button.SetFocus)

    def save_audio(self, audio_data):
        audio = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
        with wx.FileDialog(self, "Save audio file", wildcard="MP3 files (*.mp3)|*.mp3", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            path = fileDialog.GetPath()
            os.environ["PATH"] += os.pathsep + os.path.dirname(self.ffmpeg_path)
            try:
                audio.export(path, format="mp3")
            except Exception as e:
                wx.MessageBox(f"Error saving audio: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def __del__(self):
        self.executor.shutdown(wait=True)