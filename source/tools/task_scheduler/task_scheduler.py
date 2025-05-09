import wx
import wx.adv
from .alarm_settings import AlarmSettingsDialog
from .alarm_notification import AlarmNotificationFrame
from .tasks import RunExecutableDialog, OpenWebsiteDialog, SendNotificationDialog, PlayMediaDialog
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
        app_dir = os.path.join(config_dir, app_vars.app_name)
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
            if not isinstance(tasks_data_from_json, list):
                 wx.MessageBox(f"Invalid data format in tasks file: {filepath}. Expected a list.",
                               "File Error", wx.OK | wx.ICON_ERROR)
                 self.scheduled_tasks = []
                 return
        except (IOError, json.JSONDecodeError) as e:
            wx.MessageBox(f"Error loading tasks from {filepath}:\n{e}", "File Error", wx.OK | wx.ICON_ERROR)
            self.scheduled_tasks = []
            return
        except Exception as e:
            wx.MessageBox(f"An unexpected error occurred loading tasks from {filepath}:\n{e}",
                           "File Error", wx.OK | wx.ICON_ERROR)
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
                pass

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
        # Sort tasks by their next run time for better readability
        sortable_tasks = []
        for t in self.scheduled_tasks:
            try:
                datetime.datetime.fromisoformat(t.get('run_time_iso'))
                sortable_tasks.append(t)
            except (ValueError, TypeError):
                 pass

        try:
             sortable_tasks.sort(key=lambda t: datetime.datetime.fromisoformat(t['run_time_iso']))
        except (TypeError, ValueError) as e:
            sortable_tasks = [t for t in self.scheduled_tasks]

        displayed_indices = set() # Keep track of original indices added to the list control
        for task_data in sortable_tasks:
            task_id_persistent = task_data.get('id', None)
            if task_id_persistent is None:
                 continue

            try:
                original_index_in_list = self.scheduled_tasks.index(task_data)
            except ValueError:
                 continue

            if original_index_in_list in displayed_indices:
                 continue

            try:
                run_time_dt = datetime.datetime.fromisoformat(task_data.get('run_time_iso'))
                time_str = run_time_dt.strftime("%Y-%m-%d %I:%M:%S %p") # Show AM/PM
            except (ValueError, KeyError, TypeError):
                time_str = "Invalid Time" # Fallback for bad data

            display_details = task_data.get('details_str', 'N/A')
            task_name = task_data.get('name', 'Unnamed Task')
            task_type = task_data.get('type', 'Unknown')
            
            list_idx = self.task_list.GetItemCount()
            index = self.task_list.InsertItem(list_idx, task_name)
            self.task_list.SetItem(index, 1, task_type)
            self.task_list.SetItem(index, 2, time_str)
            self.task_list.SetItem(index, 3, display_details)
            self.task_list.SetItemData(index, original_index_in_list) 
            displayed_indices.add(original_index_in_list)

        for original_index, task_data in enumerate(self.scheduled_tasks):
            if original_index not in displayed_indices:
                 task_id_persistent = task_data.get('id', None)
                 list_idx = self.task_list.GetItemCount()
                 index = self.task_list.InsertItem(list_idx, task_data.get('name', 'Unnamed Task'))
                 self.task_list.SetItem(index, 1, task_data.get('type', 'Unknown') + " (Error)")
                 self.task_list.SetItem(index, 2, "N/A") # Time N/A if not sortable
                 self.task_list.SetItem(index, 3, task_data.get('details_str', 'N/A') + " (Data Error)")
                 self.task_list.SetItemData(index, original_index)


    def on_add_task_button_clicked(self, event):
        menu = wx.Menu()
        options = [
            ("Run a script", self.on_run_executable),
            ("Schedule Alarm", self.on_add_alarm),
            ("Open a Website", self.on_open_website),
            ("Play a Media file", self.on_play_media),
            ("Send a reminder notification", self.on_send_notification),
        ]
        for label, handler in options:
            item = menu.Append(wx.ID_ANY, label)
            self.Bind(wx.EVT_MENU, handler, item)
        self.PopupMenu(menu)

    def add_task(self, task_type, name, hours_offset=None, minutes_offset=None, absolute_run_time=None,
                 details_for_action=None, details_display_str=""):
        """
        Adds a new task to the scheduler.
        Uses hours_offset/minutes_offset for relative time (RunScript, Website, etc.)
        Uses absolute_run_time for precise time (Alarms, Snoozes).
        """
        if not name:
            wx.MessageBox("Task Name cannot be empty.", "Input Error", wx.OK | wx.ICON_ERROR); return False

        # Determine the exact run time
        run_time = None
        if absolute_run_time is not None and isinstance(absolute_run_time, datetime.datetime):
            run_time = absolute_run_time
        elif hours_offset is not None and minutes_offset is not None:
            now = datetime.datetime.now()
            run_time = now + datetime.timedelta(hours=hours_offset, minutes=minutes_offset)
        else:
            wx.MessageBox(f"Invalid time specification for task '{name}'. Use either offset or absolute time.",
                          "Scheduling Error", wx.OK | wx.ICON_ERROR); return False

        if run_time <= datetime.datetime.now():
             # Allow a small grace period for tasks scheduled very soon
             if (datetime.datetime.now() - run_time).total_seconds() > 5:
                 wx.MessageBox(f"Scheduled time for task '{name}' ({run_time.strftime('%Y-%m-%d %H:%M:%S')}) is in the past.",
                               "Scheduling Error", wx.OK | wx.ICON_ERROR); return False
        
        if task_type == "Executable" and not details_for_action:
            wx.MessageBox("Script Path cannot be empty.", "Input Error", wx.OK | wx.ICON_ERROR, self); return False
        if task_type == "Website" and not details_for_action:
            wx.MessageBox("Website URL cannot be empty.", "Input Error", wx.OK | wx.ICON_ERROR, self); return False
        if task_type == "Play Media" and not details_for_action:
            wx.MessageBox("Media Path cannot be empty.", "Input Error", wx.OK | wx.ICON_ERROR, self); return False
        if task_type == "Notification":
            if not isinstance(details_for_action, dict) or not details_for_action.get('title') or not details_for_action.get('message'):
                 wx.MessageBox("Notification Title or Message cannot be empty.", "Input Error", wx.OK | wx.ICON_ERROR, self); return False

        task_id = self._generate_task_id()
        task_data = {
            'id': task_id, 'name': name, 'type': task_type,
            'run_time_iso': run_time.isoformat(),
            'details_for_action': details_for_action,
            'details_str': details_display_str
        }

        self.scheduled_tasks.append(task_data)
        self._schedule_task_execution(task_data)
        self._save_tasks()
        self._refresh_task_list_display()
        return True

    def _schedule_task_execution(self, task_data):
        """Schedules a wx.Timer for a given task_data object."""
        now = datetime.datetime.now()
        try:
            run_time = datetime.datetime.fromisoformat(task_data.get('run_time_iso'))
            if run_time is None: raise ValueError("run_time_iso is None")
        except (ValueError, TypeError) as e:
            wx.MessageBox(f"Error: Invalid or missing run_time_iso format for task '{task_data.get('name', 'Unnamed Task')}' (ID: {task_data.get('id', 'No ID')}). Skipping schedule. Error: {e}",
                          "Scheduling Error", wx.OK | wx.ICON_ERROR)
            return

        # Calculate delay, ensuring it's non-negative
        delay_seconds = (run_time - now).total_seconds()
        delay_ms = int(max(0, delay_seconds) * 1000)

        timer_wx_id = wx.NewIdRef().GetId()
        timer = wx.Timer(self, id=timer_wx_id)
        task_id_persistent = task_data['id']
        task_type = task_data.get('type', 'Unknown')
        details_for_action = task_data.get('details_for_action')

        # Ensure timer is not already running for this task ID (can happen on reload if old timer didn't clean up)
        if task_id_persistent in self.timers:
             old_timer = self.timers[task_id_persistent]
             if old_timer.IsRunning():
                 old_timer.Stop()
             old_timer.Destroy()
             del self.timers[task_id_persistent]

        if task_type == "Executable":
            self.Bind(wx.EVT_TIMER, lambda evt, p_id=task_id_persistent, path=details_for_action: self.run_script(evt, p_id, path), timer)
        elif task_type == "Website":
            self.Bind(wx.EVT_TIMER, lambda evt, p_id=task_id_persistent, url=details_for_action: self.open_website(evt, p_id, url), timer)
        elif task_type == "Notification":
            title = details_for_action.get('title', 'Notification') if isinstance(details_for_action, dict) else 'Notification'
            message = details_for_action.get('message', 'Time to do something!') if isinstance(details_for_action, dict) else 'Time to do something!'
            self.Bind(wx.EVT_TIMER, lambda evt, p_id=task_id_persistent, t=title, m=message: self.send_notification(evt, p_id, t, m), timer)
        elif task_type == "Play Media":
            self.Bind(wx.EVT_TIMER, lambda evt, p_id=task_id_persistent, path=details_for_action: self.play_media(evt, p_id, path), timer)
        elif task_type == "Alarm":
            if not isinstance(details_for_action, dict):
                 wx.MessageBox(f"Error: Alarm task '{task_data.get('name', 'Unnamed')}' has invalid details.",
                               "Scheduling Error", wx.OK | wx.ICON_ERROR, self)
                 timer.Destroy(); return # Cannot schedule if details are bad
            self.Bind(wx.EVT_TIMER,
                      lambda evt, p_id=task_id_persistent, settings=details_for_action: \
                      self.trigger_alarm_action(evt, p_id, settings), timer)
        else:
            wx.MessageBox(f"Warning: Unknown task type '{task_type}' for task ID {task_id_persistent}. Cannot bind timer.",
                          "Scheduling Warning", wx.OK | wx.ICON_WARNING)
            timer.Destroy()
            return
            
        timer.StartOnce(delay_ms)
        self.timers[task_id_persistent] = timer


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

    def on_add_alarm(self, event):
        """Handles opening alarm settings dialog and adding the task."""
        dlg = AlarmSettingsDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            settings = dlg.GetAlarmSettings()
            if settings:
                # settings dictionary returned from dialog contains all user choices
                # Prepare details_for_action from this dictionary
                details_action = {
                    "alarm_name": settings["name"],
                    # Store original configured time for recurrence calculations
                    "original_hour": settings["time"]["hour"],
                    "original_minute": settings["time"]["minute"],
                    "original_second": settings["time"]["second"],
                    # Store original configured date for recurrence reference ("Weekly")
                    "original_day": settings["date"]["day"],
                    "original_month": settings["date"]["month"],
                    "original_year": settings["date"]["year"], # Current year at time of setting
                    "schedule_type": settings["schedule"]["type"],
                    "schedule_details": settings["schedule"].get("days"), # e.g., ["Mon", "Fri"] or None for "Custom Days"
                    "sound_path": settings["sound"]["path"],
                    "is_custom_sound": settings["sound"]["is_custom"],
                    "snooze_total_times": settings["snooze"]["count"], # Total number of snoozes allowed for this recurring pattern
                    "snooze_interval_minutes": settings["snooze"]["interval"]
                }
                
                # Calculate the *very first* run time based on settings
                first_run_dt = self._calculate_next_alarm_run_time(
                    base_year=settings["date"]["year"], # Use configured date for first calculation
                    base_month=settings["date"]["month"],
                    base_day=settings["date"]["day"],
                    hour=settings["time"]["hour"],
                    minute=settings["time"]["minute"],
                    second=settings["time"]["second"],
                    schedule_type=settings["schedule"]["type"],
                    schedule_details=settings["schedule"].get("days"),
                    base_datetime_for_next=None # Calculate first occurrence from or after now
                )

                if not first_run_dt:
                    # Message already shown in _calculate_next_alarm_run_time or here
                    dlg.Destroy(); return

                # Add current_run_xyz to details_action for tracking THIS specific trigger time
                details_action["current_run_year"] = first_run_dt.year
                details_action["current_run_month"] = first_run_dt.month
                details_action["current_run_day"] = first_run_dt.day
                details_action["current_run_hour"] = first_run_dt.hour
                details_action["current_run_minute"] = first_run_dt.minute
                details_action["current_run_second"] = first_run_dt.second
                
                display_str = f"{settings['name']} ({settings['schedule']['type']}) - Sound: {settings['sound']['name_for_display']}"

                self.add_task( # Use the general add_task method
                    task_type="Alarm",
                    name=settings["name"],
                    absolute_run_time=first_run_dt, # Pass calculated absolute time
                    details_for_action=details_action, # Pass the full settings dict
                    details_display_str=display_str
                )
        dlg.Destroy()

    def trigger_alarm_action(self, event, task_id, alarm_settings_from_task):
        """Called when an alarm's wx.Timer fires. Launches notification and handles recurrence."""
        current_task_data = None
        task_idx_in_list = -1
        for i, t_data in enumerate(self.scheduled_tasks):
            if t_data.get('id') == task_id:
                current_task_data = t_data
                task_idx_in_list = i
                break
        
        if not current_task_data:
            return

        # Ensure alarm_settings_from_task is a dict and has required keys for recurrence logic
        if not isinstance(alarm_settings_from_task, dict) or \
           not all(k in alarm_settings_from_task for k in ["schedule_type", "original_year", "original_month", "original_day",
                                                          "original_hour", "original_minute", "original_second",
                                                          "current_run_year", "current_run_month", "current_run_day",
                                                          "current_run_hour", "current_run_minute", "current_run_second"]):
            wx.MessageBox(f"Error: Alarm task '{current_task_data.get('name', 'Unnamed')}' "
                          f"has missing or invalid settings for triggering recurrence. Removing it.",
                          "Alarm Error", wx.OK | wx.ICON_ERROR, self)
            wx.CallAfter(self.remove_task_by_id, task_id)
            return

        alarm_frame = AlarmNotificationFrame(parent=None,
                                             alarm_settings_dict=dict(alarm_settings_from_task),
                                             task_scheduler_ref=self,
                                             task_id_original_alarm=task_id)

        schedule_type = alarm_settings_from_task["schedule_type"]
        if schedule_type == "Once":
            wx.CallAfter(self.remove_task_by_id, task_id)
        else:
            try:
                last_triggered_dt = datetime.datetime(
                    year=int(alarm_settings_from_task["current_run_year"]),
                    month=int(alarm_settings_from_task["current_run_month"]),
                    day=int(alarm_settings_from_task["current_run_day"]),
                    hour=int(alarm_settings_from_task["current_run_hour"]),
                    minute=int(alarm_settings_from_task["current_run_minute"]),
                    second=int(alarm_settings_from_task["current_run_second"])
                )
            except (KeyError, ValueError, TypeError) as e:
                 wx.MessageBox(f"Error parsing last triggered time for recurring alarm (Name: {alarm_settings_from_task.get('alarm_name', 'Unnamed')}). Cannot reliably reschedule. Error: {e}",
                               "Alarm Error", wx.OK | wx.ICON_ERROR)
                 wx.CallAfter(self.remove_task_by_id, task_id)
                 return

            next_run_dt = self._calculate_next_alarm_run_time(
                base_year=int(alarm_settings_from_task["original_year"]),
                base_month=int(alarm_settings_from_task["original_month"]),
                base_day=int(alarm_settings_from_task["original_day"]),
                hour=int(alarm_settings_from_task["original_hour"]),
                minute=int(alarm_settings_from_task["original_minute"]),
                second=int(alarm_settings_from_task["original_second"]),
                schedule_type=schedule_type,
                schedule_details=alarm_settings_from_task.get("schedule_details"),
                base_datetime_for_next=last_triggered_dt
            )

            if next_run_dt:
                current_task_data['run_time_iso'] = next_run_dt.isoformat()
                current_task_data['details_for_action']["current_run_year"] = next_run_dt.year
                current_task_data['details_for_action']["current_run_month"] = next_run_dt.month
                current_task_data['details_for_action']["current_run_day"] = next_run_dt.day
                current_task_data['details_for_action']["current_run_hour"] = next_run_dt.hour
                current_task_data['details_for_action']["current_run_minute"] = next_run_dt.minute
                current_task_data['details_for_action']["current_run_second"] = next_run_dt.second
                
                self._save_tasks()
                self._refresh_task_list_display()

                if task_id in self.timers:
                    del self.timers[task_id]

                self._schedule_task_execution(current_task_data)
            else:
                wx.CallAfter(self.remove_task_by_id, task_id)

    def _calculate_next_alarm_run_time(self, base_year, base_month, base_day,
                                    hour, minute, second,
                                    schedule_type, schedule_details,
                                    base_datetime_for_next=None):
        """
        Calculates the next valid run time for an alarm based on schedule type and details.
        Returns a datetime object or None.
        base_year/month/day is the original configured date, used for Weekly/Custom patterns.
        """
        try:
            target_time = datetime.time(hour, minute, second)
        except ValueError:
            wx.MessageBox(f"Invalid time components provided for alarm: {hour}:{minute}:{second}.",
                          "Scheduling Error", wx.OK | wx.ICON_ERROR); return None

        now_dt = datetime.datetime.now()
        if schedule_type == "Once":
            try:
                once_dt = datetime.datetime(base_year, base_month, base_day, hour, minute, second)
                if base_datetime_for_next is None and once_dt <= now_dt:
                    if (now_dt - once_dt).total_seconds() > 5:
                         wx.MessageBox(f"'Once' alarm date/time for {once_dt.strftime('%Y-%m-%d %I:%M:%S %p')} is in the past.",
                                       "Scheduling Error", wx.OK | wx.ICON_ERROR)
                    return None
                return once_dt
            except ValueError:
                wx.MessageBox(f"Invalid date for 'Once' alarm: {base_year}-{base_month}-{base_day}.",
                              "Scheduling Error", wx.OK | wx.ICON_ERROR); return None

        start_search_dt = base_datetime_for_next if base_datetime_for_next else now_dt
        # For recurrence calculation, start checking dates from today or the day after the last trigger.
        start_checking_date = start_search_dt.date()
        if base_datetime_for_next: # If rescheduling from a past trigger, start check from next day
            start_checking_date = base_datetime_dt.date() + datetime.timedelta(days=1)
        else:
             if target_time <= now_dt.time():
                  start_checking_date = now_dt.date() + datetime.timedelta(days=1)
             else:
                  start_checking_date = now_dt.date()
        current_candidate_date = start_checking_date
        day_map_to_int = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
        int_to_day_map = {v: k for k, v in day_map_to_int.items()}

        original_weekday_int = None
        try:
             original_weekday_int = datetime.date(base_year, base_month, base_day).weekday()
        except ValueError:
             wx.MessageBox(f"Invalid original base date for recurring alarm: {base_year}-{base_month}-{base_day}.",
                           "Scheduling Error", wx.OK | wx.ICON_ERROR); return None

        for _ in range(730):
            next_potential_run_datetime = datetime.datetime.combine(current_candidate_date, target_time)
            is_valid_day = False
            if schedule_type == "Daily":
                is_valid_day = True
            elif schedule_type == "Weekly":
                if current_candidate_date.weekday() == original_weekday_int:
                    is_valid_day = True
            elif schedule_type == "Custom Days":
                if not schedule_details:
                    wx.MessageBox("'Custom Days' selected but no days specified.", "Scheduling Error", wx.OK | wx.ICON_ERROR, self); return None
                target_weekdays_int = [day_map_to_int[d_str] for d_str in schedule_details if d_str in day_map_to_int]
                if current_candidate_date.weekday() in target_weekdays_int:
                    is_valid_day = True
            else:
                 wx.MessageBox(f"Unknown schedule type: {schedule_type}.", "Scheduling Error", wx.OK | wx.ICON_ERROR); return None

            if is_valid_day:
                 # Found a valid date. Now check if the time on that date is in the future
                 # relative to when we started searching (last trigger time or now).
                 if next_potential_run_datetime > start_search_dt:
                      return next_potential_run_datetime

            current_candidate_date += datetime.timedelta(days=1)
        wx.MessageBox(f"Could not find a future run time for recurring alarm within search limit ({schedule_type}, {schedule_details}).",
                      "Scheduling Warning", wx.OK | wx.ICON_WARNING); return None

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
        index_to_remove = -1
        # Find the task in the list by its persistent ID
        for i, task in enumerate(self.scheduled_tasks):
            if task.get('id') == task_id_to_remove:
                task_to_remove = task
                index_to_remove = i
                break
        
        if task_to_remove:
            if index_to_remove != -1:
                 del self.scheduled_tasks[index_to_remove]
            else:
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
            task_id = task_to_remove_data.get('id') # Get the persistent ID from the task data
            if task_id is None:
                 wx.MessageBox("Error identifying selected task (missing ID). Please try again.", "Error", wx.OK | wx.ICON_ERROR, self)
                 return
            
            confirm_dlg = wx.MessageDialog(self, 
                                           f"Are you sure you want to remove the task '{task_to_remove_data.get('name', 'Unnamed Task')}'?",
                                           "Confirm Removal",
                                           wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
            if confirm_dlg.ShowModal() == wx.ID_YES:
                self.remove_task_by_id(task_id)
            confirm_dlg.Destroy()
        else:
            wx.MessageBox("Error identifying selected task (invalid index). Please refresh the list and try again.", "Error", wx.OK | wx.ICON_ERROR)
            self._refresh_task_list_display()

    def on_run_executable(self, event):
        dlg = RunExecutableDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.name_text.GetValue()
            hours = dlg.hours_spin.GetValue()
            minutes = dlg.minutes_spin.GetValue()
            script_path = dlg.script_path_text.GetValue()
            
            self.add_task(
                task_type="Executable", name=name,
                hours_offset=hours, minutes_offset=minutes,
                details_for_action=script_path, details_display_str=script_path
            )
        dlg.Destroy()

    def on_open_website(self, event):
        dlg = OpenWebsiteDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.name_text.GetValue()
            hours = dlg.hours_spin.GetValue()
            minutes = dlg.minutes_spin.GetValue()
            url = dlg.url_text.GetValue()
            
            self.add_task(
                task_type="Website", name=name,
                hours_offset=hours, minutes_offset=minutes,
                details_for_action=url, details_display_str=url
            )
        dlg.Destroy()

    def on_send_notification(self, event):
        dlg = SendNotificationDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.name_text.GetValue()
            hours = dlg.hours_spin.GetValue()
            minutes = dlg.minutes_spin.GetValue()
            title = dlg.title_text.GetValue()
            message = dlg.message_text.GetValue()

            if not title or not message:
                wx.MessageBox("Notification Title or Message cannot be empty.", "Input Error", wx.OK | wx.ICON_ERROR, self)
                dlg.Destroy()
                return

            details_action = {'title': title, 'message': message}
            details_display = f"Title: {title}, Message: {message}"
            self.add_task(
                task_type="Notification", name=name,
                hours_offset=hours, minutes_offset=minutes,
                details_for_action=details_action, details_display_str=details_display
            )
        dlg.Destroy()

    def on_play_media(self, event):
        dlg = PlayMediaDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.name_text.GetValue()
            hours = dlg.hours_spin.GetValue()
            minutes = dlg.minutes_spin.GetValue()
            media_path = dlg.media_path_text.GetValue()            
            self.add_task(
                task_type="Play Media", name=name,
                hours_offset=hours, minutes_offset=minutes,
                details_for_action=media_path, details_display_str=media_path
            )
        dlg.Destroy()


    def on_close_frame(self, event):
        """Handles the frame's EVT_CLOSE event."""
        # Stop all running timers associated with this frame.
        for task_id in list(self.timers.keys()):
            timer = self.timers.pop(task_id)
            if timer.IsRunning():
                timer.Stop()
            timer.Destroy()
        event.Skip()
