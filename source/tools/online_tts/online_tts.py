import wx
import asyncio
import threading
from msspeech import MSSpeech, MSSpeechError
from tools.online_tts.batch_processor import OnlineTTSBatch
import os
import time
from langdetect import detect, LangDetectException
import random
from gtts import gTTS


class OnlineTTS(wx.Frame):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(620, 520))
        self.msspeech = MSSpeech()
        self.languages = {}
        self.voices = {}
        self.current_language = ""
        self.loop = None
        self.thread = None

        self.init_ui()
        self.fetch_voices()

    def init_ui(self):
        """Initialize the user interface."""
        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(240, 240, 240))
        vbox = wx.BoxSizer(wx.VERTICAL)

        text_label = wx.StaticText(panel, label="Text:")
        text_label.SetForegroundColour(wx.Colour(50, 50, 50))
        vbox.Add(text_label, 0, wx.ALL, 5)

        self.text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.text_ctrl.SetBackgroundColour(wx.WHITE)
        vbox.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        self.auto_detect_cb = wx.CheckBox(panel, label="Auto Detect Language")
        self.auto_detect_cb.SetValue(False)
        self.auto_detect_cb.Bind(wx.EVT_CHECKBOX, self.on_auto_detect_checked)
        vbox.Add(self.auto_detect_cb, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.lang_voice_hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        lang_label = wx.StaticText(panel, label="Language:")
        lang_label.SetForegroundColour(wx.Colour(50, 50, 50))
        self.lang_combo = wx.ComboBox(panel, style=wx.CB_READONLY)
        self.lang_combo.SetBackgroundColour(wx.WHITE)
        self.lang_combo.Bind(wx.EVT_COMBOBOX, self.on_language_selected)
        hbox1.Add(lang_label, 0, wx.RIGHT, 8)
        hbox1.Add(self.lang_combo, 1)
        self.lang_voice_hbox.Add(hbox1, 1)

        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        voice_label = wx.StaticText(panel, label="Voice:")
        voice_label.SetForegroundColour(wx.Colour(50, 50, 50))
        self.voice_combo = wx.ComboBox(panel, style=wx.CB_READONLY)
        self.voice_combo.SetBackgroundColour(wx.WHITE)
        hbox2.Add(voice_label, 0, wx.RIGHT, 8)
        hbox2.Add(self.voice_combo, 1)
        self.lang_voice_hbox.Add(hbox2, 1)
        vbox.Add(self.lang_voice_hbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.rate_spin, rate_box = self.create_spin(panel, "Rate:", -100, 100, 0)
        vbox.Add(rate_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.pitch_spin, pitch_box = self.create_spin(panel, "Pitch:", -100, 100, 0)
        vbox.Add(pitch_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.volume_slider, volume_box = self.create_slider(panel, "Volume:", 1, 100, 100)
        vbox.Add(volume_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        generate_btn = wx.Button(panel, label="Generate Speech")
        generate_btn.SetBackgroundColour(wx.Colour(100, 150, 255))
        generate_btn.SetForegroundColour(wx.WHITE)
        generate_btn.Bind(wx.EVT_BUTTON, self.on_generate)
        vbox.Add(generate_btn, 0, wx.ALL | wx.CENTER, 10)

        batch_button = wx.Button(panel, label="Batch Processing")
        batch_button.SetBackgroundColour(wx.Colour(255, 182, 193))  # Light Pink
        batch_button.SetForegroundColour(wx.BLACK)
        batch_button.Bind(wx.EVT_BUTTON, self.on_batch_process)
        vbox.Add(batch_button, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(vbox)
        self.Centre()


    def create_spin(self, parent, label_text, min_val, max_val, default_val):
        """Creates a wx.SpinCtrl with a label."""
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(parent, label=label_text)
        label.SetForegroundColour(wx.Colour(50, 50, 50))
        hbox.Add(label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)

        spin = wx.SpinCtrl(parent, value=str(default_val), min=min_val, max=max_val)
        hbox.Add(spin, 1)
        return spin, hbox

    def create_slider(self, parent, label_text, min_val, max_val, default_val):
        """Creates a slider with a label."""
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(parent, label=label_text)
        label.SetForegroundColour(wx.Colour(50, 50, 50))
        hbox.Add(label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)

        slider = wx.Slider(parent, value=default_val, minValue=min_val, maxValue=max_val)
        hbox.Add(slider, 1)
        return slider, hbox

    def fetch_voices(self):
        """Fetches the list of voices from the msspeech library."""
        def run_in_thread():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                voices_list = self.loop.run_until_complete(self.msspeech.get_voices_list())
                wx.CallAfter(self.process_voices, voices_list)
            except Exception as e:
                wx.CallAfter(wx.MessageBox, f"Error fetching voices: {e}", "Error", wx.OK | wx.ICON_ERROR)
            finally:
                self.loop.close()
                self.loop = None
                wx.CallAfter(loading_dlg.Destroy)

        loading_dlg = wx.ProgressDialog("Fetching Voices", "Loading voices...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
        loading_dlg.Pulse()

        self.thread = threading.Thread(target=run_in_thread)
        self.thread.start()

    def process_voices(self, voices_list):
        """Processes the fetched voices and populates the language and voice comboboxes."""
        for voice in voices_list:
            lang_code = voice["Locale"]
            if lang_code not in self.languages:
                lang_name = voice["FriendlyName"].split("-")[-1].strip()
                self.languages[lang_code] = lang_name

            if lang_code not in self.voices:
                self.voices[lang_code] = []
            self.voices[lang_code].append(voice)

        sorted_languages = sorted(self.languages.items(), key=lambda item: item[1])
        self.lang_combo.SetItems([lang_name for lang_code, lang_name in sorted_languages])
        # Set initial selection
        if sorted_languages:
            self.lang_combo.SetSelection(0)
            self.on_language_selected(None)

    def on_language_selected(self, event):
        """Handles language selection, updating the voice combobox."""
        selected_language_name = self.lang_combo.GetStringSelection()
        self.current_language = ""
        for code, name in self.languages.items():
            if name == selected_language_name:
                self.current_language = code
                break
        if self.current_language:
            voices_for_language = self.voices[self.current_language]
            voice_names = [v["FriendlyName"].split("-")[0].strip() for v in voices_for_language]
            self.voice_combo.SetItems(voice_names)
            if voice_names:
                self.voice_combo.SetValue(voice_names[0])

    def on_auto_detect_checked(self, event):
        """Handles the auto-detect checkbox, showing/hiding language and voice selection."""
        is_checked = self.auto_detect_cb.IsChecked()
        self.lang_voice_hbox.ShowItems(not is_checked)
        self.Layout()

    def on_generate(self, event):
        """Handles speech generation, delegating to specific methods."""
        text = self.text_ctrl.GetValue()
        if not text.strip():
            wx.MessageBox("Please enter some text to speak.", "Error", wx.OK | wx.ICON_WARNING)
            return

        if self.auto_detect_cb.IsChecked():
            self.generate_auto_detect(text)
        else:
            if not self.current_language or not self.voice_combo.GetStringSelection():
                wx.MessageBox("Please select a language and a voice.", "Error", wx.OK | wx.ICON_WARNING)
                return
            self.generate_manual(text)

    def on_batch_process(self, event):
        """Opens the batch processing dialog."""
        batch_dlg = OnlineTTSBatch(self, self.generate_speech_for_batch)
        batch_dlg.ShowModal()
        batch_dlg.Destroy()

    def generate_speech_for_batch(self, text, filepath):
        """Generates speech for a single item (called from batch processing)."""
        if self.auto_detect_cb.IsChecked():
             return self.generate_auto_detect_batch(text, filepath)
        else:
            return self.generate_manual_batch(text, filepath)

    def generate_manual(self, text):
        """Generates speech with manually selected language and voice."""
        selected_voice_name = self.voice_combo.GetStringSelection()
        selected_voice = None
        for voice in self.voices[self.current_language]:
            if voice["FriendlyName"].startswith(selected_voice_name):
                selected_voice = voice["ShortName"]
                break

        if not selected_voice:
            wx.MessageBox("Could not find the selected voice.  Please try again.", "Error", wx.OK | wx.ICON_ERROR)
            return

        rate = self.rate_spin.GetValue()
        pitch = self.pitch_spin.GetValue()
        volume = self.volume_slider.GetValue() / 100

        with wx.FileDialog(self, "Save Speech As", wildcard="MP3 files (*.mp3)|*.mp3", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            filepath = fileDialog.GetPath()

        def run_generation():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            try:
                self.loop.run_until_complete(self.msspeech.set_voice(selected_voice))
                self.loop.run_until_complete(self.msspeech.set_rate(rate))
                self.loop.run_until_complete(self.msspeech.set_pitch(pitch))
                self.loop.run_until_complete(self.msspeech.set_volume(volume))
                num_bytes = self.loop.run_until_complete(self.msspeech.synthesize(text, filepath))
                if num_bytes > 0:
                    wx.CallAfter(wx.MessageBox, "Speech generated successfully.", "Success", wx.OK | wx.ICON_INFORMATION)
            except MSSpeechError as e:
                 wx.CallAfter(wx.MessageBox, f"MSSpeech Error: {e}", "Error", wx.OK | wx.ICON_ERROR)
            except Exception as e:
                wx.CallAfter(wx.MessageBox, f"An unexpected error occurred: {e}", "Error", wx.OK | wx.ICON_ERROR)

            finally:
                self.loop.close()
                self.loop = None
                wx.CallAfter(loading_dlg.Destroy)

        loading_dlg = wx.ProgressDialog("Generating Speech", "Generating...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_AUTO_HIDE)

        self.thread = threading.Thread(target=run_generation)
        self.thread.start()
        while self.thread.is_alive():
            if loading_dlg.WasCancelled():
                self.thread.join(0)
                loading_dlg.Destroy()
                return
            wx.Yield()


    def generate_auto_detect(self, text):
        """Generates speech with automatically detected language."""
        try:
            detected_lang = detect(text)
        except LangDetectException:
            wx.MessageBox("Could not detect the language.", "Error", wx.OK | wx.ICON_ERROR)
            return

        with wx.FileDialog(self, "Save Speech As", wildcard="MP3 files (*.mp3)|*.mp3", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            filepath = fileDialog.GetPath()

        def run_auto_generation():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            try:
                language_found = False
                for lang_code in self.languages:
                    if lang_code.startswith(detected_lang):
                        language_found = True
                        voices_for_lang = self.voices[lang_code]
                        selected_voice = random.choice(voices_for_lang)["ShortName"]

                        self.loop.run_until_complete(self.msspeech.set_voice(selected_voice))
                        self.loop.run_until_complete(self.msspeech.set_rate(self.rate_spin.GetValue()))
                        self.loop.run_until_complete(self.msspeech.set_pitch(self.pitch_spin.GetValue()))
                        self.loop.run_until_complete(self.msspeech.set_volume(self.volume_slider.GetValue() / 100))
                        num_bytes = self.loop.run_until_complete(self.msspeech.synthesize(text, filepath))
                        if num_bytes > 0:
                            wx.CallAfter(wx.MessageBox, "Speech generated successfully (MSSpeech).", "Success", wx.OK | wx.ICON_INFORMATION)
                        break  # Exit loop once a suitable language is found

                if not language_found:
                    # Fallback to gTTS
                    try:
                        tts = gTTS(text=text, lang=detected_lang, slow=False)
                        tts.save(filepath)
                        wx.CallAfter(wx.MessageBox, "Speech generated successfully (gTTS).", "Success", wx.OK | wx.ICON_INFORMATION)
                    except Exception as gtts_error:
                        wx.CallAfter(wx.MessageBox, f"gTTS Error: {gtts_error}", "Error", wx.OK | wx.ICON_ERROR)

            except MSSpeechError as e:
                wx.CallAfter(wx.MessageBox, f"MSSpeech Error: {e}", "Error", wx.OK | wx.ICON_ERROR)
            except Exception as e:
                 wx.CallAfter(wx.MessageBox, f"An unexpected error occurred: {e}", "Error", wx.OK | wx.ICON_ERROR)
            finally:
                self.loop.close()
                self.loop = None
                wx.CallAfter(loading_dlg.Destroy)

        loading_dlg = wx.ProgressDialog("Generating Speech", "Generating...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_AUTO_HIDE)

        self.thread = threading.Thread(target=run_auto_generation)
        self.thread.start()
        while self.thread.is_alive():
            if loading_dlg.WasCancelled():
                self.thread.join(0)
                loading_dlg.Destroy()
                return
            wx.Yield()

    def generate_manual_batch(self, text, filepath):
        """Generates speech with manually selected language and voice."""
        selected_voice_name = self.voice_combo.GetStringSelection()
        selected_voice = None
        for voice in self.voices[self.current_language]:
            if voice["FriendlyName"].startswith(selected_voice_name):
                selected_voice = voice["ShortName"]
                break

        if not selected_voice:
            wx.MessageBox("Could not find the selected voice.  Please try again.", "Error", wx.OK | wx.ICON_ERROR)
            return False

        rate = self.rate_spin.GetValue()
        pitch = self.pitch_spin.GetValue()
        volume = self.volume_slider.GetValue() / 100

        def run_generation():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            success = True  # Flag for return value

            try:
                self.loop.run_until_complete(self.msspeech.set_voice(selected_voice))
                self.loop.run_until_complete(self.msspeech.set_rate(rate))
                self.loop.run_until_complete(self.msspeech.set_pitch(pitch))
                self.loop.run_until_complete(self.msspeech.set_volume(volume))
                num_bytes = self.loop.run_until_complete(self.msspeech.synthesize(text, filepath))
                if num_bytes > 0:
                    pass
                else:
                    success = False

            except MSSpeechError as e:
                wx.CallAfter(wx.MessageBox, f"MSSpeech Error: {e}", "Error", wx.OK | wx.ICON_ERROR)
                success = False
            except Exception as e:
                wx.CallAfter(wx.MessageBox, f"An unexpected error occurred: {e}", "Error", wx.OK | wx.ICON_ERROR)
                success = False
            finally:
                self.loop.close()
                self.loop = None

            return success

        success = run_generation()
        return success

    def generate_auto_detect_batch(self, text, filepath):
        """Generates speech with automatically detected language."""
        try:
            detected_lang = detect(text)
        except LangDetectException:
            wx.MessageBox("Could not detect the language.", "Error", wx.OK | wx.ICON_ERROR)
            return False

        def run_auto_generation():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            success = True

            try:
                language_found = False
                for lang_code in self.languages:
                    if lang_code.startswith(detected_lang):
                        language_found = True
                        voices_for_lang = self.voices[lang_code]
                        selected_voice = random.choice(voices_for_lang)["ShortName"]

                        self.loop.run_until_complete(self.msspeech.set_voice(selected_voice))
                        self.loop.run_until_complete(self.msspeech.set_rate(self.rate_spin.GetValue()))
                        self.loop.run_until_complete(self.msspeech.set_pitch(self.pitch_spin.GetValue()))
                        self.loop.run_until_complete(self.msspeech.set_volume(self.volume_slider.GetValue() / 100))

                        num_bytes = self.loop.run_until_complete(self.msspeech.synthesize(text, filepath))
                        if num_bytes > 0:
                           pass
                        else:
                            success = False
                        break

                if not language_found:
                    # Fallback to gTTS
                    try:
                        tts = gTTS(text=text, lang=detected_lang, slow=False)
                        tts.save(filepath)
                    except Exception as gtts_error:
                        wx.CallAfter(wx.MessageBox, f"gTTS Error: {gtts_error}", "Error", wx.OK | wx.ICON_ERROR)
                        success = False

            except MSSpeechError as e:
                wx.CallAfter(wx.MessageBox, f"MSSpeech Error: {e}", "Error", wx.OK | wx.ICON_ERROR)
                success = False
            except Exception as e:
                 wx.CallAfter(wx.MessageBox, f"An unexpected error occurred: {e}", "Error", wx.OK | wx.ICON_ERROR)
                 success = False
            finally:
                self.loop.close()
                self.loop = None
            return success

        success = run_auto_generation()
        return success