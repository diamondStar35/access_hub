import wx
import vlc
import requests
import concurrent.futures, threading
import os, re, tempfile
import shutil
import base64

class SimplePlayer(wx.Dialog):
    """
    A simple dialog using python-vlc to play and optionally save an audio stream URL or base64 encoded data.
    Handles button events, Escape key, and auto-closes on playback end/error.
    """
    def __init__(self, parent, audio_url: str = None, audio_base64: str = None, media_type: str = None, title="Audio Preview"):
        """
        Initializes the player dialog. Provide either audio_url OR audio_base64/media_type.

        Args:
            parent: The parent window.
            audio_url: The URL of the audio stream to play.
            audio_base64: Base64 encoded audio data.
            media_type: The MIME type of the base64 audio (e.g., 'audio/mpeg', 'audio/wav'). Required if audio_base64 is used.
            title: The title for the dialog window.
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.CLOSE_BOX)

        self.audio_url = audio_url
        self.audio_base64 = audio_base64
        self.media_type = media_type
        self.dialog_title = title
        self._vlc_instance = None
        self._media_player = None
        self._event_manager = None
        self._playback_started = False
        self._is_closing = False
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.download_progress_dialog = None
        self._cancel_download_event = threading.Event()
        self.temp_audio_file = None
        self.decoded_audio_data = None

        if self.audio_base64 and self.media_type:
            try:
                self.decoded_audio_data = base64.b64decode(self.audio_base64)
                # Determine extension for temp file
                ext = self._get_extension_from_mimetype(self.media_type)
                fd, self.temp_audio_file = tempfile.mkstemp(suffix=ext)
                os.close(fd)
                with open(self.temp_audio_file, 'wb') as f:
                    f.write(self.decoded_audio_data)
                self.audio_url = f'file:///{self.temp_audio_file.replace(os.sep, "/")}'

            except (TypeError, ValueError, OSError, IOError) as e:
                 wx.MessageBox(f"Failed to process base64 audio data: {e}\nPlayback may fail.",
                               "Base64 Error", wx.OK | wx.ICON_ERROR, parent=self)
                 self.audio_base64 = None
                 self.decoded_audio_data = None
                 self.temp_audio_file = None
                 self.audio_url = None

        elif not self.audio_url:
             wx.MessageBox("No valid audio source (URL or Base64) provided.",
                           "Audio Source Error", wx.OK | wx.ICON_ERROR, parent=self)
             wx.CallAfter(self.cleanup_and_close)
             return

        self._init_ui()
        self._init_vlc()
        self.Bind(wx.EVT_CHAR_HOOK, self.on_escape)
        self.Bind(wx.EVT_CLOSE, self.on_dialog_close_event)

        # Attempt to play shortly after dialog is shown
        if self.audio_url:
            wx.CallLater(150, self.start_playback)
        self.CentreOnParent()

    def _get_extension_from_mimetype(self, mime_type):
        """Determines a file extension based on MIME type."""
        mime_map = {
            'audio/mpeg': '.mp3',
            'audio/wav': '.wav',
            'audio/x-wav': '.wav',
            'audio/ogg': '.ogg',
            'audio/opus': '.opus',
            'audio/aac': '.aac',
            'audio/flac': '.flac',
            'audio/x-flac': '.flac',
            'audio/basic': '.au', # For ulaw/alaw
            'audio/L16': '.pcm',
        }
        return mime_map.get(mime_type, '.bin')

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
        self.SetMinSize((550, 200))

    def _init_vlc(self):
        """Initialize VLC instance, player, and events."""
        if not self.audio_url:
            return

        try:
            vlc_opts = ["--no-video", "--quiet"]
            self._vlc_instance = vlc.Instance(vlc_opts)
            self._media_player = self._vlc_instance.media_player_new()
            self._event_manager = self._media_player.event_manager()
            self._media_player.audio_set_volume(100)

            # Attach events
            self._event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.handle_vlc_playing)
            self._event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.handle_vlc_end_reached)
            self._event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.handle_vlc_error)
            self._event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self.handle_vlc_stopped)

        except Exception as e:
            wx.MessageBox(f"Failed to initialize Audio player.\nError: {e}",
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
            if self.temp_audio_file:
                 media = self._vlc_instance.media_new_path(self.temp_audio_file)
            else:
                 media = self._vlc_instance.media_new(self.audio_url)

            media.add_option('network-caching=1000') # Still useful for URLs
            self._media_player.set_media(media)
            media.release()

            play_result = self._media_player.play()
            if play_result == -1:
                wx.CallAfter(wx.MessageBox, "Failed to start audio playback.", "Playback Error", wx.OK | wx.ICON_ERROR)
                wx.CallAfter(self.cleanup_and_close)
            else:
                self.play_button.SetLabel("&Pause")
                self._playback_started = True

        except Exception as e:
            error_detail = self.audio_url if len(self.audio_url) < 100 else self.audio_url[:100] + "..."
            wx.MessageBox(f"Failed to load or play audio source:\n{error_detail}\n\nError: {e}", "Playback Error", wx.OK | wx.ICON_ERROR, parent=self)
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
            else:
                 self.start_playback()
        except Exception as e:
             pass

    def on_play_button(self, event):
        """Handles the Play/Pause button click."""
        self.toggle_play_pause()

    def on_save_preview(self, event):
        """Handles the Save Preview button click."""
        # Sanitize title for default filename base
        sanitized_title = re.sub(r'[\\/*?:"<>|]', "", self.dialog_title)
        sanitized_title = sanitized_title.strip() if sanitized_title else "preview"

        if self.temp_audio_file and self.decoded_audio_data:
            default_extension = self._get_extension_from_mimetype(self.media_type)
            default_filename = f"{sanitized_title}{default_extension}"
            wildcard = f"{default_extension.upper()[1:]} files (*{default_extension})|*{default_extension}|All files (*.*)|*.*"

            with wx.FileDialog(self, "Save Preview As", wildcard=wildcard,
                               style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                               defaultFile=default_filename) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                save_path = fileDialog.GetPath()

            try:
                shutil.copyfile(self.temp_audio_file, save_path)
                wx.MessageBox("Preview saved successfully!", "Save Complete", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Failed to save preview file:\n{e}", "Save Error", wx.OK | wx.ICON_ERROR)

        elif self.audio_url and not self.temp_audio_file:
            default_filename = f"{sanitized_title}.mp3" # Assume mp3 for URL downloads unless header says otherwise
            with wx.FileDialog(self, "Save Preview As", wildcard="MP3 audio (*.mp3)|*.mp3|All files (*.*)|*.*",
                               style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                               defaultFile=default_filename) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                save_path = fileDialog.GetPath()

            self._cancel_download_event.clear()
            self.download_progress_dialog = wx.ProgressDialog(
                "Downloading Preview", "Starting download...", maximum=100, parent=self,
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT
            )
            self.download_progress_dialog.Bind(wx.EVT_CLOSE, self.on_cancel_download)
            self.download_progress_dialog.Bind(wx.EVT_BUTTON, self.on_cancel_download_button, id=wx.ID_CANCEL)
            self.download_progress_dialog.Show()
            download_future = self.executor.submit(self.download_worker, self.audio_url, save_path, self.download_progress_dialog, self._cancel_download_event)
            download_future.add_done_callback(self.on_download_complete)
        else:
            wx.MessageBox("No audio source available to save.", "Error", wx.OK | wx.ICON_WARNING)

    def on_cancel_download(self, event):
        """Called when the progress dialog's close button is clicked."""
        self._cancel_download_event.set()
        if self.download_progress_dialog and wx.FindWindowById(self.download_progress_dialog.GetId()):
            self.download_progress_dialog.Destroy()
        self.download_progress_dialog = None
        event.Skip()

    def on_cancel_download_button(self, event):
        """Called when the progress dialog's cancel button is clicked."""
        if event.GetId() == wx.ID_CANCEL:
            self._cancel_download_event.set()
            if self.download_progress_dialog and wx.FindWindowById(self.download_progress_dialog.GetId()):
                wx.CallAfter(self.download_progress_dialog.Update, 0, "Cancelling download...")

    def on_dialog_close_event(self, event):
        """Handles the dialog being closed via window's 'X' button."""
        self.cleanup_and_close()

    def download_worker(self, url, save_path, progress_dialog_ref, cancel_event):
        """Downloads the audio file in a background thread."""
        downloaded_bytes = 0
        chunk_size = 8192
        progress_dialog_id = progress_dialog_ref.GetId()

        try:
            with requests.get(url, stream=True, timeout=30) as r: # Added timeout
                r.raise_for_status()
                total_length = r.headers.get('content-length')
                total_length = int(total_length) if total_length else None

                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if cancel_event.is_set() or not wx.FindWindowById(progress_dialog_id):
                            if os.path.exists(save_path):
                                try: os.remove(save_path)
                                except OSError: pass
                            return "Cancelled"

                        if chunk:
                            f.write(chunk)
                            downloaded_bytes += len(chunk)
                            if total_length:
                                progress = int(100 * downloaded_bytes / total_length)
                                if wx.FindWindowById(progress_dialog_id):
                                     wx.CallAfter(progress_dialog_ref.Update, progress, f"Downloading... {progress}%")
                            elif wx.FindWindowById(progress_dialog_id):
                                 wx.CallAfter(progress_dialog_ref.Pulse, f"Downloading... {downloaded_bytes // 1024} KB")

            # Check if download might be incomplete (only if total_length was known)
            if total_length and downloaded_bytes < total_length:
                 result = "Incomplete"
            else:
                 result = "Success"
                 if wx.FindWindowById(progress_dialog_id):
                     wx.CallAfter(progress_dialog_ref.Update, 100, "Download complete.")
            return result

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {e}"
        except IOError as e:
            error_msg = f"File error: {e}"
        except Exception as e:
            error_msg = f"Unexpected error: {e}"

        if wx.FindWindowById(progress_dialog_id):
            wx.CallAfter(progress_dialog_ref.Destroy)
        return error_msg

    def on_download_complete(self, future):
        """Callback executed when download attempt finishes."""
        if hasattr(self, 'download_progress_dialog') and self.download_progress_dialog:
            if wx.FindWindowById(self.download_progress_dialog.GetId()):
                 wx.CallAfter(self.download_progress_dialog.Destroy)
            self.download_progress_dialog = None

        try:
            result = future.result()
            if result == "Success":
                wx.CallAfter(wx.MessageBox, "Preview saved successfully!", "Download Complete", wx.OK | wx.ICON_INFORMATION)
            elif result == "Incomplete":
                 wx.CallAfter(wx.MessageBox, "Download finished, but may be incomplete (file size mismatch).", "Warning", wx.OK | wx.ICON_WARNING)
            elif result == "Cancelled":
                 pass
            else:
                 # result contains the error message from the worker
                 wx.CallAfter(wx.MessageBox, f"Failed to save preview:\n{result}", "Download Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
             wx.CallAfter(wx.MessageBox, f"An error occurred finalizing download:\n{e}", "Download Error", wx.OK | wx.ICON_ERROR)

    def handle_vlc_playing(self, event):
        if self._is_closing: return
        wx.CallAfter(self.play_button.SetLabel, "&Pause")

    def handle_vlc_end_reached(self, event):
        if self._is_closing: return
        wx.CallAfter(self.play_button.SetLabel, "&Play")
        self._playback_started = False # Allow replaying
        # wx.CallAfter(self.cleanup_and_close) # Removed auto-close

    def handle_vlc_error(self, event):
        if self._is_closing: return
        wx.CallAfter(wx.MessageBox, "An error occurred during playback.", "Playback Error", wx.OK | wx.ICON_ERROR)
        wx.CallAfter(self.play_button.SetLabel, "&Play")
        self._playback_started = False
        wx.CallAfter(self.cleanup_and_close)

    def handle_vlc_stopped(self, event):
        if self._is_closing: return
        state = self._media_player.get_state() if self._media_player else None
        if self._playback_started and state not in [vlc.State.Ended, vlc.State.Error]:
             wx.CallAfter(self.play_button.SetLabel, "&Play")


    def cleanup_and_close(self):
        """Stops playback, releases resources, deletes temp file, and closes the dialog."""
        if self._is_closing: return
        self._is_closing = True

        if self._media_player:
            try:
                if self._media_player.is_playing() or self._media_player.get_state() == vlc.State.Paused:
                    self._media_player.stop()
            except Exception: pass

        # Detach VLC Events ---
        if self._event_manager:
            try:
                # Detach specific events
                self._event_manager.event_detach(vlc.EventType.MediaPlayerPlaying)
                self._event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                self._event_manager.event_detach(vlc.EventType.MediaPlayerEncounteredError)
                self._event_manager.event_detach(vlc.EventType.MediaPlayerStopped)
            except Exception: pass # Ignore errors during cleanup
            self._event_manager = None

        # Release VLC Player ---
        if self._media_player:
            try:
                self._media_player.release()
            except Exception: pass
            self._media_player = None

        # Release VLC Instance ---
        # Releasing instance might affect other players if shared, often not needed per-dialog
        # if self._vlc_instance:
        #      try: self._vlc_instance.release()
        #      except Exception: pass
        #      self._vlc_instance = None

        # Delete Temporary File ---
        if self.temp_audio_file:
            temp_path = self.temp_audio_file
            self.temp_audio_file = None
            try:
                os.remove(temp_path)
            except OSError as e:
                # print(f"Warning: Could not delete temp file {temp_path}: {e}")
                pass

        # Shutdown Executor ---
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None

        # Close Dialog ---
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)
        else:
            wx.CallAfter(self.Destroy)

    def __del__(self):
        """Fallback cleanup."""
        if hasattr(self, 'executor') and self.executor:
            self.executor.shutdown(wait=False)
        # Attempt to delete temp file as a last resort
        if hasattr(self, 'temp_audio_file') and self.temp_audio_file:
             try:
                 if os.path.exists(self.temp_audio_file):
                      os.remove(self.temp_audio_file)
             except OSError:
                  pass
