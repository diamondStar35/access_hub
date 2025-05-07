import wx
from gui.settings import SettingsPanel
import os
import app_vars

class YoutubeSettings(SettingsPanel):
    category_name = "YouTube"

    def create_controls(self):
        playback_sizer = wx.BoxSizer(wx.VERTICAL)
        fast_forward_label = wx.StaticText(self, label="Fast Forward Interval (Seconds):")
        self.fast_forward_spin = wx.SpinCtrl(self, min=5, max=60, initial=5)
        playback_sizer.Add(fast_forward_label, 0, wx.ALL | wx.EXPAND, 5)
        playback_sizer.Add(self.fast_forward_spin, 0, wx.ALL | wx.EXPAND, 5)
        self.fast_forward_spin.Bind(wx.EVT_SPINCTRL, self.on_setting_change)

        rewind_label = wx.StaticText(self, label="Rewind Interval (Seconds):")
        self.rewind_spin = wx.SpinCtrl(self, min=5, max=60, initial=5)
        playback_sizer.Add(rewind_label, 0, wx.ALL | wx.EXPAND, 5)
        playback_sizer.Add(self.rewind_spin, 0, wx.ALL | wx.EXPAND, 5)
        self.rewind_spin.Bind(wx.EVT_SPINCTRL, self.on_setting_change)

        volume_label = wx.StaticText(self, label="Default Volume:")
        self.volume_spin = wx.SpinCtrl(self, min=1, max=150, initial=80)
        playback_sizer.Add(volume_label, 0, wx.ALL | wx.EXPAND, 5)
        playback_sizer.Add(self.volume_spin, 0, wx.ALL | wx.EXPAND, 5)
        self.volume_spin.Bind(wx.EVT_SPINCTRL, self.on_setting_change)

        quality_label = wx.StaticText(self, label="Video playback Quality:")
        self.quality_combo = wx.ComboBox(self, choices=["Low", "Medium", "Best"], style=wx.CB_READONLY)
        self.quality_combo.SetValue("Medium")
        playback_sizer.Add(quality_label, 0, wx.ALL | wx.EXPAND, 5)
        playback_sizer.Add(self.quality_combo, 0, wx.ALL | wx.EXPAND, 5)
        self.quality_combo.Bind(wx.EVT_COMBOBOX, self.on_setting_change)

        update_channel_label = wx.StaticText(self, label="yt-dlp Update Channel:")
        self.update_channel_combo = wx.ComboBox(self, choices=["stable", "nightly", "master"], style=wx.CB_READONLY)
        self.update_channel_combo.SetValue("stable")
        playback_sizer.Add(update_channel_label, 0, wx.ALL | wx.EXPAND, 5)
        playback_sizer.Add(self.update_channel_combo, 0, wx.ALL | wx.EXPAND, 5)
        self.update_channel_combo.Bind(wx.EVT_COMBOBOX, self.on_setting_change)

        self.sizer.Add(playback_sizer, 0, wx.EXPAND | wx.ALL, 5)
        self.sizer.AddSpacer(15)

        default_download_sizer = wx.BoxSizer(wx.VERTICAL)
        default_type_label = wx.StaticText(self, label="Default Download Type:")
        default_download_sizer.Add(default_type_label, 0, wx.ALL | wx.EXPAND, 5)
        self.default_type_combo = wx.ComboBox(self, choices=["Video", "Audio"], style=wx.CB_READONLY)
        self.default_type_combo.SetValue("Audio")
        default_download_sizer.Add(self.default_type_combo, 0, wx.ALL | wx.EXPAND, 5)
        self.default_type_combo.Bind(wx.EVT_COMBOBOX, self.on_default_type_change)

        self.default_quality_sizer = wx.BoxSizer(wx.VERTICAL)
        self.default_video_quality_label = wx.StaticText(self, label="Video Quality for download:")
        self.default_quality_sizer.Add(self.default_video_quality_label, 0, wx.ALL | wx.EXPAND, 5)
        self.default_video_quality_combo = wx.ComboBox(self, choices=["Low", "Medium", "Best"], style=wx.CB_READONLY)
        self.default_quality_sizer.Add(self.default_video_quality_combo, 0, wx.ALL | wx.EXPAND, 5)
        self.default_video_quality_combo.Bind(wx.EVT_COMBOBOX, self.on_setting_change)

        self.default_audio_format_label = wx.StaticText(self, label="Audio Format:")
        self.default_quality_sizer.Add(self.default_audio_format_label, 0, wx.ALL | wx.EXPAND, 5)
        self.default_audio_format_combo = wx.ComboBox(self, choices=["mp3", "wav", "aac", "opus", "flac"], style=wx.CB_READONLY)
        self.default_quality_sizer.Add(self.default_audio_format_combo, 0, wx.ALL | wx.EXPAND, 5)
        self.default_audio_format_combo.Bind(wx.EVT_COMBOBOX, self.on_setting_change)

        self.default_audio_quality_label = wx.StaticText(self, label="Audio Quality (KBPS):")
        self.default_audio_quality_choices = ["0 (Best VBR)", "92K", "128K", "160K", "192K", "256K", "320K"]
        self.default_quality_sizer.Add(self.default_audio_quality_label, 0, wx.ALL | wx.EXPAND, 5)
        self.default_audio_quality_combo = wx.ComboBox(self, choices=self.default_audio_quality_choices, style=wx.CB_READONLY)
        self.default_quality_sizer.Add(self.default_audio_quality_combo, 0, wx.ALL | wx.EXPAND, 5)
        self.default_audio_quality_combo.Bind(wx.EVT_COMBOBOX, self.on_setting_change)
        default_download_sizer.Add(self.default_quality_sizer, 0, wx.EXPAND | wx.ALL, 5)

        default_directory_label = wx.StaticText(self, label="Download Directory:")
        default_download_sizer.Add(default_directory_label, 0, wx.ALL | wx.EXPAND, 5)
        self.default_directory_text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        default_download_sizer.Add(self.default_directory_text, 0, wx.ALL | wx.EXPAND, 5)
        self.default_directory_text.Bind(wx.EVT_TEXT, self.on_setting_change)

        default_browse_button = wx.Button(self, label="Browse...")
        default_download_sizer.Add(default_browse_button, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        default_browse_button.Bind(wx.EVT_BUTTON, self.on_browse_default_directory)

        self.sizer.Add(default_download_sizer, 0, wx.EXPAND | wx.ALL, 5)
        self.sizer.AddStretchSpacer(1)


    def load_settings(self):
        youtube_settings = self.config.get('YouTube', {})
        self.fast_forward_spin.SetValue(int(youtube_settings.get('fast_forward_interval', 5)))
        self.rewind_spin.SetValue(int(youtube_settings.get('rewind_interval', 5)))
        self.volume_spin.SetValue(int(youtube_settings.get('default_volume', 80)))
        self.quality_combo.SetValue(youtube_settings.get('video_quality', "Medium"))
        self.update_channel_combo.SetValue(youtube_settings.get('yt_dlp_update_channel', "stable"))
        default_type = youtube_settings.get('default_download_type', 'Video')
        if default_type in self.default_type_combo.GetItems():
             self.default_type_combo.SetValue(default_type)
        else:
             self.default_type_combo.SetSelection(0)

        self.default_video_quality_combo.SetValue(youtube_settings.get('default_video_quality', "Medium"))
        self.default_audio_format_combo.SetValue(youtube_settings.get('default_audio_format', "mp3"))
        self.default_audio_quality_combo.SetValue(youtube_settings.get('default_audio_quality', "128K"))
        default_dir = youtube_settings.get('default_download_directory', '')
        if default_dir and os.path.isdir(default_dir):
            self.default_directory_text.SetValue(default_dir)
        else:
            self.set_default_directory_control()
        self.on_default_type_change(None)

    def save_settings(self):
        if 'YouTube' not in self.config:
            self.config['YouTube'] = {}
        self.config['YouTube']['fast_forward_interval'] = self.fast_forward_spin.GetValue()
        self.config['YouTube']['rewind_interval'] = self.rewind_spin.GetValue()
        self.config['YouTube']['default_volume'] = self.volume_spin.GetValue()
        self.config['YouTube']['video_quality'] = self.quality_combo.GetValue()
        self.config['YouTube']['yt_dlp_update_channel'] = self.update_channel_combo.GetValue()
        self.config['YouTube']['default_download_type'] = self.default_type_combo.GetValue()
        self.config['YouTube']['default_video_quality'] = self.default_video_quality_combo.GetValue()
        self.config['YouTube']['default_audio_format'] = self.default_audio_format_combo.GetValue()
        self.config['YouTube']['default_audio_quality'] = self.default_audio_quality_combo.GetValue()
        self.config['YouTube']['default_download_directory'] = self.default_directory_text.GetValue()

    def on_setting_change(self, event):
        self.save_settings()

    def on_default_type_change(self, event):
        """Handles change in default download type radio box."""
        selected_type = self.default_type_combo.GetValue()

        show_video = (selected_type == "Video")
        self.default_video_quality_label.Show(show_video)
        self.default_video_quality_combo.Show(show_video)

        show_audio = (selected_type == "Audio")
        self.default_audio_format_label.Show(show_audio)
        self.default_audio_format_combo.Show(show_audio)
        self.default_audio_quality_label.Show(show_audio)
        self.default_audio_quality_combo.Show(show_audio)

        self.default_quality_sizer.Layout()
        self.Layout()

        self.set_default_directory_control()
        self.on_setting_change(None)

    def on_browse_default_directory(self, event):
        """Opens a directory dialog to choose the default download location."""
        current_dir = self.default_directory_text.GetValue()
        start_dir = current_dir if os.path.isdir(current_dir) else os.path.expanduser("~")
        with wx.DirDialog(self, "Choose Default Download Directory", start_dir,
                           style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                new_dir = dialog.GetPath()
                self.default_directory_text.SetValue(new_dir)
                self.on_setting_change(None)

    def set_default_directory_control(self):
        """Sets the default download directory text control value based on the selected type."""
        downloads_base_dir = ""
        try:
            downloads_base_dir = wx.StandardPaths.Get().GetDownloadsDir()
            if not downloads_base_dir:
                 downloads_base_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        except Exception as e:
            downloads_base_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        downloads_app_dir = os.path.join(downloads_base_dir, app_vars.app_name)

        download_type = self.default_type_combo.GetValue().lower()
        if download_type == "video":
            default_dir = os.path.join(downloads_app_dir, "videos")
        else:
            default_dir = os.path.join(downloads_app_dir, "audios")

        if not os.path.exists(default_dir):
            try:
                os.makedirs(default_dir)
            except Exception as e:
                fallback_dir = downloads_app_dir
                if not os.path.exists(fallback_dir):
                    try:
                         os.makedirs(fallback_dir)
                         default_dir = fallback_dir
                    except Exception:
                         default_dir = downloads_base_dir if downloads_base_dir and os.path.exists(downloads_base_dir) else os.path.expanduser("~")
        self.default_directory_text.SetValue(default_dir)