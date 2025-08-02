import wx
from wx.lib.newevent import NewEvent
import app_vars
from gui.custom_controls import CustomButton
from gui.dialogs import DescriptionDialog
from .comments import CommentsDialog
from .download_dialogs import DownloadSettingsDialog, DownloadDialog
from .subtitle_manager import SubtitleManager
from .utils import run_yt_dlp_json
from .go_to_time import GoToTimeDialog
from speech import speak
import vlc
import sys
import threading
import time
import os
import subprocess
from configobj import ConfigObj
import srt
from datetime import timedelta

# Create a custom event for when VLC is ready
VlcReadyEvent, EVT_VLC_READY = NewEvent()

class CommentDownloader:
    def __init__(self, parent_window, youtube_url):
        self.parent_window = parent_window
        self.youtube_url = youtube_url

    def fetch_comments_async(self, callback):
        """
        Starts a thread to fetch comments and calls the callback when done.

        Args:
            callback (callable): A function to call on the main thread
                                 when fetching is complete. It should accept
                                 (comments_list, error_message) as arguments.
        """
        def worker_thread():
            comments = []
            error_message = None
            try:
                info_dict = run_yt_dlp_json(
                    self.youtube_url,
                    extra_args=['--write-comments', '--no-check-formats']
                    )
                if info_dict:
                    comments = info_dict.get('comments', [])
            except Exception as e:
                error_message = f"An unexpected error occurred while fetching comments: {e}"
                wx.CallAfter(wx.MessageBox, error_message, "Error", wx.OK | wx.ICON_ERROR, parent=self.parent_window)
                comments = []
            wx.CallAfter(callback, comments, error_message)

        threading.Thread(target=worker_thread, daemon=True).start()

