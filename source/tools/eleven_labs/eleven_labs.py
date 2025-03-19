import wx
import app_vars
from gui.custom_controls import CustomSlider
from tools.eleven_labs.speech_to_speech import ElevenLabsSTS
from tools.eleven_labs.audio_isolator import AudioIsolation
from tools.eleven_labs.sound_generator import SoundGeneration
import os
import json
import requests
import concurrent.futures
import io
from pydub import AudioSegment


class ElevenLabsTTS(wx.Panel):
    def __init__(self, parent, api_key, ffmpeg_path):
        super().__init__(parent)
        self.api_key = api_key
        self.voices = []
        self.tts_models = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.ffmpeg_path= ffmpeg_path
        self.voice_settings = {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": False
        }

        self.text_label = wx.StaticText(self, label="Enter Text:")
        self.text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        self.voice_label = wx.StaticText(self, label="Select Voice:")
        self.voice_combobox = wx.ComboBox(self)
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

        self.usage_button = wx.Button(self, label="Usage Info")
        self.generate_button = wx.Button(self, label="Generate Audio")

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.text_label, 0, wx.ALL, 5)
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.voice_label, 0, wx.ALL, 5)
        sizer.Add(self.voice_combobox, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.model_label, 0, wx.ALL, 5)  # Added to layout
        sizer.Add(self.model_combobox, 0, wx.EXPAND | wx.ALL, 5)  # Added to layout
        sizer.Add(voice_settings_sizer, 0, wx.ALL | wx.EXPAND, 5) # Add group to main sizer
        sizer.Add(self.usage_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        sizer.Add(self.generate_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        self.SetSizer(sizer)
        self.Layout()

        # Event bindings
        self.generate_button.Bind(wx.EVT_BUTTON, self.on_generate)
        self.voice_combobox.Bind(wx.EVT_COMBOBOX, self.on_voice_select)
        self.usage_button.Bind(wx.EVT_BUTTON, self.on_usage_info)

        # Fetch voices and models using the executor
        self.executor.submit(self.fetch_voices).add_done_callback(self.on_voices_fetched)
        self.executor.submit(self.fetch_models).add_done_callback(self.on_models_fetched)


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

    def fetch_models(self): 
        headers = {'xi-api-key': self.api_key}
        response = requests.get("https://api.elevenlabs.io/v1/models", headers=headers)
        response.raise_for_status()
        models_data = response.json()
        tts_models = {}
        for model in models_data:
            if model.get("can_do_text_to_speech"):
                model_name = model["name"]
                model_id = model["model_id"]
                tts_models[model_name] = model_id  # Store in the dictionary
        return tts_models

    def on_models_fetched(self, future): 
        try:
            self.tts_models = future.result()
            self.model_combobox.SetItems(list(self.tts_models.keys()))
            if self.tts_models:
                self.model_combobox.SetSelection(0)
            else:
                wx.MessageBox("No Text-to-Speech models found.", "No Models", wx.OK | wx.ICON_INFORMATION)
        except requests.exceptions.RequestException as e:
             wx.MessageBox(f"Error fetching models: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_generate(self, event):
        text = self.text_ctrl.GetValue()
        selected_voice_index = self.voice_combobox.GetSelection()
        selected_model_index = self.model_combobox.GetSelection()
        if selected_voice_index != -1 and selected_model_index != -1:
            voice_id = self.voices[selected_voice_index]['voice_id']

            selected_model_name = self.model_combobox.GetString(selected_model_index)  # Get the model *name*
            model_id = self.tts_models.get(selected_model_name)  # Get model ID from name
            if model_id:
                self.convert_text_to_speech(text, voice_id, model_id)
        elif selected_voice_index == -1:
            wx.MessageBox("Please select a voice.", "Error", wx.OK | wx.ICON_ERROR)
        elif selected_model_index == -1:
            wx.MessageBox("Please select a model.", "Error", wx.OK | wx.ICON_ERROR)

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

    def on_usage_info(self, event):
        future = self.executor.submit(self.fetch_subscription_info)
        future.add_done_callback(self.show_usage_dialog)

    def fetch_subscription_info(self):
        headers = {'xi-api-key': self.api_key}
        url = "https://api.elevenlabs.io/v1/user/subscription"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def show_usage_dialog(self, future):
        try:
            subscription_info = future.result()
            if subscription_info:
                wx.CallAfter(self.create_and_show_dialog, subscription_info)
        except requests.exceptions.RequestException as e:
            wx.MessageBox(f"Error getting usage info: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def create_and_show_dialog(self, subscription_info):
        text = self.text_ctrl.GetValue()
        char_count = len(text)
        remaining_chars = subscription_info.get("character_count", 0)
        chars_after = remaining_chars - char_count if remaining_chars is not None else "Unknown"

        usage_text = f"""This will take {char_count} characters, While You have {remaining_chars} characters in your account.
After conversion: You will have {chars_after} characters remaining."""

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

    def convert_text_to_speech(self, text, voice_id, model_id):
        headers = {'xi-api-key': self.api_key, 'Content-Type': 'application/json'}
        data = {
            "text": text,
            "model_id": model_id,
            "voice_settings": self.voice_settings.copy()
        }

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        self.download_audio(url, headers, data)

    def download_audio(self, url, headers, data):
        self.loading_dialog = wx.GenericProgressDialog(
            "Downloading Audio", "Please wait...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        self.loading_dialog.Show()
        future = self.executor.submit(self.download_audio_worker, url, headers, data)
        future.add_done_callback(self.on_audio_downloaded)

    def download_audio_worker(self, url, headers, data):
        try:
            with requests.post(url, headers=headers, json=data, stream=True) as response:
                response.raise_for_status()
                total_length = response.headers.get('content-length')
                if total_length is not None:
                    total_length = int(total_length)
                audio_data = bytearray()
                for chunk in response.iter_content(chunk_size=4096):
                    audio_data.extend(chunk)

                wx.CallAfter(self.loading_dialog.Update, int(100), newmsg="Download Complete.")
                return bytes(audio_data)
        except requests.exceptions.RequestException as e:
            wx.CallAfter(wx.MessageBox, f"Error downloading audio: {e}", "Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.loading_dialog.Update, int(100), newmsg=f"Error: {e}")
            return None

    def on_audio_downloaded(self, future):
        try:
            audio_data = future.result()
            if audio_data:
                wx.CallAfter(self.save_audio, audio_data)
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
            audio.export(path, format="mp3")

    def __del__(self):
        self.executor.shutdown(wait=True) # Shutdown the executor when the panel is destroyed


class ElevenLabs(wx.Frame):
    def __init__(self, parent, title="ElevenLabs"):
        super().__init__(parent, title=title)
        self.settings_file = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name, "settings.json")
        self.api_key = self.load_api_key()
        self.ffmpeg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg.exe')

        if not self.api_key:
            if wx.MessageBox("ElevenLabs API key not found. Would you like to add it now?", "API Key Missing", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                self.api_key = self.get_api_key_from_user()

        # Initialize UI based on API key presence
        if self.api_key:
            self.create_elevenlabs_ui()
        else:
            self.create_no_api_key_panel()

        self.Centre()
        self.Show()


    def load_api_key(self):
        try:
            with open(self.settings_file, "r") as f:
                settings = json.load(f)
                return settings.get("elevenlabs_api_key")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def get_api_key_from_user(self):
        dlg = wx.TextEntryDialog(self, "Enter your ElevenLabs API key:", "API Key")
        if dlg.ShowModal() == wx.ID_OK:
            api_key = dlg.GetValue()
            try:
                os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
                with open(self.settings_file, "w") as f:
                    json.dump({"elevenlabs_api_key": api_key}, f)
                return api_key
            except OSError as e:
                wx.MessageBox(f"Error saving API key: {e}", "Error", wx.OK | wx.ICON_ERROR)
                return None
        return None

    def create_no_api_key_panel(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        message = wx.StaticText(panel, label="ElevenLabs API key is missing. Please configure it to use this tool.")
        sizer.Add(message, 0, wx.ALL | wx.CENTER, 10)
        panel.SetSizer(sizer)

        frame_sizer = wx.BoxSizer()
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)

    def create_elevenlabs_ui(self):
        notebook = wx.Notebook(self)
        tts_panel = ElevenLabsTTS(notebook, self.api_key, self.ffmpeg_path)
        notebook.AddPage(tts_panel, "Text-to-Speech")
        sts_panel = ElevenLabsSTS(notebook, self.api_key, self.ffmpeg_path)
        notebook.AddPage(sts_panel, "Speech-to-Speech")
        audio_isolation_panel = AudioIsolation(notebook, self.api_key, self.ffmpeg_path)
        notebook.AddPage(audio_isolation_panel, "Audio Isolation") # add audio isolation tab
        sound_generation_panel = SoundGeneration(notebook, self.api_key, self.ffmpeg_path)
        notebook.AddPage(sound_generation_panel, "Sound Effects Generator")

        sizer = wx.BoxSizer()
        sizer.Add(notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)
