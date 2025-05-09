import wx
import datetime
import os
import sys
import vlc
import app_vars

class AlarmSettingsDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Alarm Settings", size=(500, 630))
        self.panel = wx.Panel(self)
        self.custom_sound_path = ""
        self.vlc_instance_preview = None
        self.media_player_preview = None
        
        try:
            self.vlc_instance_preview = vlc.Instance("--no-xlib --quiet")
            self.media_player_preview = self.vlc_instance_preview.media_player_new()
        except Exception as e:
            wx.MessageBox("Sound preview is not available because VLC failed to initialize.",
                          "Sound Preview Warning", wx.OK | wx.ICON_WARNING, self)

        self._setup_ui()
        self._load_default_sounds()
        self._set_default_times()
        self.Centre()
        self.Bind(wx.EVT_CLOSE, self._on_dialog_close)

    def _on_dialog_close(self, event):
        """Cleanup VLC resources when dialog closes."""
        if self.media_player_preview:
            if self.media_player_preview.is_playing():
                self.media_player_preview.stop()
            self.media_player_preview.release()
        if self.vlc_instance_preview:
            self.vlc_instance_preview.release()
        event.Skip()

    def _setup_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        name_label = wx.StaticText(self.panel, label="Alarm Name:")
        self.name_text = wx.TextCtrl(self.panel)
        main_sizer.Add(name_label, 0, wx.LEFT|wx.RIGHT|wx.TOP, 10)
        main_sizer.Add(self.name_text, 0, wx.ALL|wx.EXPAND, 5)
        main_sizer.AddSpacer(5)

        time_box = wx.StaticBox(self.panel, label="Time")
        time_static_sizer = wx.StaticBoxSizer(time_box, wx.VERTICAL)
        time_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        time_controls_sizer.Add(wx.StaticText(self.panel, label="Hour:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.hour_spin = wx.SpinCtrl(self.panel, min=1, max=12, style=wx.SP_ARROW_KEYS | wx.SP_WRAP)
        time_controls_sizer.Add(self.hour_spin, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        time_controls_sizer.Add(wx.StaticText(self.panel, label="Minute:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.minute_spin = wx.SpinCtrl(self.panel, min=0, max=59, style=wx.SP_ARROW_KEYS | wx.SP_WRAP)
        time_controls_sizer.Add(self.minute_spin, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        time_controls_sizer.Add(wx.StaticText(self.panel, label="Second:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.second_spin = wx.SpinCtrl(self.panel, min=0, max=59, style=wx.SP_ARROW_KEYS | wx.SP_WRAP)
        time_controls_sizer.Add(self.second_spin, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.ampm_radio = wx.RadioBox(self.panel, choices=["AM", "PM"], majorDimension=2, style=wx.RA_SPECIFY_COLS)
        time_controls_sizer.Add(self.ampm_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 0)

        time_static_sizer.Add(time_controls_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(time_static_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.AddSpacer(5)

        date_box = wx.StaticBox(self.panel, label="Date")
        date_static_sizer = wx.StaticBoxSizer(date_box, wx.VERTICAL)
        date_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)

        date_controls_sizer.Add(wx.StaticText(self.panel, label="Day:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.day_spin = wx.SpinCtrl(self.panel, min=1, max=31)
        self.day_spin.Bind(wx.EVT_SPINCTRL, self._validate_day_for_month)
        date_controls_sizer.Add(self.day_spin, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        date_controls_sizer.Add(wx.StaticText(self.panel, label="Month:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.month_spin = wx.SpinCtrl(self.panel, min=1, max=12)
        self.month_spin.Bind(wx.EVT_SPINCTRL, self._validate_day_for_month)
        date_controls_sizer.Add(self.month_spin, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 0)

        date_static_sizer.Add(date_controls_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(date_static_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.AddSpacer(5)

        schedule_label = wx.StaticText(self.panel, label="Schedule Interval:")
        main_sizer.Add(schedule_label, 0, wx.LEFT|wx.RIGHT|wx.TOP, 5)
        self.schedule_combo = wx.ComboBox(self.panel, choices=["Once", "Daily", "Weekly", "Custom Days"], style=wx.CB_READONLY)
        self.schedule_combo.Bind(wx.EVT_COMBOBOX, self._on_schedule_type_change)
        main_sizer.Add(self.schedule_combo, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, 5)

        self.custom_days_checkbox_sizer = wx.GridSizer(rows=1, cols=7, vgap=2, hgap=2)
        self.days_checkboxes = {}
        days_full = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        days_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days_full):
            cb = wx.CheckBox(self.panel, label=day)
            self.days_checkboxes[days_abbr[i]] = cb
            self.custom_days_checkbox_sizer.Add(cb, 0, wx.ALIGN_CENTER | wx.ALL, 2)
            cb.Show(False)
        
        custom_days_container = wx.BoxSizer(wx.HORIZONTAL)
        custom_days_container.AddStretchSpacer(1)
        custom_days_container.Add(self.custom_days_checkbox_sizer, 0, wx.ALIGN_CENTER)
        custom_days_container.AddStretchSpacer(1)
        main_sizer.Add(custom_days_container, 0, wx.EXPAND | wx.ALL, 0)
        main_sizer.AddSpacer(5)

        snooze_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        snooze_controls_sizer.Add(wx.StaticText(self.panel, label="Snooze times:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.snooze_times_spin = wx.SpinCtrl(self.panel, min=0, max=10, initial=3)
        snooze_controls_sizer.Add(self.snooze_times_spin, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        snooze_controls_sizer.Add(wx.StaticText(self.panel, label="Snooze interval:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.snooze_interval_spin = wx.SpinCtrl(self.panel, min=1, max=60, initial=5)
        snooze_controls_sizer.Add(self.snooze_interval_spin, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 0)

        main_sizer.Add(snooze_controls_sizer, 0, wx.EXPAND | wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
        main_sizer.AddSpacer(5)

        sound_label = wx.StaticText(self.panel, label="Sound:")
        main_sizer.Add(sound_label, 0, wx.LEFT|wx.RIGHT|wx.TOP, 5)
        self.sound_combo = wx.ComboBox(self.panel, style=wx.CB_READONLY | wx.TE_PROCESS_ENTER)
        self.sound_combo.Bind(wx.EVT_COMBOBOX, self._on_sound_change)
        self.sound_combo.Bind(wx.EVT_KEY_DOWN, self._on_sound_combo_key_down)
        main_sizer.Add(self.sound_combo, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, 5)

        self.custom_sound_details_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.custom_sound_text = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        browse_btn = wx.Button(self.panel, label="Browse...")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse_custom_sound)
        self.custom_sound_details_sizer.Add(self.custom_sound_text, 1, wx.EXPAND, 5)
        self.custom_sound_details_sizer.Add(browse_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(self.custom_sound_details_sizer, 0, wx.EXPAND | wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
        
        self.custom_sound_text.Show(False)
        browse_btn.Show(False)
        main_sizer.AddSpacer(10)

        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(self.panel, wx.ID_OK)
        ok_btn.SetDefault()
        cancel_btn = wx.Button(self.panel, wx.ID_CANCEL)
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.panel.SetSizerAndFit(main_sizer)
        self.Fit()

    def _set_default_times(self):
        """Sets default values for time and date controls."""
        now = datetime.datetime.now()
        hour_12 = now.hour % 12
        if hour_12 == 0: hour_12 = 12
        self.hour_spin.SetValue(hour_12)
        self.minute_spin.SetValue(now.minute)
        self.second_spin.SetValue(now.second)
        self.ampm_radio.SetSelection(0 if now.hour < 12 else 1)

        self.day_spin.SetValue(now.day)
        self.month_spin.SetValue(now.month)
        self._validate_day_for_month(None)

        self.schedule_combo.SetSelection(0)
        self._on_schedule_type_change(None)

    def _validate_day_for_month(self, event):
        """Validates day based on month (assuming current year)."""
        try:
            year = datetime.datetime.now().year
            month = self.month_spin.GetValue()
            if month < 1 or month > 12: return
            if month == 2:
                is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
                max_days = 29 if is_leap else 28
            elif month in [4, 6, 9, 11]: max_days = 30
            else: max_days = 31
            
            current_day = self.day_spin.GetValue()
            self.day_spin.SetRange(1, max_days)
            if current_day > max_days:
                self.day_spin.SetValue(max_days)

        except Exception as e:
            print(f"Error validating day/month: {e}")
        if event: event.Skip()

    def _get_sound_dir(self):
        """Returns path to 'sounds' directory in the application root."""
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), "sounds")
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            app_root_dir = os.path.dirname(os.path.dirname(script_dir))
            return os.path.join(app_root_dir, "sounds")

    def _load_default_sounds(self):
        """Loads sound files from the 'sounds' directory into the ComboBox."""
        self.sound_combo.Clear()
        self.sound_combo.Append("Choose from device...")
        
        sound_dir = self._get_sound_dir()
        default_sounds_found = False
        if sound_dir and os.path.isdir(sound_dir):
            for f_name in os.listdir(sound_dir):
                if f_name.lower().endswith((".mp3", ".wav", ".ogg", ".flac")):
                    self.sound_combo.Append(f_name)
                    default_sounds_found = True
        
        if default_sounds_found:
            self.sound_combo.SetSelection(1)
        else:
            self.sound_combo.SetSelection(0)
        self._on_sound_change(None)

    def _on_schedule_type_change(self, event):
        """Shows/hides custom days panel based on schedule type."""
        schedule_type = self.schedule_combo.GetValue()
        show_custom = (schedule_type == "Custom Days")
        for cb in self.days_checkboxes.values():
            cb.Show(show_custom)
        self.panel.Layout()

    def _on_sound_combo_key_down(self, event):
        """Handles spacebar press on sound combo to play/stop preview."""
        if event.GetKeyCode() == wx.WXK_SPACE:
            if self.media_player_preview:
                if self.media_player_preview.is_playing():
                    self.media_player_preview.stop()
                else:
                    selected_sound_name = self.sound_combo.GetValue()
                    sound_path_to_play = ""
                    if selected_sound_name == "Choose from device...":
                        sound_path_to_play = self.custom_sound_path
                    else:
                        sound_dir = self._get_sound_dir()
                        if sound_dir: # Check if sound dir was found
                             sound_path_to_play = os.path.join(sound_dir, selected_sound_name)
                    
                    if sound_path_to_play and os.path.exists(sound_path_to_play):
                        try:
                            media = self.vlc_instance_preview.media_new(sound_path_to_play)
                            self.media_player_preview.set_media(media)
                            self.media_player_preview.play()
                        except Exception as e:
                            wx.MessageBox(f"Error playing sound preview:\n{e}", "Preview Error", wx.OK | wx.ICON_ERROR, self)
                    elif sound_path_to_play:
                         wx.MessageBox("Sound file not found for preview.", "Preview Error", wx.OK | wx.ICON_WARNING, self)
                    # else: sound_dir not found, or "Choose from device" selected but no custom path
            elif self.sound_combo.GetValue() != "Choose from device...":
                 wx.MessageBox("Sound preview is not available.", "Preview Not Available", wx.OK | wx.ICON_WARNING, self)
            return

        event.Skip()

    def _on_sound_change(self, event):
        """Shows/hides custom sound path controls based on selection."""
        is_custom = (self.sound_combo.GetValue() == "Choose from device...")
        for i in range(self.custom_sound_details_sizer.GetItemCount()):
            sizer_item = self.custom_sound_details_sizer.GetItem(i)
            window_item = sizer_item.GetWindow()
            if window_item:
                window_item.Show(is_custom)
        self.panel.Layout()

    def _on_browse_custom_sound(self, event):
        """Opens file dialog to choose a custom sound."""
        with wx.FileDialog(self, "Choose Sound File",
                           wildcard="Sound files (*.mp3;*.wav;*.ogg;*.flac)|*.mp3;*.wav;*.ogg;*.flac|All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.custom_sound_path = dlg.GetPath()
                self.custom_sound_text.SetValue(self.custom_sound_path)

    def GetAlarmSettings(self):
        """Returns a dictionary with all configured alarm settings or None on error."""
        name = self.name_text.GetValue().strip()
        if not name:
            wx.MessageBox("Alarm name cannot be empty.", "Input Error", wx.OK | wx.ICON_ERROR, self)
            return None

        hour_val = self.hour_spin.GetValue()
        is_pm = (self.ampm_radio.GetSelection() == 1)
        hour_24 = hour_val
        if is_pm and hour_val != 12: hour_24 += 12
        elif not is_pm and hour_val == 12: hour_24 = 0
        
        time_settings = {"hour": hour_24, "minute": self.minute_spin.GetValue(), "second": self.second_spin.GetValue()}
        day = self.day_spin.GetValue()
        month = self.month_spin.GetValue()
        year = datetime.datetime.now().year
        
        try:
            datetime.date(year, month, day)
        except ValueError:
            wx.MessageBox(f"Invalid date selected: {day}/{month}/{year}. Please correct.", "Date Error", wx.OK | wx.ICON_ERROR, self)
            return None
        date_settings = {"day": day, "month": month, "year": year}

        schedule_type = self.schedule_combo.GetValue()
        custom_days_abbr_list = []
        if schedule_type == "Custom Days":
            # Map checked checkboxes back to abbreviations for internal storage
            days_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            for day_abbr in days_abbr:
                if self.days_checkboxes[day_abbr].IsChecked():
                    custom_days_abbr_list.append(day_abbr)

            if not custom_days_abbr_list:
                wx.MessageBox("For 'Custom Days' schedule, please select at least one day.", "Input Error", wx.OK | wx.ICON_ERROR, self)
                return None

        snooze_settings = {"count": self.snooze_times_spin.GetValue(), "interval": self.snooze_interval_spin.GetValue()}
        sound_name_in_combo = self.sound_combo.GetValue()
        is_custom_sound_selected = (sound_name_in_combo == "Choose from device...")
        sound_path_to_use = ""
        if is_custom_sound_selected:
            if not self.custom_sound_path or not os.path.exists(self.custom_sound_path):
                wx.MessageBox("Please browse and select a valid custom sound file.", "Sound Error", wx.OK | wx.ICON_ERROR, self)
                return None
            sound_path_to_use = self.custom_sound_path
        else:
            sound_dir = self._get_sound_dir()
            if not sound_dir or not os.path.isdir(sound_dir):
                 wx.MessageBox("Default sound directory not found. Cannot use default sounds.", "Sound Error", wx.OK | wx.ICON_ERROR, self)
                 return None

            sound_path_to_use = os.path.join(sound_dir, sound_name_in_combo)
            if not os.path.exists(sound_path_to_use):
                wx.MessageBox(f"Selected default sound '{sound_name_in_combo}' not found in '{sound_dir}'.", "Sound Error", wx.OK | wx.ICON_ERROR, self)
                return None

        sound_settings = {"path": sound_path_to_use, 
                          "is_custom": is_custom_sound_selected, 
                          "name_for_display": os.path.basename(sound_path_to_use)}

        return {
            "name": name, "time": time_settings, "date": date_settings,
            "schedule": {"type": schedule_type, "days": custom_days_abbr_list if custom_days_abbr_list else None},
            "snooze": snooze_settings, "sound": sound_settings
        }
