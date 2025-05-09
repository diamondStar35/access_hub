import wx

class RunExecutableDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Run Executable", size=(400, 250))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        name_label = wx.StaticText(panel, label="Task Name:")
        vbox.Add(name_label, 0, wx.ALL, 5)
        self.name_text = wx.TextCtrl(panel)
        vbox.Add(self.name_text, 0, wx.EXPAND | wx.ALL, 5)

        time_label = wx.StaticText(panel, label="Hours:")
        vbox.Add(time_label, 0, wx.ALL, 5)

        time_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.hours_spin = wx.SpinCtrl(panel, min=0, max=23, initial=0)
        time_hbox.Add(self.hours_spin, 0, wx.ALL, 5)

        minutes_label = wx.StaticText(panel, label="Minutes")
        time_hbox.Add(minutes_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.minutes_spin = wx.SpinCtrl(panel, min=0, max=59, initial=0)
        time_hbox.Add(self.minutes_spin, 0, wx.ALL, 5)
        vbox.Add(time_hbox, 0, wx.ALL, 5)

        script_label = wx.StaticText(panel, label="Script Path:")
        vbox.Add(script_label, 0, wx.ALL, 5)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.script_path_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        hbox.Add(self.script_path_text, 1, wx.EXPAND | wx.ALL, 5)

        browse_button = wx.Button(panel, label="Browse")
        browse_button.Bind(wx.EVT_BUTTON, self.on_browse)
        hbox.Add(browse_button, 0, wx.ALL, 5)
        vbox.Add(hbox, 0, wx.EXPAND | wx.ALL, 5)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        button_sizer.AddButton(ok_button)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 10)
        panel.SetSizer(vbox)

    def on_browse(self, event):
        dlg = wx.FileDialog(self, "Choose Script File", wildcard="*.py;*.bat;*.exe;*.cmd;*.ps1;*.reg", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.script_path_text.SetValue(dlg.GetPath())
        dlg.Destroy()


class OpenWebsiteDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Open Website", size=(400, 200))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        name_label = wx.StaticText(panel, label="Task Name:")
        vbox.Add(name_label, 0, wx.ALL, 5)
        self.name_text = wx.TextCtrl(panel)
        vbox.Add(self.name_text, 0, wx.EXPAND | wx.ALL, 5)

        time_label = wx.StaticText(panel, label="Hours:")
        vbox.Add(time_label, 0, wx.ALL, 5)

        time_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.hours_spin = wx.SpinCtrl(panel, min=0, max=23, initial=0)
        time_hbox.Add(self.hours_spin, 0, wx.ALL, 5)

        minutes_label = wx.StaticText(panel, label="Minutes")
        time_hbox.Add(minutes_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.minutes_spin = wx.SpinCtrl(panel, min=0, max=59, initial=0)
        time_hbox.Add(self.minutes_spin, 0, wx.ALL, 5)
        vbox.Add(time_hbox, 0, wx.ALL, 5)

        url_label = wx.StaticText(panel, label="Website URL:")
        vbox.Add(url_label, 0, wx.ALL, 5)
        self.url_text = wx.TextCtrl(panel)
        vbox.Add(self.url_text, 0, wx.EXPAND | wx.ALL, 5)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        button_sizer.AddButton(ok_button)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 10)
        panel.SetSizer(vbox)


class SendNotificationDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Send Notification", size=(400, 250))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        name_label = wx.StaticText(panel, label="Task Name:")
        vbox.Add(name_label, 0, wx.ALL, 5)
        self.name_text = wx.TextCtrl(panel)
        vbox.Add(self.name_text, 0, wx.EXPAND | wx.ALL, 5)

        time_label = wx.StaticText(panel, label="Hours:")
        vbox.Add(time_label, 0, wx.ALL, 5)

        time_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.hours_spin = wx.SpinCtrl(panel, min=0, max=23, initial=0)
        time_hbox.Add(self.hours_spin, 0, wx.ALL, 5)

        minutes_label = wx.StaticText(panel, label="Minutes")
        time_hbox.Add(minutes_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.minutes_spin = wx.SpinCtrl(panel, min=0, max=59, initial=0)
        time_hbox.Add(self.minutes_spin, 0, wx.ALL, 5)
        vbox.Add(time_hbox, 0, wx.ALL, 5)

        title_label = wx.StaticText(panel, label="Notification Title:")
        vbox.Add(title_label, 0, wx.ALL, 5)
        self.title_text = wx.TextCtrl(panel)
        vbox.Add(self.title_text, 0, wx.EXPAND | wx.ALL, 5)

        message_label = wx.StaticText(panel, label="Notification Message:")
        vbox.Add(message_label, 0, wx.ALL, 5)
        self.message_text = wx.TextCtrl(panel)
        vbox.Add(self.message_text, 0, wx.EXPAND | wx.ALL, 5)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        button_sizer.AddButton(ok_button)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 10)
        panel.SetSizer(vbox)


class PlayMediaDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Play Media", size=(400, 250))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        name_label = wx.StaticText(panel, label="Task Name:")
        vbox.Add(name_label, 0, wx.ALL, 5)
        self.name_text = wx.TextCtrl(panel)
        vbox.Add(self.name_text, 0, wx.EXPAND | wx.ALL, 5)

        time_label = wx.StaticText(panel, label="Hours:")
        vbox.Add(time_label, 0, wx.ALL, 5)

        time_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.hours_spin = wx.SpinCtrl(panel, min=0, max=23, initial=0)
        time_hbox.Add(self.hours_spin, 0, wx.ALL, 5)

        minutes_label = wx.StaticText(panel, label="Minutes")
        time_hbox.Add(minutes_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.minutes_spin = wx.SpinCtrl(panel, min=0, max=59, initial=0)
        time_hbox.Add(self.minutes_spin, 0, wx.ALL, 5)
        vbox.Add(time_hbox, 0, wx.ALL, 5)

        media_label = wx.StaticText(panel, label="Media File Path:")
        vbox.Add(media_label, 0, wx.ALL, 5)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.media_path_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        hbox.Add(self.media_path_text, 1, wx.EXPAND | wx.ALL, 5)

        browse_button = wx.Button(panel, label="Browse")
        browse_button.Bind(wx.EVT_BUTTON, self.on_browse)
        hbox.Add(browse_button, 0, wx.ALL, 5)
        vbox.Add(hbox, 0, wx.EXPAND | wx.ALL, 5)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        button_sizer.AddButton(ok_button)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 10)
        panel.SetSizer(vbox)

    def on_browse(self, event):
        wildcard = "Media Files (*.mp3;*.mp4;*.wav;*.avi;*.mkv)|*.mp3;*.mp4;*.wav;*.avi;*.mkv|All Files (*.*)|*.*"
        dlg = wx.FileDialog(self, "Choose Media File", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.media_path_text.SetValue(dlg.GetPath())
        dlg.Destroy()