class YoutubePlayer(wx.Frame):
    def __init__(self, parent, title, url, search_results_frame, description, original_youtube_link, results, current_index, play_as_audio):
        super().__init__(parent, title=title, size=(640, 480))
        self.search_results_frame = search_results_frame
        self.youtube_url = original_youtube_link
        self.title=title
        self.description = description
        self.results = results
        self.current_index = current_index
        self.is_fullscreen = False
        self.is_audio = play_as_audio
        self.subtitle_enabled = False
        self.current_subtitle=None
        self.playback_speed = 1.0
        self.start_time = None
        self.end_time = None
        self.start_selection_item = None
        self.end_selection_item = None
        self.save_audio_item = None
        self.save_video_item = None
        # Go up two levels to get to the main directory, then add ffmpeg.exe
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.ffmpeg_path = os.path.join(project_root, 'ffmpeg.exe')
        self.subtitle_manager = None

        self.load_settings()
        self.create_menu_bar()
        self.SetSize(wx.DisplaySize())
        self.Maximize(True)
        self.SetBackgroundColour(wx.BLACK if not self.is_audio else wx.Colour(240, 240, 240))
        self.url = url
        self.instance = None
        self.player = None
        self.loading_dialog = None

        self.subtitle_label = wx.StaticText(self, label="", style=wx.ALIGN_CENTER | wx.ST_NO_AUTORESIZE)
        self.subtitle_label.SetForegroundColour(wx.WHITE)
        self.subtitle_label.SetBackgroundColour(wx.BLACK)
        self.subtitle_label.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.subtitle_label.Hide()

        # Create custom buttons
        self.restart_button = CustomButton(self, -1, "Restart from beginning")
        self.rewind_button = CustomButton(self, -1, "Rewind")
        self.pause_button = CustomButton(self, -1, "Pause")
        self.forward_button = CustomButton(self, -1, "Forward")
        self.go_to_end_button = CustomButton(self, -1, "Go to End")

        # Bind button events
        self.restart_button.Bind(wx.EVT_BUTTON, self.onRestart)
        self.rewind_button.Bind(wx.EVT_BUTTON, self.onRewind)
        self.pause_button.Bind(wx.EVT_BUTTON, self.onPause)
        self.forward_button.Bind(wx.EVT_BUTTON, self.onForward)
        self.go_to_end_button.Bind(wx.EVT_BUTTON, self.onGoToEnd)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Insert(0, self.restart_button, 0, wx.ALL, 5)
        button_sizer.Add(self.rewind_button, 0, wx.ALL, 5)
        button_sizer.Add(self.pause_button, 0, wx.ALL, 5)
        button_sizer.Add(self.forward_button, 0, wx.ALL, 5)
        button_sizer.Add(self.go_to_end_button, 0, wx.ALL, 5)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(button_sizer, 0, wx.ALIGN_CENTER|wx.ALL, 15)
        sizer.Add(self.subtitle_label, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)
        self.Fit()
        self.Bind(wx.EVT_CHAR_HOOK, self.onKey)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Initialize VLC in a separate thread
        threading.Thread(target=self.init_vlc_thread).start()
        self.Bind(EVT_VLC_READY, self.onVlcReady)


    def load_settings(self):
        """Loads settings from the config file."""
        config_path = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name, "settings.ini")
        self.config = ConfigObj(config_path)
        youtube_settings = self.config.get('YouTube', {})
        self.fast_forward_interval = int(youtube_settings.get('fast_forward_interval', 5))
        self.rewind_interval = int(youtube_settings.get('rewind_interval', 5))
        self.post_playback_action = youtube_settings.get('post_playback_action', 'Close player')
        self.default_volume = int(youtube_settings.get('default_volume', 80))
        self.default_download_type = youtube_settings.get('default_download_type', 'Audio')
        self.default_video_quality = youtube_settings.get('default_video_quality', 'Medium')
        self.default_audio_format = youtube_settings.get('default_audio_format', 'mp3')
        self.default_audio_quality = youtube_settings.get('default_audio_quality', '128K')
        self.default_download_directory = youtube_settings.get('default_download_directory', '')

    def create_menu_bar(self):
        menubar = wx.MenuBar()
        video_menu = wx.Menu()
        download_menu = wx.Menu()
        download_video_item = download_menu.Append(wx.ID_ANY, "Download video...\tctrl+shift+d")
        self.Bind(wx.EVT_MENU, self.on_download_menu_item, download_video_item)

        direct_download_item = download_menu.Append(wx.ID_ANY, "Direct Download\tctrl+d")
        self.Bind(wx.EVT_MENU, self.on_direct_download_menu_item, direct_download_item)
        video_menu.AppendSubMenu(download_menu, "&Download")

        go_to_time_item = video_menu.Append(wx.ID_ANY, "Go to Time...\tctrl+g")
        self.Bind(wx.EVT_MENU, self.on_go_to_time, go_to_time_item)

        toggle_fullscreen_item = video_menu.Append(wx.ID_ANY, "Toggle Full Screen\tF")
        self.Bind(wx.EVT_MENU, lambda event: self.toggle_fullscreen(), toggle_fullscreen_item)

        description_item = video_menu.Append(wx.ID_ANY, "Video Description\talt+d")
        self.Bind(wx.EVT_MENU, lambda event: self.show_description(event), description_item)
        show_comments_item = video_menu.Append(wx.ID_ANY, "Show Comments\talt+c")
        self.Bind(wx.EVT_MENU, self.on_show_comments, show_comments_item)

        copy_link_item = video_menu.Append(wx.ID_ANY, "Copy Link\tctrl+c")
        self.Bind(wx.EVT_MENU, self.on_copy_youtube_link, copy_link_item)

        subtitle_menu = wx.Menu()
        self.enable_subtitle_item = subtitle_menu.Append(wx.ID_ANY, "Enable Video Subtitle", kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, self.on_toggle_subtitle, self.enable_subtitle_item)

        download_subtitle_item = subtitle_menu.Append(wx.ID_ANY, "Download Subtitle")
        self.Bind(wx.EVT_MENU, self.on_download_subtitle, download_subtitle_item)  # Placeholder binding
        video_menu.AppendSubMenu(subtitle_menu, "&Subtitle")

        selection_menu = wx.Menu()
        self.start_selection_item = selection_menu.Append(wx.ID_ANY, "Start Selection")
        self.Bind(wx.EVT_MENU, lambda evt: self.set_start_time(), self.start_selection_item)
        self.end_selection_item = selection_menu.Append(wx.ID_ANY, "End Selection")
        self.Bind(wx.EVT_MENU, lambda evt: self.set_end_time(), self.end_selection_item)
        selection_menu.AppendSeparator()
        self.save_audio_item = selection_menu.Append(wx.ID_ANY, "Save Selection as Audio\tCtrl+S")
        self.Bind(wx.EVT_MENU, self.on_save_audio_selection, self.save_audio_item)
        self.save_video_item = selection_menu.Append(wx.ID_ANY, "Save Selection as Video\tCtrl+Shift+S")
        self.Bind(wx.EVT_MENU, self.on_save_video_selection, self.save_video_item)

        menubar.Append(video_menu, "&Options")
        self.SetMenuBar(menubar)
        menubar.Append(selection_menu, "&Selection")
        self.update_save_selection_state()

    def init_vlc_thread(self):
        self.instance = vlc.Instance()
        if not self.instance:
            wx.CallAfter(wx.MessageBox, "Failed to initialize the media player.", "Player error", wx.OK | wx.ICON_ERROR)
        self.player = self.instance.media_player_new()
        media = self.instance.media_new(self.url)
        self.player.set_media(media)

        if sys.platform == "win32":
            if not self.is_audio:
                self.player.set_hwnd(self.GetHandle())
        elif sys.platform == "darwin":
            self.player.set_nsobject(self.panel.GetHandle())
        else:
            self.player.set_xwindow(self.panel.GetHandle())

        # Attach event handlers for MediaPlayerOpening and media end
        event_manager = self.player.event_manager()
        event_manager.event_attach(vlc.EventType.MediaPlayerOpening, self.on_media_opening)
        event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_media_end)
        self.player.audio_set_volume(self.default_volume)
        self.player.play()
        wx.PostEvent(self, VlcReadyEvent())  # Post the event after play()

    def on_media_opening(self, event):
        wx.PostEvent(self, VlcReadyEvent())

    def on_media_end(self, event):
        """Handles the MediaPlayerEndReached event based on settings."""
        if self.player:
            action = self.post_playback_action
            if action == "Replay video":
                wx.CallAfter(self.player.stop)
                new_media = self.instance.media_new(self.url)
                wx.CallAfter(self.player.set_media, new_media)
                wx.CallAfter(self.player.play)
                wx.CallAfter(self.pause_button.SetLabel, "Pause")
            elif action == "Close the player":
                wx.CallAfter(self.player.stop)
                wx.CallAfter(self.player.set_time, 0)
                wx.CallAfter(self.pause_button.SetLabel, "Play")
                wx.CallAfter(self.Close)
            else:
                wx.CallAfter(self.player.stop)
                wx.CallAfter(self.player.set_time, 0)
                wx.CallAfter(self.pause_button.SetLabel, "Play")
                wx.CallAfter(speak, "Video finished.")

    def onVlcReady(self, event):
        if self.loading_dialog:
            self.loading_dialog.Destroy()
        self.Show()
        self.SetFocus()

    def on_time_changed(self, event):
        """Handles the MediaPlayerTimeChanged event to display subtitles."""
        current_time_ms = self.player.get_time()
        current_time = timedelta(milliseconds=current_time_ms)

        # Check if we are already displaying a subtitle
        if hasattr(self, 'current_subtitle') and self.current_subtitle:
            if self.current_subtitle.start <= current_time <= self.current_subtitle.end:
                return
            else:
                self.current_subtitle = None

        for subtitle in self.subtitles:
            if subtitle.start <= current_time <= subtitle.end:
                wx.CallAfter(self.display_subtitle, subtitle.content)
                self.current_subtitle = subtitle
                return
        wx.CallAfter(self.hide_subtitle)

    def onRewind(self, event):
        self.player.set_time(self.player.get_time() - (self.rewind_interval * 1000))

    def onPause(self, event):
        if self.player.is_playing():
            self.player.pause()
            self.pause_button.SetLabel("Play")
            speak("Paused")
        elif self.player.get_state() in (vlc.State.Paused, vlc.State.Stopped):
             self.player.play()
             self.pause_button.SetLabel("Pause")
             speak("Play")

    def onForward(self, event):
        self.player.set_time(self.player.get_time() + (self.fast_forward_interval * 1000))

    def onKey(self, event):
        keycode = event.GetKeyCode()
        modifiers = event.GetModifiers()

        if keycode == wx.WXK_SPACE:
           self.onPause(event)
        elif keycode == wx.WXK_LEFT:
            self.onRewind(event)
        elif keycode == wx.WXK_RIGHT:
            self.onForward(event)
        elif keycode == wx.WXK_UP:
            if modifiers == wx.MOD_CONTROL:
                self.increase_speed()
            else:
                self.onVolumeUp(event)
        elif keycode == wx.WXK_DOWN:
            if modifiers == wx.MOD_CONTROL:
                self.decrease_speed()
            else:
                self.onVolumeDown(event)
        elif keycode == wx.WXK_PAGEUP:
            self.play_previous_video()
        elif keycode == wx.WXK_PAGEDOWN:
            self.play_next_video()
        elif keycode == ord('V') or keycode == ord('v'):
            self.onAnnounceVolume(event)
        elif keycode == ord('E') or keycode == ord('e'):
            self.onAnnounceElapsedTime(event)
        elif keycode == ord('R') or keycode == ord('r'):
            self.onAnnounceRemainingTime(event)
        elif keycode == ord('T') or keycode == ord('t'):
            self.onAnnounceTotalTime(event)
        elif keycode == ord('P') or keycode == ord('p'):
            self.onAnnouncePercentage(event)
        elif keycode == wx.WXK_HOME:
           self.onRestart(event)
        elif keycode == wx.WXK_END:
            self.onGoToEnd(event)
        elif keycode == ord('F') or keycode == ord('f'):
           self.toggle_fullscreen()
        elif keycode == ord('S') or keycode == ord('s'):
            if modifiers == wx.MOD_CONTROL | wx.MOD_SHIFT:
                self.on_save_video_selection(event)
            elif modifiers == wx.MOD_CONTROL:
                self.on_save_audio_selection(event)
            else:
                self.announce_speed()
        elif ord('1') <= keycode <= ord('9'):
            self.handle_percentage_jump(keycode, modifiers)
        elif keycode == ord('[') or keycode == ord('{'):
            self.set_start_time()
        elif keycode == ord(']') or keycode == ord('}'):
            self.set_end_time()
        elif keycode == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def toggle_fullscreen(self):
        if self.is_audio: return
        self.is_fullscreen = not self.is_fullscreen
        self.ShowFullScreen(self.is_fullscreen)
        if self.is_fullscreen:
            speak("full screen on")
        else:
            speak("full screen off")

    def on_toggle_subtitle(self, event):
        """Toggles the subtitle state."""
        self.subtitle_enabled = not self.subtitle_enabled

        if self.subtitle_enabled:
            # Only create subtitle_manager if it doesn't exist
            if not self.subtitle_manager:
                self.subtitle_manager = SubtitleManager(self, self.youtube_url)
            if self.subtitle_manager.subtitle_filename:
                self.start_subtitle_monitoring()
            else:
                self.subtitle_manager.download_subtitles()
                if self.subtitle_manager.subtitle_filename:
                    self.start_subtitle_monitoring()
                else:
                    speak("Error: No subtitles found")
                    self.subtitle_enabled = False
                    self.enable_subtitle_item.Check(False)
        else:
            self.stop_subtitle_monitoring()
            self.subtitle_label.Hide()

    def start_subtitle_monitoring(self):
        """Starts monitoring the video time for subtitle display."""
        speak("Video subtitles enabled.")
        self.subtitle_label.Show()
        config_dir = wx.StandardPaths.Get().GetUserConfigDir()
        subtitles_dir = os.path.join(config_dir, app_vars.app_name, "subtitles")
        subtitle_path = os.path.join(subtitles_dir, self.subtitle_manager.subtitle_filename)

        try:
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                self.subtitles = list(srt.parse(f))
        except Exception as e:
            wx.MessageBox(f"Error parsing subtitle file: {e}", "Error", wx.OK | wx.ICON_ERROR)
            self.subtitle_enabled = False
            return

        event_manager = self.player.event_manager()
        event_manager.event_attach(vlc.EventType.MediaPlayerTimeChanged, self.on_time_changed)

    def stop_subtitle_monitoring(self):
        """Stops monitoring the video time for subtitle display."""
        speak("Video subtitles disabled.")
        event_manager = self.player.event_manager()
        event_manager.event_detach(vlc.EventType.MediaPlayerTimeChanged)

    def on_download_subtitle(self, event):
        """Handles the 'Download Subtitle' menu item."""
        if not self.youtube_url:
            speak("No Youtube video loaded.")
            return

        if not self.subtitle_manager:
            self.subtitle_manager = SubtitleManager(self, self.youtube_url)
        self.subtitle_manager.download_subtitles()

    def display_subtitle(self, text):
        """Displays the given subtitle text."""
        self.subtitle_label.SetLabel(text)
        speak(text, interrupt=True)

    def hide_subtitle(self):
        """Hides the subtitle label."""
        self.subtitle_label.SetLabel("")

    def increase_speed(self):
        self.playback_speed = min(self.playback_speed + 0.1, 4.0)
        self.player.set_rate(self.playback_speed)
        speak(f"Speed {self.playback_speed:.1f}x")

    def decrease_speed(self):
        self.playback_speed = max(self.playback_speed - 0.1, 0.1)
        self.player.set_rate(self.playback_speed)
        speak(f"Speed {self.playback_speed:.1f}x")

    def announce_speed(self):
        speak(f"Current speed is {self.playback_speed:.1f}x")

    def onVolumeUp(self, event):
        if self.player is not None:
            current_volume = self.player.audio_get_volume()
            new_volume = min(current_volume + 5, 400)
            if new_volume != current_volume:
                self.player.audio_set_volume(new_volume)
                speak(f"{int(new_volume)}%")

    def onVolumeDown(self, event):
        if self.player is not None:
            current_volume = self.player.audio_get_volume()
            new_volume = max(current_volume - 5, 0)
            if new_volume != current_volume:
                self.player.audio_set_volume(new_volume)
                speak(f"{int(new_volume)}%")

    def onAnnounceVolume(self, event):
        if self.player is not None:
            current_volume = self.player.audio_get_volume()
            speak(f"The current Volume is {current_volume}%")
        else:
            speak("Current volume is unknown")

    def play_next_video(self):
        if self.player is None or self.player.get_length() is None:
            return

        if self.current_index < len(self.results) - 1:
            self.current_index += 1
            self.play_video_at_index(self.current_index)
            speak("Loading next video, Please wait...")

    def play_previous_video(self):
        if self.player is None or self.player.get_length() is None:
            return

        if self.current_index > 0:
            self.current_index -= 1
            self.play_video_at_index(self.current_index)
            speak("Loading previous video, Please wait...")

    def play_video_at_index(self, index):
        if self.player is None or self.player.get_length() is None:
            return

        selected_video = self.results[index]
        if self.player:
            self.player.stop()
            self.player.release()
            self.instance.release()
            self.player = None
        threading.Thread(target=self.get_direct_link_and_play, args=(selected_video['webpage_url'], selected_video['title'], False)).start()

    def get_direct_link_and_play(self, url, title, play_as_audio=False):
        # This function is called when navigating next/previous
        try:
            self.youtube_url = url
            self.title = title
            self.SetTitle(title)

            format_selector = None
            if self.is_audio:
                 format_selector = 'ba/b'
            else:
                if self.default_video_quality == "Low":
                    format_selector = 'worst[ext=mp4]/worstvideo[ext=mp4]/worst'
                elif self.default_video_quality == "Medium":
                    format_selector = 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'
                elif self.default_video_quality == "Best":
                    format_selector = 'best[ext=mp4]/bestvideo[ext=mp4]/best'
                else:
                    format_selector = 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'

            wx.CallAfter(speak, f"Loading {title}...")
            wx.CallAfter(wx.BeginBusyCursor)

            info_dict = run_yt_dlp_json(url, format_selector=format_selector)
            if not info_dict:
                 raise ValueError("Failed to get video info from yt-dlp.")

            media_url = info_dict.get('url')
            self.description = info_dict.get('description', '')

            if not media_url:
                formats = info_dict.get('formats', [])
                if formats:
                    media_url = formats[0].get('url')
            if not media_url:
                raise ValueError("No playable URL found in yt-dlp output for next/prev.")

            self.url = media_url
            wx.CallAfter(wx.EndBusyCursor)
            self.init_vlc_thread()
        except Exception as e:
            wx.CallAfter(wx.EndBusyCursor)
            wx.CallAfter(wx.MessageBox, f"Could not play next/previous video: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def _format_time(self, milliseconds):
        if milliseconds is None or milliseconds == 0:
            return "Unknown"

        seconds = int(milliseconds / 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"  # HH:MM:SS
        else:
            return f"00:{minutes:02d}:{seconds:02d}"

    def onAnnounceElapsedTime(self, event):
        if self.player is not None:
            elapsed = self.player.get_time()
            formatted_time = self._format_time(elapsed)
            speak(f"Elapsed Time: {formatted_time}")
        else:
            speak("Elapsed time is unknown")

    def onAnnounceRemainingTime(self, event):
        if self.player is not None:
            total_time = self.player.get_length()
            elapsed_time = self.player.get_time()
            if total_time is not None and total_time !=0 and elapsed_time is not None and elapsed_time != 0:
               remaining = total_time - elapsed_time
            else:
                remaining = None
            formatted_time = self._format_time(remaining)
            speak(f"Remaining Time: {formatted_time}")
        else:
            speak("Remaining time is unknown")

    def onAnnounceTotalTime(self, event):
        if self.player is not None:
            total = self.player.get_length()
            formatted_time = self._format_time(total)
            speak(f"Total Time: {formatted_time}")
        else:
            speak("Total time is unknown")

    def onAnnouncePercentage(self, event):
        """Announces the current playback percentage."""
        if self.player is not None:
            elapsed_time_ms = self.player.get_time()
            total_time_ms = self.player.get_length()

        # Ensure both values are valid (not None or 0 total time)
            if elapsed_time_ms is not None and total_time_ms is not None and total_time_ms > 0:
                percentage = (elapsed_time_ms / total_time_ms) * 100
                speak(f"{int(percentage)} percent")
            else:
                speak("Percentage unknown")
        else:
            speak("Percentage is unknown")

    def onRestart(self, event):
        if self.player is not None:
            self.player.set_time(0)
            speak("Restart from beginning")

    def onGoToEnd(self, event):
        if self.player is not None:
            total_time = self.player.get_length()
            if total_time != 0:
                self.player.set_time(max(0, total_time - 10000))
            speak("Near end")

    def handle_percentage_jump(self, keycode, modifiers):
        percentage = (keycode - ord('0')) * 10
        if modifiers == wx.MOD_SHIFT:
            percentage += 5

        total_time = self.player.get_length()
        if total_time > 0:
            target_time = int(total_time * (percentage / 100.0))
            self.player.set_time(target_time)
            speak(f"{percentage} percent")

    def set_start_time(self):
        """Sets the start time of the selection."""
        self.start_time = self.player.get_time()
        speak(f"Start selection: {self._format_time(self.start_time)}")
        self.update_save_selection_state()

    def set_end_time(self):
        """Sets the end time of the selection."""
        self.end_time = self.player.get_time()
        speak(f"End selection: {self._format_time(self.end_time)}")
        self.update_save_selection_state()

    def on_save_audio_selection(self, event):
        """Downloads the selected portion of the video as an MP3 file."""
        if self.start_time is None or self.end_time is None:
            speak("Selection not set.")
            return

        if self.start_time >= self.end_time:
            speak("Invalid selection. Start time must be before end time.")
            return

        with wx.FileDialog(self, "Save selection as", wildcard="MP3 files (*.mp3)|*.mp3",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            output_path = fileDialog.GetPath()
            if not output_path.lower().endswith(".mp3"):
                output_path += ".mp3"
            self.loading_dialog = wx.ProgressDialog("Downloading Selection", "Please wait...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
            threading.Thread(target=self.download_and_extract_audio,
                             args=(self.url, output_path, self.start_time, self.end_time)).start()

    def on_save_video_selection(self, event):
        """Downloads the selected portion of the video as an MP4 file."""
        if self.is_audio: return
        if self.start_time is None or self.end_time is None:
            speak("Selection not set.")
            return

        if self.start_time >= self.end_time:
            speak("Invalid selection. Start time must be before end time.")
            return

        with wx.FileDialog(self, "Save selection as", wildcard="MP4 files (*.mp4)|*.mp4",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            output_path = fileDialog.GetPath()
            if not output_path.lower().endswith(".mp4"):
                output_path += ".mp4"
            
            self.loading_dialog = wx.ProgressDialog("Saving Video Selection", "Please wait...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
            threading.Thread(target=self.download_and_extract_video,
                             args=(self.url, output_path, self.start_time, self.end_time)).start()

    def download_and_extract_video(self, url, output_path, start_time, end_time):
        """Uses ffmpeg to save a video clip from a stream URL."""
        try:
            start_time_str = time.strftime('%H:%M:%S', time.gmtime(start_time / 1000))
            duration_seconds = (end_time - start_time) / 1000

            cmd = [
                self.ffmpeg_path,
                "-y",
                "-ss", start_time_str,
                "-i", url,
                "-t", str(duration_seconds),
                "-c:v", "copy",
                "-c:a", "copy",
                output_path
            ]

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo)
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                # Fallback to re-encoding if stream copy failed
                speak("Stream copy failed, attempting to re-encode. This will be slower.")
                wx.CallAfter(self.loading_dialog.Update, 50, "Re-encoding...")

                cmd_reencode = [
                    self.ffmpeg_path,
                    "-y",
                    "-ss", start_time_str,
                    "-i", url,
                    "-t", str(duration_seconds),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "22",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    output_path
                ]
                process_reencode = subprocess.Popen(cmd_reencode, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo)
                stdout, stderr = process_reencode.communicate()
                
                if process_reencode.returncode != 0:
                    raise subprocess.CalledProcessError(process_reencode.returncode, cmd_reencode, output=stdout, stderr=stderr)

            wx.CallAfter(speak, "Video selection saved successfully.")
        except subprocess.CalledProcessError as e:
            error_details = f"FFMPEG Error:\n{e.stderr}"
            wx.CallAfter(wx.MessageBox, error_details, "Error Saving Video", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(speak, "Error saving video selection.")
        except (FileNotFoundError, PermissionError) as e:
            wx.CallAfter(speak, str(e))
        except Exception as e:
            wx.CallAfter(speak, f"An unexpected error occurred: {e}")
        finally:
            if self.loading_dialog:
                wx.CallAfter(self.loading_dialog.Destroy)

    def download_and_extract_audio(self, url, output_path, start_time, end_time):
        try:
            start_time_str = time.strftime('%H:%M:%S', time.gmtime(start_time / 1000))
            duration_seconds = (end_time - start_time) / 1000

            cmd = [
                self.ffmpeg_path,
                "-y",
                "-ss", start_time_str,
                "-i", url,
                "-t", str(duration_seconds),
                "-q:a", "0",
                "-map", "a",
                output_path
            ]

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo)
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout, stderr=stderr)
            wx.CallAfter(speak, "Selection saved successfully.")
        except subprocess.CalledProcessError as e:
            error_details = f"FFMPEG Error:\n{e.stderr}"
            wx.CallAfter(wx.MessageBox, error_details, "Error Saving Audio", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(speak, "Error saving audio selection.")
        except (FileNotFoundError, PermissionError) as e:
            wx.CallAfter(speak, str(e))
        except Exception as e:
            wx.CallAfter(speak, f"An unexpected error occurred: {e}")
        finally:
            if self.loading_dialog:
                wx.CallAfter(self.loading_dialog.Destroy)

    def process_is_alive(self, process):
        """Checks if the given subprocess is still running."""
        if process is None:
            return False
        return process.poll() is None

    def update_save_selection_state(self):
        """Enables or disables the 'Save Selection' menu items based on selection and player mode."""
        is_selection_valid = self.start_time is not None and self.end_time is not None and self.start_time < self.end_time

        # 'Save Audio' is enabled if the selection is valid, regardless of player mode.
        if self.save_audio_item:
            self.save_audio_item.Enable(is_selection_valid)

        # 'Save Video' is only enabled if the selection is valid AND the player is in video mode.
        is_video_mode = not self.is_audio
        if self.save_video_item:
            self.save_video_item.Enable(is_selection_valid and is_video_mode)

    def on_go_to_time(self, event):
        if not self.player:
            wx.MessageBox("Player is not initialized.", "Error", wx.OK | wx.ICON_ERROR, self)
            return

        total_duration_ms = self.player.get_length()
        current_elapsed_ms = self.player.get_time()

        if total_duration_ms <= 0:
            wx.MessageBox("Video duration is not available or video not fully loaded.",
                          "Cannot Go to Time", wx.OK | wx.ICON_INFORMATION, self)
            return

        dlg = GoToTimeDialog(self, total_duration_ms, current_elapsed_ms)
        if dlg.ShowModal() == wx.ID_OK:
            target_ms = dlg.get_selected_time_milliseconds()
            if self.player:
                self.player.set_time(target_ms)
                speak(f"Jumped to {self._format_time(target_ms)}")
        dlg.Destroy()

    def show_description(self, event):
        if hasattr(self, 'description') and self.description:
             desc_dlg = DescriptionDialog(self, "Video description", self.description)
             desc_dlg.ShowModal()
             desc_dlg.Destroy()
        else:
            wx.MessageBox("Description is not available for this video.", "Description Unavailable", wx.OK | wx.ICON_INFORMATION)

    def on_show_comments(self, event):
        if not self.youtube_url:
            speak("No Youtube video loaded.")
            return

        self.loading_dialog = wx.ProgressDialog(
            "Loading Comments",
            "Fetching comments from YouTube...",
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
            )
        self.loading_dialog.Show()
        wx.Yield()
        self.comment_downloader = CommentDownloader(self, self.youtube_url)
        self.comment_downloader.fetch_comments_async(self.on_comments_fetched)

    def on_comments_fetched(self, comments_list, error_message):
        if self.loading_dialog:
             try:
                 self.loading_dialog.Destroy()
             except Exception:
                 pass
             self.loading_dialog = None

        if comments_list:
            dlg = CommentsDialog(self, comments_list)
            dlg.ShowModal()
            dlg.Destroy()
        else:
            wx.MessageBox("No comments found for this video.", "Comments", wx.OK | wx.ICON_INFORMATION)

    def on_copy_youtube_link(self, event):
        """Copies the original YouTube URL to the clipboard."""
        if not self.youtube_url:
            wx.MessageBox("No youtube URL to copy", "Error", wx.OK | wx.ICON_INFORMATION)
            return

        clipboard = wx.Clipboard.Get()
        if clipboard.Open():
            text_data = wx.TextDataObject()
            text_data.SetText(self.youtube_url)
            clipboard.SetData(text_data)
            clipboard.Close()
            clipboard.Flush()
            speak("Link copyed to clipboard", interrupt=True)
        else:
            wx.MessageBox("Could not access clipboard.", "Error", wx.OK | wx.ICON_ERROR)

    def on_download_menu_item(self, event):
         if not self.youtube_url:
             wx.MessageBox("No YouTube video loaded.", "Error", wx.OK | wx.ICON_INFORMATION)
             return

         settings_dialog = DownloadSettingsDialog(self, "Download Settings", self.title, self.youtube_url)
         if settings_dialog.ShowModal() == wx.ID_OK:
             download_settings = settings_dialog.settings
             self.start_download_process(download_settings)
         settings_dialog.Destroy()

    def on_direct_download_menu_item(self, event):
        """Handles the 'Direct Download' menu item."""
        if not self.youtube_url:
            wx.MessageBox("No YouTube video loaded.", "Error", wx.OK | wx.ICON_INFORMATION)
            return

        if not self.default_download_directory or not os.path.isdir(self.default_download_directory):
            wx.MessageBox("Default download directory is not set or invalid. Please configure it in Settings.", "Direct Download Failed", wx.OK | wx.ICON_WARNING)
            return

        download_settings = {
            'url': self.youtube_url,
            'filename': self.title,
            'directory': self.default_download_directory,
            'type': self.default_download_type,
            'video_quality': self.default_video_quality,
            'audio_format': self.default_audio_format,
            'audio_quality': self.default_audio_quality,
        }
        self.start_download_process(download_settings)

    def start_download_process(self, download_settings):
        """Starts the DownloadDialog with the collected settings."""
        dlg_title = f"Downloading: {download_settings['filename']}"
        download_dlg = DownloadDialog(self, dlg_title, download_settings)
        download_dlg.download_task()


    def OnClose(self, event):
        if self.player:
            self.player.stop()
            self.player.release()
            self.instance.release()
            self.player = None
        if self.loading_dialog: #Close the dialog if it still exists.
            self.loading_dialog.Destroy()
            self.loading_dialog=None

        frame_to_show_after_player = self.search_results_frame
        self.Destroy()
        if frame_to_show_after_player:
            try:
                # Check if the frame to show still exists, as it might have been closed
                if isinstance(frame_to_show_after_player, wx.Window) and frame_to_show_after_player.IsBeingDeleted() == False:
                    frame_to_show_after_player.Show()
                    frame_to_show_after_player.Raise()
            except (wx.wxAssertionError, RuntimeError):
                pass
