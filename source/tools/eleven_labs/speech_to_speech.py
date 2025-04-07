import wx
from gui.custom_controls import CustomSlider
import requests
import concurrent.futures
import io
import json
from pydub import AudioSegment
import os


class ElevenLabsSTS(wx.Panel):
    def __init__(self, parent, api_key, ffmpeg_path):
        super().__init__(parent)
        self.api_key = api_key
        self.voices = []
        self.sts_models = {}
        self.audio_file_path = ""
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.ffmpeg_path= ffmpeg_path
        self.voice_settings = {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": False
        }

        file_path_label = wx.StaticText(self, label="Audio File Path:")
        file_path_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.file_path_textbox = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        browse_button = wx.Button(self, label="Browse")
        browse_button.Bind(wx.EVT_BUTTON, self.on_browse)
        file_path_sizer.Add(self.file_path_textbox, 1, wx.EXPAND | wx.ALL, 5)
        file_path_sizer.Add(browse_button, 0, wx.ALL, 5)

        self.voice_label = wx.StaticText(self, label="Select Voice:")
        self.voice_combobox = wx.ComboBox(self)
        self.voice_combobox.Bind(wx.EVT_COMBOBOX, self.on_voice_select)
        self.model_label = wx.StaticText(self, label="Select Model:")
        self.model_combobox = wx.ComboBox(self)

        self.voice_settings_group = wx.StaticBox(self, -1, "Voice Settings")
        voice_settings_sizer = wx.StaticBoxSizer(self.voice_settings_group, wx.VERTICAL)

        stability_sizer = wx.BoxSizer(wx.VERTICAL)
        stability_label = wx.StaticText(self, label="Stability:")
        self.stability_slider = CustomSlider(self, value=50, minValue=0, maxValue=100, style=wx.SL_HORIZONTAL)
        stability_sizer.Add(stability_label, 0, wx.ALIGN_CENTER)
        stability_sizer.Add(self.stability_slider, 1, wx.EXPAND)
        voice_settings_sizer.Add(stability_sizer, 1, wx.EXPAND | wx.ALL, 5)

        similarity_sizer = wx.BoxSizer(wx.VERTICAL)
        similarity_label = wx.StaticText(self, label="Similarity:")
        self.similarity_slider = CustomSlider(self, value=75, minValue=0, maxValue=100, style=wx.SL_HORIZONTAL)
        similarity_sizer.Add(similarity_label, 0, wx.ALIGN_CENTER)
        similarity_sizer.Add(self.similarity_slider, 1, wx.EXPAND)
        voice_settings_sizer.Add(similarity_sizer, 1, wx.EXPAND | wx.ALL, 5)

        style_exaggeration_sizer = wx.BoxSizer(wx.VERTICAL)
        style_exaggeration_label = wx.StaticText(self, label="Style Exaggeration:")
        self.style_exaggeration_slider = CustomSlider(self, value=0, minValue=0, maxValue=100, style=wx.SL_HORIZONTAL)
        style_exaggeration_sizer.Add(style_exaggeration_label, 0, wx.ALIGN_CENTER)
        style_exaggeration_sizer.Add(self.style_exaggeration_slider, 1, wx.EXPAND)
        voice_settings_sizer.Add(style_exaggeration_sizer, 1, wx.EXPAND | wx.ALL, 5)

        self.speaker_boost_checkbox = wx.CheckBox(self, label="Use Speaker Boost")
        voice_settings_sizer.Add(self.speaker_boost_checkbox, 0, wx.ALL, 5)

        self.remove_noise_checkbox = wx.CheckBox(self, label="Remove Background Noise")
        self.enable_logging_checkbox = wx.CheckBox(self, label="Enable Logging")
        self.enable_logging_checkbox.SetValue(True)

        self.convert_button = wx.Button(self, label="Convert Speech")
        self.convert_button.Bind(wx.EVT_BUTTON, self.on_convert)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(file_path_label, 0, wx.ALL, 5)
        sizer.Add(file_path_sizer, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.voice_label, 0, wx.ALL, 5)
        sizer.Add(self.voice_combobox, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.model_label, 0, wx.ALL, 5)
        sizer.Add(self.model_combobox, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(voice_settings_sizer, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.remove_noise_checkbox, 0, wx.ALL, 5)
        sizer.Add(self.enable_logging_checkbox, 0, wx.ALL, 5)
        sizer.Add(self.convert_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        self.SetSizer(sizer)
        self.Layout()

        # Fetch voices and models using the executor
        self.executor.submit(self.fetch_voices).add_done_callback(self.on_voices_fetched)
        self.executor.submit(self.fetch_sts_models).add_done_callback(self.on_models_fetched)


    def fetch_voices(self):
        headers = {'xi-api-key': self.api_key}
        response = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers)
        response.raise_for_status()  # Raise HTTPError for bad responses (important for error handling)
        return response.json()['voices']

    def on_voices_fetched(self, future):
        try:
            self.voices = future.result()
            voice_labels = [
                f"{voice['name']} (Gender: {voice.get('labels', {}).get('gender', 'Unknown')}, Age: {voice.get('labels', {}).get('age', 'Unknown')})"
                for voice in self.voices
            ]
            self.voice_combobox.SetItems(voice_labels)
            if voice_labels:
                self.voice_combobox.SetSelection(0)
        except requests.exceptions.RequestException as e:
            wx.MessageBox(f"Error fetching voices: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_voice_select(self, event):
        selected_voice_index = self.voice_combobox.GetSelection()
        if selected_voice_index != -1:
            voice_id = self.voices[selected_voice_index]['voice_id']
        future = self.executor.submit(self.fetch_voice_settings, voice_id)
        future.add_done_callback(self.on_voice_settings_received) 

    def fetch_voice_settings(self, voice_id):
        url = f"https://api.elevenlabs.io/v1/voices/{voice_id}/settings"
        headers = {'xi-api-key': self.api_key}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            wx.CallAfter(wx.MessageBox, f"Error getting voice settings: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_voice_settings_received(self, future):
        try:
            result = future.result()
            if result:
                wx.CallAfter(self.update_ui_with_settings, result)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"An error occurred: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def update_ui_with_settings(self, settings):
        self.stability_slider.SetValue(int(settings["stability"] * 100))
        self.similarity_slider.SetValue(int(settings["similarity_boost"] * 100))
        self.style_exaggeration_slider.SetValue(int(settings["style"] * 100))
        if "use_speaker_boost" in settings:
            self.speaker_boost_checkbox.SetValue(settings["use_speaker_boost"])
        self.voice_settings.update(settings)

    def fetch_sts_models(self): 
        headers = {'xi-api-key': self.api_key}
        response = requests.get("https://api.elevenlabs.io/v1/models", headers=headers)
        response.raise_for_status()
        models_data = response.json()
        tts_models = {}
        for model in models_data:
            if model.get("can_do_voice_conversion"):
                model_name = model["name"]
                model_id = model["model_id"]
                tts_models[model_name] = model_id  # Store in the dictionary
        return tts_models

    def on_models_fetched(self, future): 
        try:
            self.sts_models = future.result()
            self.model_combobox.SetItems(list(self.sts_models.keys()))
            if self.sts_models:
                self.model_combobox.SetSelection(0)
            else:
                wx.MessageBox("No Text-to-Speech models found.", "No Models", wx.OK | wx.ICON_INFORMATION)
        except requests.exceptions.RequestException as e:
             wx.MessageBox(f"Error fetching models: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_browse(self, event):
        with wx.FileDialog(self, "Choose audio file", wildcard="Audio files (*.mp3;*.wav)|*.mp3;*.wav", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_OK:
                self.audio_file_path = fileDialog.GetPath()
                self.file_path_textbox.SetValue(self.audio_file_path)

    def on_convert(self, event):
        if not self.audio_file_path:
            wx.MessageBox("Please select an audio file.", "Error", wx.OK | wx.ICON_ERROR)
            return

        selected_voice_index = self.voice_combobox.GetSelection()
        if selected_voice_index == -1:
            wx.MessageBox("Please select a voice.", "Error", wx.OK | wx.ICON_ERROR)
            return
        voice_id = self.voices[selected_voice_index]["voice_id"]
        selected_model_index = self.model_combobox.GetSelection()
        if selected_model_index == -1:
            wx.MessageBox("Please select a model.", "Error", wx.OK | wx.ICON_ERROR)
            return

        model_id = self.sts_models[self.model_combobox.GetString(selected_model_index)]
        self.loading_dialog = wx.ProgressDialog("Converting Speech", "Please wait...", maximum=100, parent=self,
                                                      style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
        self.loading_dialog.Show()

        future = self.executor.submit(self.convert_speech_worker, voice_id, model_id)
        future.add_done_callback(self.on_conversion_complete)

    def convert_speech_worker(self, voice_id, model_id):
        headers = {'xi-api-key': self.api_key}
        url = f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}"
        data = {
            'model_id': model_id,
            'voice_settings': json.dumps(self.voice_settings),
            "remove_background_noise": self.remove_noise_checkbox.GetValue()
        }

        params = {
            "enable_logging": self.enable_logging_checkbox.GetValue(),
        }

        try:
            with open(self.audio_file_path, 'rb') as audio_file:
                files = {'audio': audio_file}
                with requests.post(url, headers=headers, params=params, data=data, files=files, stream=True) as response:
                    response.raise_for_status()
                    total_length = response.headers.get('content-length')
                    if total_length is not None:
                        total_length = int(total_length)

                    converted_audio_data = bytearray()
                    for chunk in response.iter_content(chunk_size=4096):
                        converted_audio_data.extend(chunk)
                        if total_length is not None:
                            wx.CallAfter(self.loading_dialog.Update, int(len(converted_audio_data) / total_length * 100),
                                        newmsg="Converting...")

            wx.CallAfter(self.loading_dialog.Update, int(100), newmsg="Conversion Complete.")
            return bytes(converted_audio_data)

        except requests.exceptions.RequestException as e:
            print(f"Conversion error: {e}")
            wx.CallAfter(self.loading_dialog.Update, int(100), newmsg=f"Conversion Error: {e}")
            return None

    def on_conversion_complete(self, future):
        try:
            audio_data = future.result()
            if audio_data:
                wx.CallAfter(self.save_audio, audio_data)
            else:
                wx.CallAfter(wx.MessageBox, "Speech conversion failed.", "Conversion Failed", wx.OK | wx.ICON_ERROR)
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