import wx
import requests
import concurrent.futures
import io
import json
from pydub import AudioSegment
import os

class SoundGeneration(wx.Panel):
    def __init__(self, parent, api_key, ffmpeg_path):
        super().__init__(parent)
        self.api_key = api_key
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.ffmpeg_path= ffmpeg_path

        text_label = wx.StaticText(self, label="Enter Text prompt:")
        self.text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE)

        voice_settings_group = wx.StaticBox(self, -1, "Voice Settings")
        voice_settings_sizer = wx.StaticBoxSizer(voice_settings_group, wx.VERTICAL)
        self.auto_duration_checkbox = wx.CheckBox(self, label="Use Automatic Duration")
        self.auto_duration_checkbox.SetValue(True)
        self.auto_duration_checkbox.Bind(wx.EVT_CHECKBOX, self.on_auto_duration_change)

        manual_duration_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.duration_spin_label = wx.StaticText(self, label="Duration (seconds):")
        self.duration_spin = wx.SpinCtrl(self, min=1, max=22, initial=1)
        manual_duration_sizer.Add(self.duration_spin_label, 0, wx.ALL, 5)  # Add spinctrl label
        manual_duration_sizer.Add(self.duration_spin, 0, wx.ALL, 5)
        self.duration_spin.Hide()
        self.duration_spin_label.Hide()

        prompt_influence_sizer = wx.BoxSizer(wx.VERTICAL)
        prompt_influence_label = wx.StaticText(self, label="Prompt Influence:")
        self.prompt_influence_slider = wx.Slider(self, value=30, minValue=0, maxValue=100, style=wx.SL_HORIZONTAL)
        prompt_influence_sizer.Add(prompt_influence_label, 0, wx.ALIGN_CENTER)
        prompt_influence_sizer.Add(self.prompt_influence_slider, 1, wx.EXPAND)

        voice_settings_sizer.Add(self.auto_duration_checkbox, 0, wx.ALL, 5)
        voice_settings_sizer.Add(manual_duration_sizer, 0, wx.ALL, 5)
        voice_settings_sizer.Add(prompt_influence_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.generate_button = wx.Button(self, label="Generate")
        self.generate_button.Bind(wx.EVT_BUTTON, self.on_generate)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(text_label, 0, wx.ALL, 5)
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(voice_settings_sizer, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.generate_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        self.SetSizer(sizer)
        self.Layout()


    def on_auto_duration_change(self, event):
        if self.auto_duration_checkbox.GetValue():
            self.duration_spin.Hide()
            self.duration_spin_label.Hide()
        else:
            self.duration_spin.Show()
            self.duration_spin_label.Show()
        self.Layout()

    def on_generate(self, event):
        text = self.text_ctrl.GetValue()
        if not text:
            wx.MessageBox("Please enter some text.", "Error", wx.OK | wx.ICON_ERROR)
            return

        self.loading_dialog = wx.GenericProgressDialog("Generating Sound", "Please wait...", maximum=100, parent=self,
                                                      style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
        self.loading_dialog.Show()
        future = self.executor.submit(self.generate_sound_worker, text)
        future.add_done_callback(self.on_generation_complete)

    def generate_sound_worker(self, text):  # Worker function
        headers = {'xi-api-key': self.api_key, 'Content-Type': 'application/json'}
        url = "https://api.elevenlabs.io/v1/sound-generation"

        if self.auto_duration_checkbox.GetValue():
            duration_seconds = None  # Let API handle it
        else:
            duration_seconds = self.duration_spin.GetValue()
        prompt_influence = self.prompt_influence_slider.GetValue() / 100.0
        data = {"text": text}

        if duration_seconds is not None:
            data["duration_seconds"] = duration_seconds
        data["prompt_influence"] = prompt_influence

        try:
            with requests.post(url, headers=headers, json=data, stream=True) as response:
                response.raise_for_status()

                generated_audio_data = bytearray()
                for chunk in response.iter_content(chunk_size=4096):
                    generated_audio_data.extend(chunk)
            wx.CallAfter(self.loading_dialog.Update, 100, newmsg="Generation Complete.")
            return bytes(generated_audio_data)

        except requests.exceptions.RequestException as e:
            wx.CallAfter(wx.MessageBox, f"Error generating sound: {e}", "Generation failed", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.loading_dialog.Update, 100, newmsg=f"Error: {e}")
            return None

    def on_generation_complete(self, future):
        try:
            audio_data = future.result()
            if audio_data:
                wx.CallAfter(self.save_audio, audio_data)
            else:
                wx.CallAfter(wx.MessageBox, "Sound generation failed.", "Generation Failed", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"An error occurred: {e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
             wx.CallAfter(self.loading_dialog.Destroy)

    def save_audio(self, audio_data):
        audio = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
        with wx.FileDialog(None, "Save audio file", wildcard="MP3 files (*.mp3)|*.mp3", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
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