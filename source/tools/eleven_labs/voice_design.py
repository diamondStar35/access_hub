import wx
import wx.adv
import requests
import concurrent.futures
import json
import base64
import io
import os
from pydub import AudioSegment
from gui.custom_controls import CustomSlider
from .audio_player import SimplePlayer

class AddVoiceFromPromptDialog(wx.Dialog):
    """
    Dialog for initiating the creation of a new voice using ElevenLabs Voice Design.
    """
    OUTPUT_FORMATS = {
        # User Friendly Name: API Value
        "MP3, 44.1kHz, 192kbps (Default)": "mp3_44100_192",
        "MP3, 44.1kHz, 128kbps": "mp3_44100_128",
        "MP3, 44.1kHz, 96kbps": "mp3_44100_96",
        "MP3, 44.1kHz, 64kbps": "mp3_44100_64",
        "MP3, 44.1kHz, 32kbps": "mp3_44100_32",
        "MP3, 22.05kHz, 32kbps": "mp3_22050_32",
        "PCM, 44.1kHz": "pcm_44100",
        "PCM, 24kHz": "pcm_24000",
        "PCM, 22.05kHz": "pcm_22050",
        "PCM, 16kHz": "pcm_16000",
        "PCM, 8kHz": "pcm_8000",
        "μ-law, 8kHz": "ulaw_8000",
        "A-law, 8kHz": "alaw_8000",
        "Opus, 48kHz, 192kbps": "opus_48000_192",
        "Opus, 48kHz, 128kbps": "opus_48000_128",
        "Opus, 48kHz, 96kbps": "opus_48000_96",
        "Opus, 48kHz, 64kbps": "opus_48000_64",
        "Opus, 48kHz, 32kbps": "opus_48000_32",
    }
    LOUDNESS_QUALITY_SLIDER_STEPS = 40 # (-1 to 1 in steps of 0.05) means 2 / 0.05 = 40 steps
    LOUDNESS_QUALITY_SLIDER_MIN = -1.0
    LOUDNESS_QUALITY_SLIDER_MAX = 1.0
    LOUDNESS_QUALITY_SLIDER_STEP = 0.05

    def __init__(self, parent, api_key, ffmpeg_path):
        super().__init__(parent, title="Add Voice from Prompt", size=(600, 700), # Adjusted size
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.api_key = api_key
        self.ffmpeg_path = ffmpeg_path # Needed for potential audio saving in player
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.progress_dialog = None

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        basic_info_sizer = wx.BoxSizer(wx.VERTICAL)
        name_label = wx.StaticText(panel, label="Voice Name:")
        self.name_text = wx.TextCtrl(panel)
        desc_label = wx.StaticText(panel, label="Voice Description (20-1000 characters):")
        self.desc_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 80))
        self.text_prompt_label = wx.StaticText(panel, label="Text Prompt (100-1000 characters):")
        self.text_prompt_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 100))
        output_format_label = wx.StaticText(panel, label="Output Format for Generated Previews:")
        self.output_format_combo = wx.ComboBox(panel, choices=list(self.OUTPUT_FORMATS.keys()), style=wx.CB_READONLY)
        self.output_format_combo.SetSelection(0)

        basic_info_sizer.Add(name_label, 0, wx.ALL, 5)
        basic_info_sizer.Add(self.name_text, 0, wx.EXPAND | wx.ALL, 5)
        basic_info_sizer.Add(desc_label, 0, wx.ALL, 5)
        basic_info_sizer.Add(self.desc_text, 0, wx.EXPAND | wx.ALL, 5)
        basic_info_sizer.Add(self.text_prompt_label, 0, wx.ALL, 5)
        basic_info_sizer.Add(self.text_prompt_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        basic_info_sizer.Add(output_format_label, 0, wx.ALL, 5)
        basic_info_sizer.Add(self.output_format_combo, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(basic_info_sizer, 0, wx.EXPAND | wx.ALL, 10)

        settings_group = wx.StaticBox(panel, label="Generation Settings")
        settings_sizer = wx.StaticBoxSizer(settings_group, wx.VERTICAL)
        self.auto_generate_checkbox = wx.CheckBox(panel, label="Automatically generate text based on description")
        self.auto_generate_checkbox.Bind(wx.EVT_CHECKBOX, self.on_auto_generate_change)
        settings_sizer.Add(self.auto_generate_checkbox, 0, wx.ALL, 5)

        loudness_sizer = wx.BoxSizer(wx.HORIZONTAL)
        loudness_label = wx.StaticText(panel, label="Loudness:", size=(150,-1))
        initial_loudness_slider_val = int((0.5 - self.LOUDNESS_QUALITY_SLIDER_MIN) / self.LOUDNESS_QUALITY_SLIDER_STEP)
        self.loudness_slider = CustomSlider(panel, value=initial_loudness_slider_val,
                                            minValue=0, maxValue=self.LOUDNESS_QUALITY_SLIDER_STEPS,
                                            style=wx.SL_HORIZONTAL)
        self.loudness_slider.Bind(wx.EVT_SLIDER, lambda event: self.on_loudness_quality_slider_change(event, "Loudness"))
        loudness_sizer.Add(loudness_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        loudness_sizer.Add(self.loudness_slider, 1, wx.EXPAND | wx.RIGHT, 5)
        settings_sizer.Add(loudness_sizer, 0, wx.EXPAND | wx.ALL, 5)

        quality_sizer = wx.BoxSizer(wx.HORIZONTAL)
        quality_label = wx.StaticText(panel, label="Quality:", size=(150,-1))
        initial_quality_slider_val = int((0.9 - self.LOUDNESS_QUALITY_SLIDER_MIN) / self.LOUDNESS_QUALITY_SLIDER_STEP)
        self.quality_slider = CustomSlider(panel, value=initial_quality_slider_val,
                                           minValue=0, maxValue=self.LOUDNESS_QUALITY_SLIDER_STEPS,
                                           style=wx.SL_HORIZONTAL)
        self.quality_slider.Bind(wx.EVT_SLIDER, lambda event: self.on_loudness_quality_slider_change(event, "Quality"))
        quality_sizer.Add(quality_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        quality_sizer.Add(self.quality_slider, 1, wx.EXPAND | wx.RIGHT, 5)
        settings_sizer.Add(quality_sizer, 0, wx.EXPAND | wx.ALL, 5)

        guidance_sizer = wx.BoxSizer(wx.HORIZONTAL)
        guidance_label = wx.StaticText(panel, label="Guidance Scale:", size=(150,-1))
        self.guidance_slider = CustomSlider(panel, value=5, minValue=0, maxValue=100, style=wx.SL_HORIZONTAL)
        guidance_sizer.Add(guidance_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        guidance_sizer.Add(self.guidance_slider, 1, wx.EXPAND | wx.RIGHT, 5)
        settings_sizer.Add(guidance_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(settings_sizer, 0, wx.EXPAND | wx.ALL, 10)

        button_sizer = wx.StdDialogButtonSizer()
        self.generate_button = wx.Button(panel, label="&Generate Voice")
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(self.generate_button)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()

        main_sizer.AddStretchSpacer(1)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        self.CentreOnParent()
        self.generate_button.Bind(wx.EVT_BUTTON, self.on_generate_previews)

    def on_auto_generate_change(self, event):
        """Toggles the visibility of the text prompt input and updates label."""
        is_auto = self.auto_generate_checkbox.GetValue()
        show_text_prompt = not is_auto
        self.text_prompt_label.Show(show_text_prompt)
        self.text_prompt_ctrl.Show(show_text_prompt)
        if is_auto:
            self.text_prompt_label.SetLabel("Text Prompt (Auto-generated based on description):")
        else:
            self.text_prompt_label.SetLabel("Text Prompt (100-1000 characters):")

        if event:
             self.Layout()
             self.Fit()

    def on_loudness_quality_slider_change(self, event, slider_name):
        """Handles updates for sliders mapping int to float -1 to 1."""
        slider = event.GetEventObject()
        slider_value = event.GetInt()
        float_value = self.map_slider_to_float(slider_value)
        slider.SetToolTip(f"{slider_name}: {float_value:.2f}")
        event.Skip()

    def map_slider_to_float(self, slider_value):
        """Converts slider integer (0-40) to float (-1.0 to 1.0)."""
        float_val = self.LOUDNESS_QUALITY_SLIDER_MIN + (slider_value * self.LOUDNESS_QUALITY_SLIDER_STEP)
        return max(self.LOUDNESS_QUALITY_SLIDER_MIN, min(self.LOUDNESS_QUALITY_SLIDER_MAX, float_val))

    def get_selected_output_format(self):
        """Gets the API value for the selected output format."""
        selected_index = self.output_format_combo.GetSelection()
        if selected_index == wx.NOT_FOUND:
            return self.OUTPUT_FORMATS[list(self.OUTPUT_FORMATS.keys())[0]]
        selected_key = self.output_format_combo.GetString(selected_index)
        return self.OUTPUT_FORMATS.get(selected_key, "mp3_44100_192")

    def validate_inputs(self):
        """Checks if required inputs meet API criteria."""
        voice_name = self.name_text.GetValue().strip()
        if not voice_name:
            wx.MessageBox("Please enter a name for the voice.", "Input Error", wx.OK | wx.ICON_WARNING)
            self.name_text.SetFocus()
            return False

        voice_desc = self.desc_text.GetValue().strip()
        desc_len = len(voice_desc)
        if not (20 <= desc_len <= 1000):
            wx.MessageBox(f"Voice description must be between 20 and 1000 characters long (currently {desc_len}).",
                          "Input Error", wx.OK | wx.ICON_WARNING)
            self.desc_text.SetFocus()
            return False

        if not self.auto_generate_checkbox.GetValue():
            text_prompt = self.text_prompt_ctrl.GetValue().strip()
            text_len = len(text_prompt)
            if not (100 <= text_len <= 1000):
                wx.MessageBox(f"Text prompt must be between 100 and 1000 characters long (currently {text_len}) when not auto-generating.",
                              "Input Error", wx.OK | wx.ICON_WARNING, self)
                self.text_prompt_ctrl.SetFocus()
                return False
        return True

    def on_generate_previews(self, event):
        """Starts the process to generate voice previews."""
        if not self.validate_inputs():
            return

        self.progress_dialog = wx.ProgressDialog(
            "Generating Voice Previews", "Sending request to ElevenLabs...", maximum=100,
            parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        self.progress_dialog.Show()
        self.progress_dialog.Pulse("Processing...")

        voice_desc = self.desc_text.GetValue().strip()
        auto_generate = self.auto_generate_checkbox.GetValue()
        payload = {
            "voice_description": voice_desc,
            "auto_generate_text": auto_generate,
            "loudness": self.map_slider_to_float(self.loudness_slider.GetValue()),
            "quality": self.map_slider_to_float(self.quality_slider.GetValue()),
            "guidance_scale": self.guidance_slider.GetValue()
        }
        if not auto_generate:
            payload["text"] = self.text_prompt_ctrl.GetValue().strip()
        output_format = self.get_selected_output_format()

        future = self.executor.submit(self.create_preview_worker, payload, output_format)
        future.add_done_callback(self.on_preview_created)

    def create_preview_worker(self, payload, output_format):
        """Worker thread for POST /v1/text-to-voice/create-previews."""
        url = "https://api.elevenlabs.io/v1/text-to-voice/create-previews"
        headers = {'xi-api-key': self.api_key, 'Content-Type': 'application/json'}
        params = {'output_format': output_format}

        try:
            response = requests.post(url, headers=headers, json=payload, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
             raise TimeoutError("The request to generate previews timed out.")
        except requests.exceptions.RequestException as e:
            error_msg = f"Network or API error generating preview: {e}"
            if e.response is not None:
                error_msg += f" (Status: {e.response.status_code})"
                try: error_msg += f" - {e.response.text}"
                except Exception: pass
            raise ConnectionError(error_msg) from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding preview response: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error generating preview: {e}") from e

    def on_preview_created(self, future):
        """Callback after the preview generation attempt."""
        if self.progress_dialog:
            wx.CallAfter(self.progress_dialog.Destroy)
        self.progress_dialog = None

        try:
            result_data = future.result()
            previews_list = result_data.get("previews", [])
            generated_text = result_data.get("text", "")

            if not previews_list or not isinstance(previews_list, list):
                wx.CallAfter(wx.MessageBox, "API response did not contain a valid list under the 'previews' key.",
                              "Generation Failed", wx.OK | wx.ICON_ERROR)
                return

            voice_name = self.name_text.GetValue().strip()
            voice_desc = self.desc_text.GetValue().strip()
            wx.CallAfter(self._show_preview_dialog, previews_list)

        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Failed to process voice previews:\n{e}",
                          "Error", wx.OK | wx.ICON_ERROR)

    def _show_preview_dialog(self, previews_list):
        """Creates and shows the PreviewSelectionDialog. Runs on main thread."""
        if not self or not wx.FindWindowById(self.GetId()):
             return

        try:
            voice_name = self.name_text.GetValue().strip()
            voice_desc = self.desc_text.GetValue().strip()

            preview_dialog = PreviewSelectionDialog(
                self,
                self.api_key,
                previews_list,
                voice_name,
                voice_desc
            )
            modal_result = preview_dialog.ShowModal()
            preview_dialog.Destroy()
            self.EndModal(wx.ID_OK)

        except Exception as e:
             wx.MessageBox(f"Error showing preview selection dialog:\n{e}",
                           "Dialog Error", wx.OK | wx.ICON_ERROR, parent=None)


    def __del__(self):
        """Ensure executor shutdown and progress dialog cleanup."""
        if hasattr(self, 'executor') and self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
             if wx.FindWindowById(self.progress_dialog.GetId()):
                  # Needs CallAfter as __del__ might be off main thread
                  wx.CallAfter(self.progress_dialog.Destroy)
             self.progress_dialog = None


class ConfirmAddVoiceDialog(wx.Dialog):
    """
    Dialog to confirm/edit the name and description before adding a voice.
    """
    def __init__(self, parent, default_name, default_description):
        super().__init__(parent, title="Confirm Voice Details", size=(450, 350),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.voice_name = default_name
        self.voice_description = default_description

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        info = wx.StaticText(panel, label="Confirm or edit the details for the voice to be added:")
        main_sizer.Add(info, 0, wx.ALL, 10)

        name_label = wx.StaticText(panel, label="Voice Name:")
        self.name_text = wx.TextCtrl(panel, value=default_name)
        main_sizer.Add(name_label, 0, wx.LEFT|wx.RIGHT|wx.TOP, 10)
        main_sizer.Add(self.name_text, 0, wx.EXPAND | wx.LEFT|wx.RIGHT|wx.BOTTOM, 10)

        desc_label = wx.StaticText(panel, label="Voice Description:")
        self.desc_text = wx.TextCtrl(panel, value=default_description, style=wx.TE_MULTILINE, size=(-1, 100))
        main_sizer.Add(desc_label, 0, wx.LEFT|wx.RIGHT|wx.TOP, 10)
        main_sizer.Add(self.desc_text, 1, wx.EXPAND | wx.LEFT|wx.RIGHT|wx.BOTTOM, 10)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK, label="Add Voice")
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(main_sizer)
        self.CentreOnParent()
        ok_button.Bind(wx.EVT_BUTTON, self.on_ok)

    def on_ok(self, event):
        """Validate inputs before accepting."""
        name = self.name_text.GetValue().strip()
        description = self.desc_text.GetValue().strip()
        desc_len = len(description)
        if not name:
            wx.MessageBox("Please enter a name for the voice.", "Input Error", wx.OK | wx.ICON_WARNING, self)
            self.name_text.SetFocus()
            return

        if not (20 <= desc_len <= 1000):
            wx.MessageBox(f"Voice description must be between 20 and 1000 characters long, Currently {desc_len} characters.",
                          "Input Error", wx.OK | wx.ICON_WARNING, self)
            self.desc_text.SetFocus()
            return

        # Inputs are valid, store them and end modal
        self.voice_name = name
        self.voice_description = description
        self.EndModal(wx.ID_OK)

    def GetVoiceName(self):
        """Returns the confirmed/edited voice name."""
        return self.voice_name

    def GetVoiceDescription(self):
        """Returns the confirmed/edited voice description."""
        return self.voice_description


class PreviewSelectionDialog(wx.Dialog):
    """
    Dialog to display generated voice previews, allow playing, and adding one to the library.
    """
    def __init__(self, parent, api_key, previews_list, voice_name, voice_description):
        super().__init__(parent, title=f"Select Preview for '{voice_name}'", size=(600, 450),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.api_key = api_key
        self.previews = previews_list
        self.original_voice_name = voice_name
        self.original_voice_desc = voice_description
        self.selected_preview_index = -1
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.progress_dialog = None

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        info_label = wx.StaticText(panel, label="Select a generated preview:")
        main_sizer.Add(info_label, 0, wx.ALL, 10)

        self.preview_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        main_sizer.Add(self.preview_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.populate_preview_list()

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.play_button = wx.Button(panel, label="&Play Selected")
        self.add_button = wx.Button(panel, label="&Add to Library")
        self.close_button = wx.Button(panel, wx.ID_CANCEL, label="&Close")

        button_sizer.Add(self.play_button, 0, wx.RIGHT, 10)
        button_sizer.Add(self.add_button, 0, wx.RIGHT, 10)
        button_sizer.AddStretchSpacer(1)
        button_sizer.Add(self.close_button, 0)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        self.CentreOnParent()

        self.preview_list.Bind(wx.EVT_LISTBOX, self.on_preview_select)
        self.preview_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_play)
        self.play_button.Bind(wx.EVT_BUTTON, self.on_play)
        self.add_button.Bind(wx.EVT_BUTTON, self.on_add)
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close)

        self.play_button.Disable()
        self.add_button.Disable()
        if self.previews:
            self.preview_list.SetSelection(0)
            self.on_preview_select(None)


    def populate_preview_list(self):
        """Fills the listbox with preview identifiers."""
        self.preview_list.Clear()
        for i, preview in enumerate(self.previews):
            duration = preview.get('duration_secs')
            text_snippet = preview.get('text', '')
            label = f"Preview {i+1}"
            if duration:
                 label += f" ({duration:.2f}s)"
            if text_snippet:
                 label += f" - \"{text_snippet[:100]}...\"" if len(text_snippet) > 100 else f" - \"{text_snippet}\""
            self.preview_list.Append(label)

    def on_preview_select(self, event):
        """Enables/disables buttons based on list selection."""
        self.selected_preview_index = self.preview_list.GetSelection()
        has_selection = self.selected_preview_index != wx.NOT_FOUND
        self.play_button.Enable(has_selection)
        self.add_button.Enable(has_selection)
        if event:
            event.Skip()

    def on_play(self, event):
        """Plays the selected preview using SimplePlayer with base64."""
        if self.selected_preview_index == wx.NOT_FOUND:
            return

        selected_preview = self.previews[self.selected_preview_index]
        audio_b64 = selected_preview.get('audio_base_64')
        media_type = selected_preview.get('media_type')

        if not audio_b64 or not media_type:
            wx.MessageBox("Selected preview is missing audio data or media type.", "Play Error", wx.OK | wx.ICON_ERROR)
            return

        try:
            player_title = f"Preview {self.selected_preview_index + 1} for {self.original_voice_name}"
            player = SimplePlayer(self, audio_base64=audio_b64, media_type=media_type, title=player_title)
            player.ShowModal()
            player.Destroy()
        except Exception as e:
            wx.MessageBox(f"Failed to start audio player:\n{e}", "Player Error", wx.OK | wx.ICON_ERROR)

    def on_add(self, event):
        """Initiates adding the selected preview voice to the library."""
        if self.selected_preview_index == wx.NOT_FOUND:
            return

        selected_preview = self.previews[self.selected_preview_index]
        generated_voice_id = selected_preview.get('generated_voice_id')
        if not generated_voice_id:
            wx.MessageBox("Selected preview is missing the required 'generated_voice_id'.", "Add Error", wx.OK | wx.ICON_ERROR)
            return

        # Suggest a potentially unique name by default if multiple previews exist
        suggested_name = self.original_voice_name
        if len(self.previews) > 1:
             suggested_name += f" (Preview {self.selected_preview_index + 1})"
        confirm_dialog = ConfirmAddVoiceDialog(
            self,
            default_name=suggested_name,
            default_description=self.original_voice_desc
        )
        result = confirm_dialog.ShowModal()
        confirmed_name = confirm_dialog.GetVoiceName()
        confirmed_desc = confirm_dialog.GetVoiceDescription()
        confirm_dialog.Destroy()

        if result != wx.ID_OK:
            return

        self.progress_dialog = wx.ProgressDialog(
            "Adding Voice", f"Adding '{confirmed_name}' to your library...", maximum=100,
            parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        self.progress_dialog.Show()
        self.progress_dialog.Pulse("Communicating with ElevenLabs...")

        payload = {
            "voice_name": confirmed_name,
            "voice_description": confirmed_desc,
            "generated_voice_id": generated_voice_id
        }

        future = self.executor.submit(self.save_voice_worker, payload)
        future.add_done_callback(self._on_voice_save_future_done)

    def save_voice_worker(self, payload):
        """Worker thread for POST /v1/text-to-voice/create-voice-from-preview."""
        url = "https://api.elevenlabs.io/v1/text-to-voice/create-voice-from-preview"
        headers = {'xi-api-key': self.api_key, 'Content-Type': 'application/json'}

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise TimeoutError("The request to add the voice timed out.")
        except requests.exceptions.RequestException as e:
            error_msg = f"Network or API error saving voice: {e}"
            if e.response is not None:
                error_msg += f" (Status: {e.response.status_code})"
                try: error_msg += f" - {e.response.text}"
                except Exception: pass
            raise ConnectionError(error_msg) from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding save voice response: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error saving voice: {e}") from e

    def _on_voice_save_future_done(self, future):
        """Callback executed in background thread when save_voice_worker finishes."""
        if self.progress_dialog:
            wx.CallAfter(self.progress_dialog.Destroy)
        self.progress_dialog = None

        try:
            save_result = future.result()
            wx.CallAfter(self._handle_voice_saved_ui, save_result)

        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Failed to add voice to library:\n{e}",
                          "Save Error", wx.OK | wx.ICON_ERROR, self)

    def _handle_voice_saved_ui(self, save_result):
        """Handles UI updates after voice save attempt, runs on main thread."""
        final_voice_id = save_result.get('voice_id')
        final_voice_name = save_result.get('name', self.original_voice_name)
        library_preview_url = save_result.get('preview_url')
        if not final_voice_id:
             wx.MessageBox("Failed to save voice: API did not return a voice ID.",
                           "Save Failed", wx.OK | wx.ICON_ERROR, self)
             return

        # Voice added successfully, now ask about library preview
        msg = f"The voice '{final_voice_name}' has been successfully added to your account." # Uses final_voice_name
        style = wx.OK | wx.ICON_INFORMATION
        if library_preview_url:
            msg += "\n\nWould you like to hear the audio preview for this voice?"
            style = wx.YES_NO | wx.ICON_QUESTION | wx.YES_DEFAULT
        confirm_dialog = wx.MessageDialog(self, msg, "Success", style)
        response = confirm_dialog.ShowModal()
        confirm_dialog.Destroy()

        player_shown = False
        if response == wx.ID_YES and library_preview_url:
            try:
                player = SimplePlayer(self, audio_url=library_preview_url, title=f"Audio Preview: {final_voice_name}")
                player.ShowModal()
                player.Destroy()
                player_shown = True
            except Exception as e:
                wx.MessageBox(f"Failed to play audio preview:\n{e}", "Player Error", wx.OK | wx.ICON_ERROR, self)


    def on_close(self, event):
        """Closes the dialog."""
        self.EndModal(wx.ID_CANCEL)

    def __del__(self):
        """Ensure executor shutdown."""
        if hasattr(self, 'executor') and self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
             if wx.FindWindowById(self.progress_dialog.GetId()):
                  wx.CallAfter(self.progress_dialog.Destroy)
             self.progress_dialog = None
