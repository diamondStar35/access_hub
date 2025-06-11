import wx

class GoToTimeDialog(wx.Dialog):
    def __init__(self, parent, total_duration_ms, current_elapsed_ms=0):
        super().__init__(parent, title="Go to time", style=wx.DEFAULT_DIALOG_STYLE)
        self.total_duration_ms = total_duration_ms
        self.selected_time_ms = 0

        # Calculate total duration components
        total_seconds_video = self.total_duration_ms // 1000
        self.max_hours_video = total_seconds_video // 3600
        self.max_minutes_video_part_if_no_hours = (total_seconds_video % 3600) // 60
        self.max_seconds_video_part_if_no_minutes_or_hours = total_seconds_video % 60
        # Calculate initial values from current_elapsed_ms
        initial_h, initial_m, initial_s = 0, 0, 0
        if current_elapsed_ms and current_elapsed_ms > 0:
            elapsed_s_total = current_elapsed_ms // 1000
            initial_h = elapsed_s_total // 3600
            initial_m = (elapsed_s_total % 3600) // 60
            initial_s = elapsed_s_total % 60

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        grid_sizer = wx.GridBagSizer(5, 5)
        self.hours_label = wx.StaticText(panel, label="Hours:")
        self.hours_spin = wx.SpinCtrl(panel, min=0, max=self.max_hours_video, initial=initial_h)
        if self.max_hours_video > 0:
            grid_sizer.Add(self.hours_label, pos=(0, 0), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=5)
            grid_sizer.Add(self.hours_spin, pos=(0, 1), flag=wx.EXPAND|wx.ALL, border=5)
        else:
            self.hours_label.Hide()
            self.hours_spin.Hide()

        minutes_label = wx.StaticText(panel, label="Minutes:")
        max_minutes_for_spin = 59
        if self.max_hours_video == 0: # Video is less than 1 hour
            max_minutes_for_spin = self.max_minutes_video_part_if_no_hours
        self.minutes_spin = wx.SpinCtrl(panel, min=0, max=max_minutes_for_spin, initial=initial_m)
        grid_sizer.Add(minutes_label, pos=(1, 0), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=5)
        grid_sizer.Add(self.minutes_spin, pos=(1, 1), flag=wx.EXPAND|wx.ALL, border=5)

        seconds_label = wx.StaticText(panel, label="Seconds:")
        max_seconds_for_spin = 59
        if self.max_hours_video == 0 and self.max_minutes_video_part_if_no_hours == 0: # Video is less than 1 minute
            max_seconds_for_spin = self.max_seconds_video_part_if_no_minutes_or_hours
        self.seconds_spin = wx.SpinCtrl(panel, min=0, max=max_seconds_for_spin, initial=initial_s)
        grid_sizer.Add(seconds_label, pos=(2, 0), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=5)
        grid_sizer.Add(self.seconds_spin, pos=(2, 1), flag=wx.EXPAND|wx.ALL, border=5)

        grid_sizer.AddGrowableCol(1)
        main_sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        main_sizer.Fit(self)
        self.CentreOnParent()
        ok_button.Bind(wx.EVT_BUTTON, self.on_ok)

    def on_ok(self, event):
        hours = self.hours_spin.GetValue() if self.max_hours_video > 0 else 0
        minutes = self.minutes_spin.GetValue()
        seconds = self.seconds_spin.GetValue()

        entered_total_seconds = (hours * 3600) + (minutes * 60) + seconds
        entered_total_ms = entered_total_seconds * 1000
        if entered_total_ms > self.total_duration_ms:
            wx.MessageBox(f"The entered time ({hours:02d}:{minutes:02d}:{seconds:02d}) exceeds the video duration.",
                "Invalid Time", wx.OK | wx.ICON_ERROR, self)
            return
        elif entered_total_ms < 0:
            wx.MessageBox("The entered time cannot be negative.",
                "Invalid Time", wx.OK | wx.ICON_ERROR, self)
            return

        self.selected_time_ms = entered_total_ms
        self.EndModal(wx.ID_OK)

    def get_selected_time_milliseconds(self):
        return self.selected_time_ms
