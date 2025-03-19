import wx
from wx.lib.newevent import NewEvent
import yt_dlp
from youtube_comment_downloader.downloader import YoutubeCommentDownloader, SORT_BY_POPULAR
import app_vars
from gui.custom_controls import CustomButton
from tools.network_player.comments import CommentsDialog
from tools.network_player.download_dialog import DownloadDialog
from tools.network_player.subtitle_manager import SubtitleManager
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

class YoutubePlayer(wx.Frame):
    def __init__(self, parent, title, url, search_results_frame, description, original_youtube_link, results, current_index):
        super().__init__(parent, title=title, size=(640, 480))
        self.search_results_frame = search_results_frame
        self.youtube_url = original_youtube_link
        self.title=title
        self.description = description
        self.results = results
        self.current_index = current_index
        self.is_fullscreen = False
        self.is_audio = url.endswith("m4a")
        self.subtitle_enabled = False
        self.current_subtitle=None
        self.playback_speed = 1.0
        self.start_time = None
        self.end_time = None
        self.save_selection_item = None
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
        self.default_volume = int(youtube_settings.get('default_volume', 80))

    def create_menu_bar(self):
        menubar = wx.MenuBar()
        video_menu = wx.Menu()
        download_menu = wx.Menu()
        download_video_item = download_menu.Append(wx.ID_ANY, "Video")
        download_audio_item = download_menu.Append(wx.ID_ANY, "Audio")
        self.save_selection_item = download_menu.Append(wx.ID_ANY, "Save Selection\tctrl+s")
        self.Bind(wx.EVT_MENU, self.save_selection, self.save_selection_item)
        self.save_selection_item.Enable(False)  # Initially disabled
        self.Bind(wx.EVT_MENU, lambda event: self.on_download_from_menu(event, is_audio=False), download_video_item)
        self.Bind(wx.EVT_MENU, lambda event: self.on_download_from_menu(event, is_audio=True), download_audio_item)
        video_menu.AppendSubMenu(download_menu, "&Download")

        description_item = video_menu.Append(wx.ID_ANY, "Video Description\talt+d")
        self.Bind(wx.EVT_MENU, lambda event: self.show_description(event), description_item)
        show_comments_item = video_menu.Append(wx.ID_ANY, "Show Comments")
        self.Bind(wx.EVT_MENU, self.on_show_comments, show_comments_item)

        copy_link_item = video_menu.Append(wx.ID_ANY, "Copy Link\tctrl+c")
        self.Bind(wx.EVT_MENU, self.on_copy_youtube_link, copy_link_item)

        subtitle_menu = wx.Menu()
        self.enable_subtitle_item = subtitle_menu.Append(wx.ID_ANY, "Enable Video Subtitle", kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, self.on_toggle_subtitle, self.enable_subtitle_item)

        download_subtitle_item = subtitle_menu.Append(wx.ID_ANY, "Download Subtitle")
        self.Bind(wx.EVT_MENU, self.on_download_subtitle, download_subtitle_item)  # Placeholder binding
        video_menu.AppendSubMenu(subtitle_menu, "&Subtitle")

        menubar.Append(video_menu, "&Options")
        self.SetMenuBar(menubar)

    def init_vlc_thread(self):
        self.instance = vlc.Instance()
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

        # Attach event handler for MediaPlayerOpening
        event_manager = self.player.event_manager()
        event_manager.event_attach(vlc.EventType.MediaPlayerOpening, self.on_media_opening)
        self.player.audio_set_volume(self.default_volume)
        self.player.play()
        wx.PostEvent(self, VlcReadyEvent())  # Post the event after play()

    def on_media_opening(self, event):
        wx.PostEvent(self, VlcReadyEvent())

    def onVlcReady(self, event):
        if self.loading_dialog:
            self.loading_dialog.Destroy()
        self.Show()
        self.SetFocus() #Give focus to the main frame

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
        else:
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
        elif keycode == wx.WXK_HOME:
           self.onRestart(event)
        elif keycode == wx.WXK_END:
            self.onGoToEnd(event)
        elif keycode == ord('F') or keycode == ord('f'):
           self.toggle_fullscreen()
        elif keycode == ord('S') or keycode == ord('s'):
            if modifiers==wx.MOD_CONTROL:
                self.save_selection(event)
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
        current_volume = self.player.audio_get_volume()
        new_volume = min(current_volume + 5, 400)
        if new_volume != current_volume:
            self.player.audio_set_volume(new_volume)
            speak(f"{int(new_volume)}%")

    def onVolumeDown(self, event):
        current_volume = self.player.audio_get_volume()
        new_volume = max(current_volume - 5, 0)
        if new_volume != current_volume:
            self.player.audio_set_volume(new_volume)
            speak(f"{int(new_volume)}%")

    def onAnnounceVolume(self, event):
        current_volume = self.player.audio_get_volume()
        speak(f"The current Volume is {current_volume}%")

    def play_next_video(self):
        if self.current_index < len(self.results) - 1:
            self.current_index += 1
            self.play_video_at_index(self.current_index)
            speak("Loading next video, Please wait...")

    def play_previous_video(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.play_video_at_index(self.current_index)
            speak("Loading previous video, Please wait...")

    def play_video_at_index(self, index):
        selected_video = self.results[index]
        if self.player:
            self.player.stop()
            self.player.release()
            self.instance.release()
            self.player = None
        threading.Thread(target=self.get_direct_link_and_play, args=(selected_video['link'], selected_video['title'], False)).start()

    def get_direct_link_and_play(self, url, title, play_as_audio):
        #This function was copyed from the youtube_search.py file, Because it is doing exactly what we need
        try:
            self.youtube_url = url
            self.title = title
            ydl_opts = {
                'format': 'bestaudio/best' if play_as_audio else 'best[ext=mp4]/best',
                'quiet': True,
                'noplaylist': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                media_url = info_dict.get('url', None)
                self.description = info_dict['description']
                if not media_url:
                    raise ValueError("No playable video URL found.")

                self.url = media_url
                self.is_audio = url.endswith("m4a")
                self.init_vlc_thread()
                self.SetTitle(title)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Could not play video: {e}", "Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Show)

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
        elapsed = self.player.get_time()
        formatted_time = self._format_time(elapsed)
        speak(f"Elapsed Time: {formatted_time}")

    def onAnnounceRemainingTime(self, event):
        total_time = self.player.get_length()
        elapsed_time = self.player.get_time()
        if total_time is not None and total_time !=0 and elapsed_time is not None and elapsed_time != 0:
           remaining = total_time - elapsed_time
        else:
            remaining = None
        formatted_time = self._format_time(remaining)
        speak(f"Remaining Time: {formatted_time}")

    def onAnnounceTotalTime(self, event):
        total = self.player.get_length()
        formatted_time = self._format_time(total)
        speak(f"Total Time: {formatted_time}")

    def onRestart(self, event):
        self.player.set_time(0)
        speak("Restart from beginning")

    def onGoToEnd(self, event):
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

    def save_selection(self, event):
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
            if not output_path.endswith(".mp3"):
                output_path += ".mp3"
            self.loading_dialog = wx.ProgressDialog("Downloading Selection", "Please wait...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
            threading.Thread(target=self.download_and_extract_audio,
                             args=(self.url, output_path, self.start_time, self.end_time)).start()

    def download_and_extract_audio(self, url, output_path, start_time, end_time):
        try:
            start_time_str = time.strftime('%H:%M:%S', time.gmtime(start_time / 1000))
            end_time_str = time.strftime('%H:%M:%S', time.gmtime(end_time / 1000))

            # Construct the ffmpeg command
            cmd = [
                self.ffmpeg_path,
                "-y",  # Overwrite output file without asking
                "-ss", start_time_str,
                "-to", end_time_str,
                "-i", url,
                "-q:a", "0",
                "-map", "a",
                output_path
            ]

            # Execute the ffmpeg command
            # result = subprocess.run(cmd, capture_output=True, check=False)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout, stderr=stderr)
            wx.CallAfter(speak, "Selection saved successfully.")
        except subprocess.CalledProcessError as e:
            wx.CallAfter(speak, f"Error saving selection: {e}")
        except (FileNotFoundError, PermissionError) as e:
            wx.CallAfter(speak, str(e))
        except Exception as e:
            wx.CallAfter(speak, f"An unexpected error occurred: {e}")
        finally:
            wx.CallAfter(self.loading_dialog.Destroy)

    def process_is_alive(self, process):
        """Checks if the given subprocess is still running."""
        if process is None:
            return False
        return process.poll() is None

    def update_save_selection_state(self):
        """Enables or disables the 'Save Selection' menu item based on selection."""
        if self.save_selection_item:
            if self.start_time is not None and self.end_time is not None:
                self.save_selection_item.Enable(True)
            else:
                self.save_selection_item.Enable(False)

    def show_description(self, event):
        dlg = wx.Dialog(self, title="Video Description", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        dlg.SetSize(800, 600)
        dlg.SetMinSize((800, 600))
        panel = wx.Panel(dlg)

        text_area = wx.TextCtrl(panel, -1, self.description, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        ok_button = wx.Button(panel, wx.ID_OK, "Close")

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(text_area, 1, wx.ALL | wx.EXPAND, 10)
        sizer.Add(ok_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        panel.SetSizer(sizer)
        dlg.Fit()
        dlg.ShowModal()
        dlg.Destroy()

    def on_show_comments(self, event):
        downloader = YoutubeCommentDownloader()
        loading_dlg = wx.ProgressDialog("Loading Comments", "Please wait...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)

        def download_comments():
            try:
                comments_generator = downloader.get_comments_from_url(self.youtube_url, sort_by=SORT_BY_POPULAR)
                comments = list(comments_generator)  # Convert generator to a list (this takes time)
                wx.CallAfter(loading_dlg.Update, 100, "Comments Loaded")
                wx.CallAfter(show_comments_dialog, comments)
            except Exception as e:
                wx.CallAfter(loading_dlg.Update, 100, f"Error: {e}")
                wx.CallAfter(wx.MessageBox, f"Error downloading comments: {e}", "Error", wx.OK | wx.ICON_ERROR)
            finally:
                wx.CallAfter(loading_dlg.Destroy)

        def show_comments_dialog(comments):
            dlg = CommentsDialog(self, comments)
            dlg.ShowModal()
            dlg.Destroy()
        threading.Thread(target=download_comments).start()

    def on_copy_youtube_link(self, event):
        """Copies the original YouTube URL to the clipboard."""
        if not self.youtube_url:
            wx.MessageBox("No youtube URL to copy", "Error", wx.OK | wx.ICON_INFORMATION)
            return

        clipboard = wx.Clipboard.Get()
        if clipboard.Open():
            text_data = wx.TextDataObject()
            text_data.SetText(self.youtube_url)

            # Check if SetDataObject is available, if not use SetData
            if hasattr(clipboard, 'SetDataObject'):
                clipboard.SetDataObject(text_data)
            else:
                clipboard.SetData(text_data)
            clipboard.Close()
            speak("Link copyed to clipboard", interrupt=True)
        else:
            wx.MessageBox("Could not access clipboard.", "Error", wx.OK | wx.ICON_ERROR)

    def on_download_from_menu(self, event, is_audio):
        self.download(self.youtube_url, self.title, is_audio)

    def download(self, url, title, is_audio):
        try:
            with wx.DirDialog(self, "Choose download directory", style=wx.DD_DEFAULT_STYLE) as dialog:
                if dialog.ShowModal() == wx.ID_OK:
                    download_path = dialog.GetPath()
                    download_dlg = DownloadDialog(self, f"Downloading {'Audio' if is_audio else 'Video'}: {title}", is_audio)
                    download_dlg.download_task(url, title, download_path)
                else:
                    return
        except Exception as e:
            wx.MessageBox(f"Could not start download: {e}", "Error", wx.OK | wx.ICON_ERROR)


    def OnClose(self, event):
        if self.player:
            self.player.stop()
            self.player.release()
            self.instance.release()
            self.player = None
        if self.loading_dialog: #Close the dialog if it still exists.
            self.loading_dialog.Destroy()
        self.Destroy()
        if self.search_results_frame:
            self.search_results_frame.Show()