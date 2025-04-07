import wx, concurrent.futures, requests, json
import math
from gui.custom_controls import CustomSlider


class EditVoiceSettings(wx.Dialog):
    def __init__(self, parent, api_key, voice_id, voice_name):
        super().__init__(parent, title=f"Edit Settings for {voice_name}", size=(450, 400),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.api_key = api_key
        self.voice_id = voice_id
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.SLIDER_MAX = 100 # For 0.0 to 1.0 range
        self.SPEED_SLIDER_MIN_VAL = 0.7
        self.SPEED_SLIDER_MAX_VAL = 1.2
        self.SPEED_SLIDER_STEP = 0.05
        # Calculate steps for speed slider (0 to N)
        self.SPEED_SLIDER_STEPS = int(round((self.SPEED_SLIDER_MAX_VAL - self.SPEED_SLIDER_MIN_VAL) / self.SPEED_SLIDER_STEP))

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        settings_sizer = wx.BoxSizer(wx.VERTICAL)

        def create_setting_row(label_text, slider_range_max, initial_val_float):
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)
            label = wx.StaticText(panel, label=label_text, size=(180,-1))
            slider = CustomSlider(panel, value=int(initial_val_float * self.SLIDER_MAX),
                               minValue=0, maxValue=slider_range_max,
                               style=wx.SL_HORIZONTAL)

            row_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            row_sizer.Add(slider, 1, wx.EXPAND | wx.RIGHT, 5)
            settings_sizer.Add(row_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)
            return slider

        self.stability_slider = create_setting_row(
            "Stability:", self.SLIDER_MAX, 0.5)
        self.stability_slider.Bind(wx.EVT_SLIDER, lambda event: self.on_standard_slider_change(event, self.SLIDER_MAX))

        self.similarity_slider = create_setting_row(
            "Similarity Boost:", self.SLIDER_MAX, 0.75)
        self.similarity_slider.Bind(wx.EVT_SLIDER, lambda event: self.on_standard_slider_change(event, self.SLIDER_MAX))

        self.style_slider = create_setting_row(
            "Style Exaggeration:", self.SLIDER_MAX, 0.0)
        self.style_slider.Bind(wx.EVT_SLIDER, lambda event: self.on_standard_slider_change(event, self.SLIDER_MAX))

        speed_sizer = wx.BoxSizer(wx.HORIZONTAL)
        speed_label = wx.StaticText(panel, label="Speed:", size=(180,-1))
        initial_speed_slider_val = int(round((1.0 - self.SPEED_SLIDER_MIN_VAL) / self.SPEED_SLIDER_STEP)) # Default 1.0
        self.speed_slider = wx.Slider(panel, value=initial_speed_slider_val,
                                       minValue=0, maxValue=self.SPEED_SLIDER_STEPS,
                                       style=wx.SL_HORIZONTAL)
        speed_sizer.Add(speed_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        speed_sizer.Add(self.speed_slider, 1, wx.EXPAND | wx.RIGHT, 5)
        settings_sizer.Add(speed_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)
        self.speed_slider.Bind(wx.EVT_SLIDER, self.on_speed_slider_change)

        speaker_boost_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.speaker_boost_check = wx.CheckBox(panel, label="Use speaker boost")
        speaker_boost_sizer.Add(self.speaker_boost_check, 0, wx.ALIGN_CENTER_VERTICAL)
        settings_sizer.Add(speaker_boost_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.loading_text = wx.StaticText(panel, label="Loading current settings...")
        self.loading_indicator = wx.ActivityIndicator(panel)

        button_sizer = wx.StdDialogButtonSizer()
        self.ok_button = wx.Button(panel, wx.ID_OK)
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL)
        self.ok_button.SetDefault()
        button_sizer.AddButton(self.ok_button)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()

        main_sizer.Add(self.loading_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        main_sizer.Add(self.loading_indicator, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        main_sizer.Add(settings_sizer, 1, wx.EXPAND | wx.ALL, 15)
        main_sizer.AddStretchSpacer(1)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        panel.Layout()
        self.Layout()
        self.CentreOnParent()
        self.ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
        self.loading_indicator.Start()
        self.load_current_settings()


    def on_standard_slider_change(self, event, max_value):
        slider_value = event.GetInt()
        float_value = slider_value / float(max_value)
        event.Skip()

    def on_speed_slider_change(self, event):
        """Updates the text label for the custom speed slider."""
        slider_value = event.GetInt()
        # Map slider value (0 to N) back to float speed (0.7 to 1.2)
        speed_value = self.SPEED_SLIDER_MIN_VAL + (slider_value * self.SPEED_SLIDER_STEP)
        speed_value = max(self.SPEED_SLIDER_MIN_VAL, min(self.SPEED_SLIDER_MAX_VAL, speed_value))
        event.Skip()

    def load_current_settings(self):
        """Fetch current voice settings in background."""
        self.fetch_future = self.executor.submit(self.fetch_current_settings_worker)
        self.fetch_future.add_done_callback(self.on_settings_fetched)

    def fetch_current_settings_worker(self):
        """Worker thread to get current settings."""
        headers = {'xi-api-key': self.api_key}
        url = f"https://api.elevenlabs.io/v1/voices/{self.voice_id}/settings"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Network error fetching settings: {e}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding settings response: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error fetching settings: {e}") from e

    def on_settings_fetched(self, future):
        """Callback when current settings are fetched."""
        wx.CallAfter(self.loading_indicator.Stop)
        wx.CallAfter(self.loading_text.Hide)

        try:
            settings = future.result()
            stability_val = settings.get('stability', 0.5)
            wx.CallAfter(self.stability_slider.SetValue, int(stability_val * self.SLIDER_MAX))

            similarity_val = settings.get('similarity_boost', 0.75)
            wx.CallAfter(self.similarity_slider.SetValue, int(similarity_val * self.SLIDER_MAX))

            style_val = settings.get('style', 0.0)
            wx.CallAfter(self.style_slider.SetValue, int(style_val * self.SLIDER_MAX))

            speed_val = settings.get('speed', 1.0)
            speed_slider_val = int(round((speed_val - self.SPEED_SLIDER_MIN_VAL) / self.SPEED_SLIDER_STEP))
            speed_slider_val = max(0, min(self.SPEED_SLIDER_STEPS, speed_slider_val))
            wx.CallAfter(self.speed_slider.SetValue, speed_slider_val)
            wx.CallAfter(self.speaker_boost_check.SetValue, settings.get('use_speaker_boost', False))

        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Failed to load current voice settings:\n{e}\n\nCannot edit settings.",
                          "Error Loading Settings", wx.OK | wx.ICON_ERROR, self)
            wx.CallAfter(self.set_controls_enabled, False)

    def on_ok(self, event):
        """Handle OK button click: save settings."""
        stability_float = self.stability_slider.GetValue() / float(self.SLIDER_MAX)
        similarity_float = self.similarity_slider.GetValue() / float(self.SLIDER_MAX)
        style_float = self.style_slider.GetValue() / float(self.SLIDER_MAX)

        # Calculate speed float from its custom slider
        speed_slider_val = self.speed_slider.GetValue()
        speed_float = self.SPEED_SLIDER_MIN_VAL + (speed_slider_val * self.SPEED_SLIDER_STEP)
        speed_float = max(self.SPEED_SLIDER_MIN_VAL, min(self.SPEED_SLIDER_MAX_VAL, speed_float))

        new_settings = {
            "stability": stability_float,
            "similarity_boost": similarity_float,
            "style": style_float,
            "speed": speed_float,
            "use_speaker_boost": self.speaker_boost_check.GetValue()
        }

        self.progress_dialog = wx.ProgressDialog(
            "Saving Settings", "Applying changes...",
            parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        self.progress_dialog.Show()

        save_future = self.executor.submit(self.save_settings_worker, new_settings)
        save_future.add_done_callback(self.on_settings_saved)

    def save_settings_worker(self, settings_payload):
        """Worker thread to POST updated settings."""
        headers = {'xi-api-key': self.api_key, 'Content-Type': 'application/json'}
        url = f"https://api.elevenlabs.io/v1/voices/{self.voice_id}/settings/edit"
        try:
            response = requests.post(url, headers=headers, json=settings_payload)
            response.raise_for_status()
            data = response.json()
            if data.get('status') == 'ok':
                return True
            else:
                error_detail = data.get('detail', {}).get('message', 'Unknown error from API')
                raise RuntimeError(f"API reported failure: {error_detail}")

        except requests.exceptions.RequestException as e:
            error_msg = f"Network or API error saving settings: {e}"
            if e.response is not None:
                 error_msg += f" (Status Code: {e.response.status_code})"
                 try:
                     error_detail = e.response.json().get('detail', {}).get('message', '')
                     if error_detail: error_msg += f" - {error_detail}"
                 except json.JSONDecodeError: pass
            raise ConnectionError(error_msg) from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error saving settings: {e}") from e

    def on_settings_saved(self, future):
        """Callback when settings save attempt is complete."""
        if self.progress_dialog:
             wx.CallAfter(self.progress_dialog.Destroy)

        try:
            success = future.result()
            if success:
                wx.CallAfter(wx.MessageBox, "Voice settings updated successfully.", "Success", wx.OK | wx.ICON_INFORMATION, self)
                wx.CallAfter(self.EndModal, wx.ID_OK)
            else:
                # Might not be reachable if worker raises exceptions
                 wx.CallAfter(wx.MessageBox, "Failed to save settings: API did not report success.", "Save Failed", wx.OK | wx.ICON_ERROR, self)

        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Failed to save voice settings:\n{e}", "Save Error", wx.OK | wx.ICON_ERROR, self)
            wx.CallAfter(self.set_controls_enabled, True)

    def __del__(self):
        if hasattr(self, 'executor') and self.executor and not self.executor._shutdown:
             self.executor.shutdown(wait=False)
