import wx
import vlc
import requests
import concurrent.futures
import os
import re


class SimplePlayer(wx.Dialog):
    """
    A simple dialog using python-vlc to play and optionally save an audio stream URL.
    Handles button events, Escape key, and auto-closes on playback end/error.
    """
    def __init__(self, parent, audio_url: str, title="Audio Preview"):
        """
        Initializes the player dialog.
        Args:
            parent: The parent window.
            audio_url: The URL of the audio stream to play.
            title: The title for the dialog window.
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.CLOSE_BOX)

        self.audio_url = audio_url
        self.dialog_title = title
        self._vlc_instance = None
        self._media_player = None
        self._event_manager = None
        self._playback_started = False
        self._is_closing = False
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.download_progress_dialog = None

        self._init_ui()
        self._init_vlc()
        self.Bind(wx.EVT_CHAR_HOOK, self.on_escape)
        self.Bind(wx.EVT_CLOSE, self.on_dialog_close_event)

        # Attempt to play shortly after dialog is shown
        wx.CallLater(150, self.start_playback) # Slightly longer delay
        self.CentreOnParent()


    def _init_ui(self):
        """Initialize UI elements and bind button events."""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.play_button = wx.Button(panel, label="&Play")
        self.save_button = wx.Button(panel, label="&Save Preview...")
        self.close_button = wx.Button(panel, label="&Close")

        self.play_button.Bind(wx.EVT_BUTTON, self.on_play_button)
        self.save_button.Bind(wx.EVT_BUTTON, self.on_save_preview)
        self.close_button.Bind(wx.EVT_BUTTON, lambda e: self.cleanup_and_close())

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer(1)
        button_sizer.Add(self.play_button, 0, wx.ALL, 5)
        button_sizer.Add(self.save_button, 0, wx.ALL, 5)
        button_sizer.Add(self.close_button, 0, wx.ALL, 5)
        button_sizer.AddStretchSpacer(1)

        sizer.AddStretchSpacer(1)
        sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)
        sizer.AddStretchSpacer(1)

        panel.SetSizer(sizer)
        self.SetMinSize((450, 220))

    def _init_vlc(self):
        """Initialize VLC instance, player, and events."""
        try:
            self._vlc_instance = vlc.Instance("--no-video --quiet")
            self._media_player = self._vlc_instance.media_player_new()
            self._event_manager = self._media_player.event_manager()
            self._media_player.audio_set_volume(100)

            # Attach events
            self._event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.handle_vlc_playing)
            self._event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.handle_vlc_end_reached)
            self._event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.handle_vlc_error)
            self._event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self.handle_vlc_stopped)

        except Exception as e:
            wx.MessageBox(f"Failed to initialize Audio player.\nPlease ensure VLC is installed.\n\nError: {e}",
                          "Player Error", wx.OK | wx.ICON_ERROR, parent=self)
            wx.CallAfter(self.cleanup_and_close)

    def on_escape(self, event):
        """Handles the Escape key press."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.cleanup_and_close()
        else:
            event.Skip()

    def start_playback(self):
        """Loads the MRL and starts playback."""
        if self._is_closing or not self._media_player or not self.audio_url:
            return
        try:
            media = self._vlc_instance.media_new(self.audio_url)
            media.add_option('network-caching=1000')
            self._media_player.set_media(media)
            media.release()

            play_result = self._media_player.play()
            if play_result == -1:
                # Need wx.CallAfter because this might be called from CallLater
                wx.CallAfter(wx.MessageBox, "Failed to start audio playback.", "Playback Error", wx.OK | wx.ICON_ERROR, self)
                wx.CallAfter(self.cleanup_and_close)
            else:
                self.play_button.SetLabel("&Pause")
                self._playback_started = True

        except Exception as e:
            wx.MessageBox(f"Failed to load or play audio URL.\n\nError: {e}", "Playback Error", wx.OK | wx.ICON_ERROR, parent=self)
            wx.CallAfter(self.cleanup_and_close)

    def toggle_play_pause(self, event=None):
        """Toggles playback state."""
        if self._is_closing or not self._media_player: return

        try:
            if self._media_player.is_playing():
                self._media_player.pause()
                self.play_button.SetLabel("&Play")
            elif self._playback_started:
                 state = self._media_player.get_state()
                 if state in [vlc.State.Paused, vlc.State.Stopped, vlc.State.Ended]:
                     self._media_player.play()
                     self.play_button.SetLabel("&Pause")
                 # else: Currently playing, opening, buffering, or error - do nothing
            else:
                 # If never started, try starting
                 self.start_playback()
        except Exception as e:
            pass

    def on_play_button(self, event):
        """Handles the Play/Pause button click."""
        self.toggle_play_pause()

    def on_save_preview(self, event):
        """Handles the Save Preview button click."""
        if not self.audio_url:
            wx.MessageBox("No audio URL available to save.", "Error", wx.OK | wx.ICON_WARNING, self)
            return

        # Sanitize title for default filename
        default_filename = re.sub(r'[\\/*?:"<>|]', "", self.dialog_title)
        default_filename = default_filename.strip() + ".mp3"

        with wx.FileDialog(self, "Save Preview As", wildcard="MP3 audio (*.mp3)|*.mp3",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                           defaultFile=default_filename) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            save_path = fileDialog.GetPath()
        self.download_progress_dialog = wx.ProgressDialog(
            "Downloading Preview", "Starting download...", maximum=100, parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME
        )
        self.download_progress_dialog.Show()
        download_future = self.executor.submit(self.download_worker, self.audio_url, save_path, self.download_progress_dialog)
        download_future.add_done_callback(self.on_download_complete)

    def on_dialog_close_event(self, event):
        """Handles the dialog being closed via window's 'X' button."""
        self.cleanup_and_close()

    def download_worker(self, url, save_path, progress_dialog):
        """Downloads the audio file in a background thread."""
        downloaded_bytes = 0
        chunk_size = 8192
        cancelled = False
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                total_length = r.headers.get('content-length')
                total_length = int(total_length) if total_length else None

                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        keep_going, _ = wx.CallAfter(progress_dialog.Update, 0).Get()
                        if not keep_going:
                             cancelled = True
                             break

                        if chunk:
                            f.write(chunk)
                            downloaded_bytes += len(chunk)
                            if total_length:
                                progress = int(100 * downloaded_bytes / total_length)
                                wx.CallAfter(progress_dialog.Update, progress, f"Downloading... {progress}%")
                            else:
                                # Pulse if total length is unknown
                                wx.CallAfter(progress_dialog.Pulse, f"Downloading... {downloaded_bytes // 1024} KB")

            if cancelled:
                if os.path.exists(save_path):
                    os.remove(save_path)
                return "Cancelled"
            elif total_length and downloaded_bytes < total_length:
                 return "Incomplete"
            else:
                return "Success"

        except requests.exceptions.RequestException as e:
            return f"Network error: {e}"
        except IOError as e:
            return f"File error: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

    def on_download_complete(self, future):
        """Callback executed when download attempt finishes."""
        if hasattr(self, 'download_progress_dialog') and self.download_progress_dialog:
            if self.download_progress_dialog.IsShown():
                 wx.CallAfter(self.download_progress_dialog.Destroy)
            self.download_progress_dialog = None

        try:
            result = future.result()
            if result == "Success":
                wx.CallAfter(wx.MessageBox, "Preview saved successfully!", "Download Complete", wx.OK | wx.ICON_INFORMATION, self)
            elif result == "Incomplete":
                 wx.CallAfter(wx.MessageBox, "Download finished, but may be incomplete.", "Warning", wx.OK | wx.ICON_WARNING, self)
            else:
                wx.CallAfter(wx.MessageBox, f"Failed to save preview:\n{result}", "Download Error", wx.OK | wx.ICON_ERROR, self)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"An error occurred during download:\n{e}", "Download Error", wx.OK | wx.ICON_ERROR, self)

    def handle_vlc_playing(self, event):
        if self._is_closing: return
        wx.CallAfter(self.play_button.SetLabel, "&Pause")

    def handle_vlc_end_reached(self, event):
        if self._is_closing: return
        wx.CallAfter(self.cleanup_and_close)

    def handle_vlc_error(self, event):
        if self._is_closing: return
        wx.CallAfter(wx.MessageBox, "An error occurred during playback.", "Playback Error", wx.OK | wx.ICON_ERROR, self)
        wx.CallAfter(self.cleanup_and_close)

    def handle_vlc_stopped(self, event):
        if self._is_closing: return
        state = self._media_player.get_state() if self._media_player else None
        if self._playback_started and state != vlc.State.Ended:
             wx.CallAfter(self.play_button.SetLabel, "&Play")


    def cleanup_and_close(self):
        """Stops playback, releases resources, and closes the dialog."""
        if self._event_manager:
            try:
                # Detach all events at once if possible, otherwise specific ones
                self._event_manager.event_detach(vlc.EventType.MediaPlayerPlaying)
                self._event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                self._event_manager.event_detach(vlc.EventType.MediaPlayerEncounteredError)
                self._event_manager.event_detach(vlc.EventType.MediaPlayerStopped)
            except Exception as e:
                print(f"Error detaching VLC events: {e}")
            self._event_manager = None # Avoid reuse

        if self._media_player:
            try:
                if self._media_player.is_playing() or self._media_player.get_state() == vlc.State.Paused:
                    self._media_player.stop()
                self._media_player.release()
            except Exception as e:
                print(f"Error stopping/releasing VLC player: {e}")
            self._media_player = None

        if self._vlc_instance:
             try:
                 # self._vlc_instance.release()
                 pass
             except Exception as e:
                 print(f"Error releasing VLC instance: {e}")
             # self._vlc_instance = None # Keep instance usually

        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)
        else:
            if self:
                try:
                    self.Destroy()
                except wx.wxAssertionError as e:
                    pass

    def __del__(self):
        """Ensure executor shutdown as fallback."""
        if hasattr(self, 'executor') and self.executor:
            self.executor.shutdown(wait=False)
