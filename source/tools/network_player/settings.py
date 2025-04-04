import wx
from gui.settings import SettingsPanel

class YoutubeSettings(SettingsPanel):
    category_name = "YouTube"

    def create_controls(self):
        fast_forward_label = wx.StaticText(self, label="Fast Forward Interval (Seconds):")
        self.fast_forward_spin = wx.SpinCtrl(self, min=5, max=60, initial=5)
        self.sizer.Add(fast_forward_label, 0, wx.ALL, 5)
        self.sizer.Add(self.fast_forward_spin, 0, wx.ALL | wx.EXPAND, 5)
        self.fast_forward_spin.Bind(wx.EVT_SPINCTRL, self.on_setting_change)

        rewind_label = wx.StaticText(self, label="Rewind Interval (Seconds):")
        self.rewind_spin = wx.SpinCtrl(self, min=5, max=60, initial=5)
        self.sizer.Add(rewind_label, 0, wx.ALL, 5)
        self.sizer.Add(self.rewind_spin, 0, wx.ALL | wx.EXPAND, 5)
        self.rewind_spin.Bind(wx.EVT_SPINCTRL, self.on_setting_change)

        volume_label = wx.StaticText(self, label="Default Volume:")
        self.volume_spin = wx.SpinCtrl(self, min=1, max=150, initial=80)
        self.sizer.Add(volume_label, 0, wx.ALL, 5)
        self.sizer.Add(self.volume_spin, 0, wx.ALL | wx.EXPAND, 5)
        self.volume_spin.Bind(wx.EVT_SPINCTRL, self.on_setting_change)

        quality_label = wx.StaticText(self, label="Default Video Quality:")
        self.quality_combo = wx.ComboBox(self, choices=["Low", "Medium", "Best"], style=wx.CB_READONLY)
        self.quality_combo.SetValue("Medium")
        self.sizer.Add(quality_label, 0, wx.ALL, 5)
        self.sizer.Add(self.quality_combo, 0, wx.ALL | wx.EXPAND, 5)
        self.quality_combo.Bind(wx.EVT_COMBOBOX, self.on_setting_change)

        update_channel_label = wx.StaticText(self, label="yt-dlp Update Channel:")
        self.update_channel_combo = wx.ComboBox(self, choices=["stable", "nightly", "master"], style=wx.CB_READONLY)
        self.update_channel_combo.SetValue("stable") # Default value
        self.sizer.Add(update_channel_label, 0, wx.ALL, 5)
        self.sizer.Add(self.update_channel_combo, 0, wx.ALL | wx.EXPAND, 5)
        self.update_channel_combo.Bind(wx.EVT_COMBOBOX, self.on_setting_change)


    def load_settings(self):
        youtube_settings = self.config.get('YouTube', {})
        self.fast_forward_spin.SetValue(int(youtube_settings.get('fast_forward_interval', 5)))
        self.rewind_spin.SetValue(int(youtube_settings.get('rewind_interval', 5)))
        self.volume_spin.SetValue(int(youtube_settings.get('default_volume', 80)))
        self.quality_combo.SetValue(youtube_settings.get('video_quality', "Medium"))
        self.update_channel_combo.SetValue(youtube_settings.get('yt_dlp_update_channel', "stable"))

    def save_settings(self):
        if 'YouTube' not in self.config:
            self.config['YouTube'] = {}
        self.config['YouTube']['fast_forward_interval'] = self.fast_forward_spin.GetValue()
        self.config['YouTube']['rewind_interval'] = self.rewind_spin.GetValue()
        self.config['YouTube']['default_volume'] = self.volume_spin.GetValue()
        self.config['YouTube']['video_quality'] = self.quality_combo.GetValue()
        self.config['YouTube']['yt_dlp_update_channel'] = self.update_channel_combo.GetValue()

    def on_setting_change(self, event):
        self.save_settings()
