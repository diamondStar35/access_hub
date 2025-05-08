import wx
import wx.adv
import subprocess
import datetime
import json
import os  
import uuid
import app_vars

TASKS_JSON_FILE = "scheduled_tasks.json"

class TaskScheduler(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Task Scheduler", size=(600, 400))
        self.scheduled_tasks = []
        self.timers = {}

        self.SetBackgroundColour(wx.Colour(240, 240, 240))

        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(230, 230, 230))
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
        add_button.SetBackgroundColour(wx.Colour(100, 200, 150))
        add_button.SetForegroundColour(wx.Colour(255, 255, 255))
        add_button.Bind(wx.EVT_BUTTON, self.on_add_task_button_clicked) # Renamed for clarity
        vbox.Add(add_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        
        remove_button = wx.Button(panel, label="Remove Selected Task")
        remove_button.SetBackgroundColour(wx.Colour(200, 100, 100)) # Muted red
        remove_button.SetForegroundColour(wx.Colour(255, 255, 255))
        remove_button.Bind(wx.EVT_BUTTON, self.on_remove_selected_task)
        vbox.Add(remove_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        panel.SetSizer(vbox)        
        self._load_tasks()
        self.Bind(wx.EVT_CLOSE, self.on_close_frame)


    def _get_tasks_filepath(self):
        """Returns the full path to the tasks JSON file."""
        config_dir = wx.StandardPaths.Get().GetUserConfigDir()
        tasks_file = os.path.join(config_dir, app_vars.app_name, TASKS_JSON_FILE)
        app_dir = os.path.join(config_dir, app_vars.app_name, "subtitles")
        if not os.path.exists(app_dir):
            os.makedirs(config_dir)
        return tasks_file

    def _load_tasks(self):
        """Loads tasks from the JSON file."""
        filepath = self._get_tasks_filepath()
        if not os.path.exists(filepath):
            self.scheduled_tasks = []
            return

        try:
            with open(filepath, 'r') as f:
                tasks_data_from_json = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            wx.LogError(f"Error loading tasks from {filepath}: {e}")
            self.scheduled_tasks = []
            return
        
        now = datetime.datetime.now()
        valid_tasks_to_keep = []

        for task_data in tasks_data_from_json:
            try:
                run_time = datetime.datetime.fromisoformat(task_data['run_time_iso'])
                if run_time > now:
                    self.scheduled_tasks.append(task_data)
                    self._schedule_task_execution(task_data)
                    valid_tasks_to_keep.append(task_data)
            except (ValueError, KeyError) as e:
                wx.LogWarning(f"Skipping invalid task data during load: {task_data}. Error: {e}")
        
        if len(valid_tasks_to_keep) != len(tasks_data_from_json):
             self.scheduled_tasks = valid_tasks_to_keep
             self._save_tasks()
        self._refresh_task_list_display()

    def _save_tasks(self):
        """Saves the current list of scheduled_tasks to the JSON file."""
        filepath = self._get_tasks_filepath()
        try:
            with open(filepath, 'w') as f:
                json.dump(self.scheduled_tasks, f, indent=4)
        except IOError as e:
            wx.LogError(f"Error saving tasks to {filepath}: {e}")

    def _generate_task_id(self):
        """Generates a unique ID for a task."""
        return uuid.uuid4().hex

    def _refresh_task_list_display(self):
        """Clears and repopulates the wx.ListCtrl from self.scheduled_tasks."""
        self.task_list.DeleteAllItems()
        self.scheduled_tasks.sort(key=lambda t: datetime.datetime.fromisoformat(t['run_time_iso']))
        
        for i, task_data in enumerate(self.scheduled_tasks):
            run_time_dt = datetime.datetime.fromisoformat(task_data['run_time_iso'])
            time_str = run_time_dt.strftime("%Y-%m-%d %H:%M:%S")            
            display_details = task_data['details_str']

            index = self.task_list.InsertItem(self.task_list.GetItemCount(), task_data['name'])
            self.task_list.SetItem(index, 1, task_data['type'])
            self.task_list.SetItem(index, 2, time_str)
            self.task_list.SetItem(index, 3, display_details)
            self.task_list.SetItemData(index, i)


    def on_add_task_button_clicked(self, event):
        menu = wx.Menu()
        options = [
            ("Run a script", self.on_run_executable_dialog), # Dialog launchers
            ("Open a Website", self.on_open_website_dialog),
            ("Play a Media file", self.on_play_media_dialog),
            ("Send a reminder notification", self.on_send_notification_dialog),
        ]
        for label, handler in options:
            item = menu.Append(wx.ID_ANY, label)
            self.Bind(wx.EVT_MENU, handler, item)
        self.PopupMenu(menu)

    def _schedule_task_execution(self, task_data):
        """Schedules a wx.Timer for a given task_data object."""
        now = datetime.datetime.now()
        run_time = datetime.datetime.fromisoformat(task_data['run_time_iso'])        
        if run_time <= now:
            return

        delay_ms = int((run_time - now).total_seconds() * 1000)
        if delay_ms < 0: delay_ms = 0

        timer_wx_id = wx.NewId() 
        timer = wx.Timer(self, id=timer_wx_id)        
        task_id = task_data['id']
        task_type = task_data['type']
        details_for_action = task_data['details_for_action']

        if task_type == "Executable":
            self.Bind(wx.EVT_TIMER, lambda evt, p_id=task_id, path=details_for_action: self.run_script_action(evt, p_id, path), timer)
        elif task_type == "Website":
            self.Bind(wx.EVT_TIMER, lambda evt, p_id=task_id, url=details_for_action: self.open_website_action(evt, p_id, url), timer)
        elif task_type == "Notification":
            title, message = details_for_action['title'], details_for_action['message']
            self.Bind(wx.EVT_TIMER, lambda evt, p_id=task_id, t=title, m=message: self.send_notification_action(evt, p_id, t, m), timer)
        elif task_type == "Play Media":
            self.Bind(wx.EVT_TIMER, lambda evt, p_id=task_id, path=details_for_action: self.play_media_action(evt, p_id, path), timer)
        
        timer.StartOnce(delay_ms)
        self.timers[task_id] = timer

    def add_new_task_from_dialog(self, task_type, name, hours, minutes, details_for_action, details_display_str):
        if not name:
            wx.MessageBox("Task Name cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            return False

        if task_type == "Executable" and not details_for_action:
            wx.MessageBox("Script Path cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            return False
        if task_type == "Website" and not details_for_action:
            wx.MessageBox("Website URL cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            return False
        if task_type == "Play Media" and not details_for_action:
            wx.MessageBox("Media Path cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
            return False
        if task_type == "Notification":
            if not details_for_action['title'] or not details_for_action['message']:
                wx.MessageBox("Notification Title or Message cannot be empty.", "Error", wx.OK | wx.ICON_ERROR)
                return False

        task_id = self._generate_task_id()
        now = datetime.datetime.now()
        run_time = now + datetime.timedelta(hours=hours, minutes=minutes)

        task_data = {
            'id': task_id,
            'name': name,
            'type': task_type,
            'run_time_iso': run_time.isoformat(),
            'details_for_action': details_for_action,
            'details_str': details_display_str
        }
        self.scheduled_tasks.append(task_data)
        self._schedule_task_execution(task_data)
        self._save_tasks()
        self._refresh_task_list_display()
        return True


    def run_script_action(self, event, task_id, path):
        try:
            subprocess.run([path], check=True)
        except subprocess.CalledProcessError as e:
            wx.MessageBox(f"Error running script: {e}", "Error", wx.OK | wx.ICON_ERROR)
        except FileNotFoundError:
            wx.MessageBox("Script file not found.", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            self.remove_task_by_id(task_id)

    def open_website_action(self, event, task_id, url):
        try:
            wx.LaunchDefaultBrowser(url)
        except Exception as e:
            wx.MessageBox(f"Error opening website: {e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            self.remove_task_by_id(task_id)

    def send_notification_action(self, event, task_id, title, message):
        try:
            notification = wx.adv.NotificationMessage(title, message, parent=self, flags=wx.ICON_INFORMATION)
            notification.Show()
        except Exception as e:
            wx.MessageBox(f"Error sending notification: {e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            self.remove_task_by_id(task_id)
    
    def play_media_action(self, event, task_id, path):
        try:
            wx.LaunchDefaultApplication(path)
        except FileNotFoundError: # Should be Exception, wx.LaunchDefaultApplication doesn't raise FileNotFoundError directly.
            wx.MessageBox("Media file not found.", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e: 
            wx.MessageBox(f"Error opening media: {e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            self.remove_task_by_id(task_id) # Ensure removal even if action fails


    def remove_task_by_id(self, task_id_to_remove):
        """Removes a task by its persistent ID."""
        task_to_remove = None
        for task in self.scheduled_tasks:
            if task['id'] == task_id_to_remove:
                task_to_remove = task
                break
        
        if task_to_remove:
            self.scheduled_tasks.remove(task_to_remove)
            
            if task_id_to_remove in self.timers:
                timer = self.timers.pop(task_id_to_remove)
                if timer.IsRunning():
                    timer.Stop()            
            self._save_tasks()
            self._refresh_task_list_display()

    def on_remove_selected_task(self, event):
        selected_list_item_idx = self.task_list.GetFirstSelected()
        if selected_list_item_idx == -1:
            wx.MessageBox("Please select a task to remove.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return

        task_internal_idx = self.task_list.GetItemData(selected_list_item_idx)        
        if 0 <= task_internal_idx < len(self.scheduled_tasks):
            task_to_remove_data = self.scheduled_tasks[task_internal_idx]
            task_id = task_to_remove_data['id']
            
            confirm_dlg = wx.MessageDialog(self, 
                                           f"Are you sure you want to remove the task '{task_to_remove_data['name']}'?",
                                           "Confirm Removal",
                                           wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
            if confirm_dlg.ShowModal() == wx.ID_YES:
                self.remove_task_by_id(task_id)
            confirm_dlg.Destroy()
        else:
            wx.MessageBox("Error identifying selected task. Please try again.", "Error", wx.OK | wx.ICON_ERROR)


    def on_run_executable_dialog(self, event):
        dlg = RunExecutableDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            script_path = dlg.script_path_text.GetValue()
            self.add_new_task_from_dialog(
                task_type="Executable",
                name=dlg.name_text.GetValue(),
                hours=dlg.hours_spin.GetValue(),
                minutes=dlg.minutes_spin.GetValue(),
                details_for_action=script_path,
                details_display_str=script_path
            )
        dlg.Destroy()

    def on_open_website_dialog(self, event):
        dlg = OpenWebsiteDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            url = dlg.url_text.GetValue()
            self.add_new_task_from_dialog(
                task_type="Website",
                name=dlg.name_text.GetValue(),
                hours=dlg.hours_spin.GetValue(),
                minutes=dlg.minutes_spin.GetValue(),
                details_for_action=url,
                details_display_str=url
            )
        dlg.Destroy()

    def on_send_notification_dialog(self, event):
        dlg = SendNotificationDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            title = dlg.title_text.GetValue()
            message = dlg.message_text.GetValue()
            details_action = {'title': title, 'message': message}
            details_display = f"Title: {title}, Message: {message}"
            self.add_new_task_from_dialog(
                task_type="Notification",
                name=dlg.name_text.GetValue(),
                hours=dlg.hours_spin.GetValue(),
                minutes=dlg.minutes_spin.GetValue(),
                details_for_action=details_action,
                details_display_str=details_display
            )
        dlg.Destroy()

    def on_play_media_dialog(self, event):
        dlg = PlayMediaDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            media_path = dlg.media_path_text.GetValue()
            self.add_new_task_from_dialog(
                task_type="Play Media",
                name=dlg.name_text.GetValue(),
                hours=dlg.hours_spin.GetValue(),
                minutes=dlg.minutes_spin.GetValue(),
                details_for_action=media_path,
                details_display_str=media_path
            )
        dlg.Destroy()

    def on_close_frame(self, event):
        # Stop all running timers associated with this frame to prevent issues
        for task_id, timer in list(self.timers.items()):
            if timer.IsRunning():
                timer.Stop()
        self.timers.clear()
        event.Skip()


class RunExecutableDialog(wx.Dialog): # No changes needed inside this class
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


class OpenWebsiteDialog(wx.Dialog): # No changes needed inside this class
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


class SendNotificationDialog(wx.Dialog): # No changes needed inside this class
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


class PlayMediaDialog(wx.Dialog): # No changes needed inside this class
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
