import wx
import wx.adv
import subprocess
import datetime


class TaskScheduler(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Task Scheduler", size=(600, 400))
        self.timers = {}
        self.SetBackgroundColour(wx.Colour(240, 240, 240))  # Light gray

        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(230, 230, 230)) # Slightly darker gray
        vbox = wx.BoxSizer(wx.VERTICAL)

        tasks_label = wx.StaticText(panel, label="Scheduled Tasks:")
        vbox.Add(tasks_label, 0, wx.ALL, 5)

        self.task_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_VRULES | wx.BORDER_SIMPLE)
        self.task_list.InsertColumn(0, "Name")
        self.task_list.InsertColumn(1, "Type")
        self.task_list.InsertColumn(2, "Time")
        self.task_list.InsertColumn(3, "Details")
        self.task_list.SetBackgroundColour(wx.Colour(250, 250, 250))
        self.task_list.SetTextColour(wx.Colour(30, 30, 30))
        vbox.Add(self.task_list, 1, wx.EXPAND | wx.ALL, 10)

        add_button = wx.Button(panel, label="Add Task")
        add_button.SetBackgroundColour(wx.Colour(100, 200, 150))  # Muted green
        add_button.SetForegroundColour(wx.Colour(255, 255, 255))
        add_button.Bind(wx.EVT_BUTTON, self.on_add_task)
        vbox.Add(add_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        panel.SetSizer(vbox)


    def on_add_task(self, event):
        menu = wx.Menu()
        options = [
            ("Run a script", self.on_run_executable),
            ("Open a Website", self.on_open_website),
            ("Play a Media file", self.on_play_media),
            ("Send a reminder notification", self.on_send_notification),
        ]
        for label, handler in options:
            item = menu.Append(wx.ID_ANY, label)
            self.Bind(wx.EVT_MENU, handler, item)
        self.PopupMenu(menu)

    def add_task(self, task_type, name, hours, minutes, details):
        if not name:
            wx.MessageBox("Task Name cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            return

        if task_type == "Executable" and not details:
            wx.MessageBox("Script Path cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            return

        if task_type == "Website" and not details:
            wx.MessageBox("Website URL cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            return

        if task_type == "Play Media" and not details:
            wx.MessageBox("Media Path cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            return

        if task_type == "Notification":
            title, message = details.split(", Message: ")
            title = title.replace("Title: ", "")
            if not title or not message:
                wx.MessageBox("Notification Title or Message cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
                return

        now = datetime.datetime.now()
        run_time = now + datetime.timedelta(hours=hours, minutes=minutes) #Correctly add time

        time_str = run_time.strftime("%Y-%m-%d %H:%M:%S")
        index = self.task_list.InsertItem(self.task_list.GetItemCount(), name)
        self.task_list.SetItem(index, 1, task_type)
        self.task_list.SetItem(index, 2, time_str)
        self.task_list.SetItem(index, 3, details)

        delay_ms = int((run_time - now).total_seconds() * 1000)
        timer = wx.Timer(self, id=index)

        if task_type == "Executable":
            self.Bind(wx.EVT_TIMER, lambda evt, path=details: self.run_script(evt, path), timer)
        elif task_type == "Website":
            self.Bind(wx.EVT_TIMER, lambda evt, url=details: self.open_website(evt, url), timer)
        elif task_type == "Notification":
            title, message = details.split(", Message: ")
            title = title.replace("Title: ", "")
            self.Bind(wx.EVT_TIMER, lambda evt, title=title, message=message: self.send_notification(evt, title, message), timer)
        elif task_type == "Play Media": #Media
            self.Bind(wx.EVT_TIMER, lambda evt, path=details: self.play_media(evt, path), timer) #Bind and pass detail
        timer.StartOnce(delay_ms)
        self.timers[index] = timer

    def on_run_executable(self, event): # Modified to use add_task
        dlg = RunExecutableDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            self.add_task("Executable", dlg.name_text.GetValue(), dlg.hours_spin.GetValue(),
                          dlg.minutes_spin.GetValue(), dlg.script_path_text.GetValue())
        dlg.Destroy()

    def run_script(self, event, path):  # Added error handling
        try:
            subprocess.run([path], check=True)
        except subprocess.CalledProcessError as e:
            wx.MessageBox(f"Error running script: {e}", "Error", wx.OK | wx.ICON_ERROR)
        except FileNotFoundError:
            wx.MessageBox("Script file not found.", "Error", wx.OK | wx.ICON_ERROR)
        self.remove_task(event)

    def on_play_media(self, event):
        dlg = PlayMediaDialog(self)  # Assuming you have a PlayMediaDialog class
        if dlg.ShowModal() == wx.ID_OK:
            self.add_task("Play Media", dlg.name_text.GetValue(), dlg.hours_spin.GetValue(),
                          dlg.minutes_spin.GetValue(), dlg.media_path_text.GetValue())
        dlg.Destroy()

    def play_media(self, event, path):
        try:
            wx.LaunchDefaultApplication(path)
        except FileNotFoundError:
            wx.MessageBox("Media file not found.", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e: #catches other potential exceptions during file opening
            wx.MessageBox(f"Error opening media: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_open_website(self, event):
        dlg = OpenWebsiteDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            self.add_task("Website", dlg.name_text.GetValue(), dlg.hours_spin.GetValue(),
                          dlg.minutes_spin.GetValue(), dlg.url_text.GetValue())
        dlg.Destroy()

    def on_send_notification(self, event):
        dlg = SendNotificationDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            self.add_task("Notification", dlg.name_text.GetValue(), dlg.hours_spin.GetValue(),
                          dlg.minutes_spin.GetValue(),
                          f"Title: {dlg.title_text.GetValue()}, Message: {dlg.message_text.GetValue()}")
        dlg.Destroy()

    def open_website(self, event, url):
        try:
            wx.LaunchDefaultBrowser(url)
        except Exception as e:
            wx.MessageBox(f"Error opening website: {e}", "Error", wx.OK | wx.ICON_ERROR)
        self.remove_task(event)


    def send_notification(self, event, title, message):
        try:
            notification = wx.adv.NotificationMessage(title, message, parent=self, flags=wx.ICON_INFORMATION)
            notification.Show()
        except Exception as e:
            wx.MessageBox(f"Error sending notification: {e}", "Error", wx.OK | wx.ICON_ERROR)
        self.remove_task(event)

    def remove_task(self, event):
        index = event.GetId()
        if index in self.timers:
            try:
                self.task_list.DeleteItem(index)
                del self.timers[index]
            except RuntimeError:
                pass


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

        time_label = wx.StaticText(panel, label="Hours:")  # Corrected label
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
        wildcard = "Media Files (*.mp3;*.mp4;*.wav;*.avi;*.mkv)|*.mp3;*.mp4;*.wav;*.avi;*.mkv|All Files (*.*)|*.*" # Added media file types
        dlg = wx.FileDialog(self, "Choose Media File", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.media_path_text.SetValue(dlg.GetPath())
        dlg.Destroy()
