import wx
import vlc
import time
import threading
import os
import datetime

VLC_READY_EVENT_TYPE = wx.NewEventType()
EVT_VLC_READY = wx.PyEventBinder(VLC_READY_EVENT_TYPE, 1)

class VlcReadyEvent(wx.PyCommandEvent):
    def __init__(self, etype, eid, value=None):
        super().__init__(etype, eid)
        self._value = value
    def GetValue(self):
        return self._value

class AlarmNotificationFrame(wx.Frame):
    def __init__(self, parent, alarm_settings_dict, task_scheduler_ref, task_id_original_alarm):
        if not isinstance(alarm_settings_dict, dict):
            alarm_settings_dict = {"alarm_name": "Error - Invalid Settings",
                                   "snooze_total_times": 0,
                                   "snooze_interval_minutes": 5,
                                   "sound_path": "",
                                   "original_year": datetime.datetime.now().year, # Add minimal structure
                                   "original_month": datetime.datetime.now().month,
                                   "original_day": datetime.datetime.now().day,
                                   "original_hour": 0, "original_minute": 0, "original_second": 0,
                                   "current_run_year": datetime.datetime.now().year,
                                   "current_run_month": datetime.datetime.now().month,
                                   "current_run_day": datetime.datetime.now().day,
                                   "current_run_hour": 0, "current_run_minute": 0, "current_run_second": 0,
                                  }
        super().__init__(parent, title=f"Alarm: {alarm_settings_dict.get('alarm_name', 'Notification')}",
                         size=(350, 170),
                         style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX) | wx.STAY_ON_TOP)
        
        self.alarm_settings = alarm_settings_dict
        self.task_scheduler = task_scheduler_ref
        self.task_id_original = task_id_original_alarm

        self.snooze_remaining = self.alarm_settings.get("snooze_total_times", 0)
        self.snooze_interval_min = self.alarm_settings.get("snooze_interval_minutes", 5)
        self.sound_path = self.alarm_settings.get("sound_path", "")

        self.vlc_instance = None
        self.media_player = None
        self.sound_duration_timer = None
        self.is_playing = False
        self.max_play_seconds = 120

        self.panel = wx.Panel(self)
        self._setup_ui()
        self.CentreOnScreen()
        self.Hide() 
        self.Bind(EVT_VLC_READY, self.on_vlc_ready)
        self.Bind(wx.EVT_CLOSE, self.on_close_alarm_frame)

        if not self.sound_path or not os.path.exists(self.sound_path):
            wx.MessageBox(f"Alarm sound file not found: '{self.sound_path}'. Alarm cannot play sound.",
                          "Sound File Error", wx.OK | wx.ICON_ERROR, self)
            wx.CallAfter(self.on_vlc_ready, VlcReadyEvent(VLC_READY_EVENT_TYPE, self.GetId(), value="SOUND_NOT_FOUND"))
        else:
            threading.Thread(target=self._init_vlc_and_play, daemon=True).start()

    def _setup_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        name_for_label = self.alarm_settings.get('alarm_name', 'Alarm Triggered!')
        self.info_label = wx.StaticText(self.panel, label=name_for_label)
        font = self.info_label.GetFont()
        font.PointSize += 3
        self.info_label.SetFont(font.Bold())
        
        self.time_label = wx.StaticText(self.panel, label=datetime.datetime.now().strftime("%I:%M:%S %p"))
        sizer.Add(self.info_label, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        sizer.Add(self.time_label, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.stop_btn = wx.Button(self.panel, label="Stop Alarm")
        self.snooze_btn = wx.Button(self.panel, label=f"Snooze ({self.snooze_interval_min} min)")

        self.stop_btn.Bind(wx.EVT_BUTTON, self.on_stop_alarm) # Reverted to original name
        self.snooze_btn.Bind(wx.EVT_BUTTON, self.on_snooze_alarm) # Reverted to original name
        btn_sizer.Add(self.stop_btn, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        btn_sizer.Add(self.snooze_btn, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        self.snooze_btn.Enable(self.snooze_remaining > 0)
        self.panel.SetSizer(sizer)
        self.Layout()

    def _init_vlc_and_play(self):
        """Initializes VLC and starts playing in a separate thread."""
        try:
            self.vlc_instance = vlc.Instance("--no-xlib --quiet --input-repeat=-1")
            self.media_player = self.vlc_instance.media_player_new()
            
            if not self.sound_path or not os.path.exists(self.sound_path):
                wx.PostEvent(self, VlcReadyEvent(VLC_READY_EVENT_TYPE, self.GetId(), value="ERROR_NO_SOUND_FILE_IN_THREAD"))
                return

            media = self.vlc_instance.media_new(self.sound_path)
            self.media_player.set_media(media)
            self.media_player.play()
            self.is_playing = True
            wx.PostEvent(self, VlcReadyEvent(VLC_READY_EVENT_TYPE, self.GetId(), value="SUCCESS"))
        except Exception as e:
            wx.MessageBox(f"Error initializing VLC or playing sound:\n{e}", "VLC Playback Error", wx.OK | wx.ICON_ERROR, self)
            wx.PostEvent(self, VlcReadyEvent(VLC_READY_EVENT_TYPE, self.GetId(), value=f"ERROR_VLC_PLAY: {e}"))

    def on_vlc_ready(self, event):
        """Called when VLC is initialized. Show frame and start timer."""
        status = event.GetValue()
        if status == "SUCCESS" or status == "SOUND_NOT_FOUND": # Show frame even if sound is missing
            self.Show()
            self.Raise()
            self.Iconize(False)
            self.SetFocus()
            self.sound_duration_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.on_sound_timeout, self.sound_duration_timer)
            self.sound_duration_timer.StartOnce(self.max_play_seconds * 1000)
        else:
            # Error occurred during VLC init, frame should close.
            self.Close(True)

    def on_sound_timeout(self, event):
        """Called if sound plays/frame is open for 2 minutes without interaction."""
        if self.snooze_remaining > 0:
            self._perform_snooze_action()
        else:
            self._perform_stop_action(from_timeout=True)

    def _cleanup_vlc(self):
        if self.sound_duration_timer and self.sound_duration_timer.IsRunning():
            self.sound_duration_timer.Stop()
        if self.media_player:
            if self.media_player.is_playing():
                self.media_player.stop()
            self.media_player.release()
            self.media_player = None
        if self.vlc_instance:
            self.vlc_instance.release()
            self.vlc_instance = None
        self.is_playing = False

    def on_stop_alarm(self, event=None):
        """Handles Stop button click or timed stop."""
        self._perform_stop_action()

    def _perform_stop_action(self, from_timeout=False):
        """Stops alarm sound and closes frame."""
        self._cleanup_vlc()
        self.Close(True)

    def on_snooze_alarm(self, event=None):
        """Handles Snooze button click or timed snooze."""
        self._perform_snooze_action()

    def _perform_snooze_action(self):
        """Calculates next snooze time, schedules new task, and closes current frame."""
        if self.snooze_remaining <= 0:
            self._perform_stop_action()
            return

        self._cleanup_vlc()        
        snooze_alarm_name_base = self.alarm_settings.get('alarm_name', 'Alarm')
        # Remove previous "(Snooze X)" part if present
        if "(Snooze" in snooze_alarm_name_base:
            snooze_alarm_name_base = snooze_alarm_name_base.split("(Snooze")[0].strip()

        snooze_instance_number = self.alarm_settings.get('snooze_total_times', 0) - self.snooze_remaining + 1
        snooze_name = f"{snooze_alarm_name_base} (Snooze {snooze_instance_number})"        
        snooze_run_time = datetime.datetime.now() + datetime.timedelta(minutes=self.snooze_interval_min)

        snooze_task_details = {
            "alarm_name": snooze_name,
            "original_hour": self.alarm_settings.get("original_hour"),
            "original_minute": self.alarm_settings.get("original_minute"),
            "original_second": self.alarm_settings.get("original_second"),
            "original_day": self.alarm_settings.get("original_day"),
            "original_month": self.alarm_settings.get("original_month"),
            "original_year": self.alarm_settings.get("original_year"),
            "schedule_type": "Once", # Snoozes are always "Once"
            "schedule_details": None,
            "sound_path": self.sound_path,
            "is_custom_sound": self.alarm_settings.get("is_custom_sound", False),
            "snooze_total_times": self.snooze_remaining - 1, # Decrement remaining snoozes
            "snooze_interval_minutes": self.snooze_interval_min,
            "current_run_year": snooze_run_time.year,
            "current_run_month": snooze_run_time.month,
            "current_run_day": snooze_run_time.day,
            "current_run_hour": snooze_run_time.hour,
            "current_run_minute": snooze_run_time.minute,
            "current_run_second": snooze_run_time.second,
        }        
        display_str = f"{snooze_name} at {snooze_run_time.strftime('%I:%M:%S %p')}"

        if self.task_scheduler:
            # Call back to the TaskScheduler to add this new "Once" snooze task
            self.task_scheduler.add_task(
                task_type="Alarm",
                name=snooze_name,
                absolute_run_time=snooze_run_time,
                details_for_action=snooze_task_details,
                details_display_str=display_str
            )
        self.Close(True)

    def on_close_alarm_frame(self, event):
        """Ensures VLC is cleaned up when frame is closed."""
        self._cleanup_vlc()
        event.Skip()
