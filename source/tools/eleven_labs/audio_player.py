import wx
import vlc
import time
import threading


class SimpleVlcPlayer(wx.Dialog):
    """
    A simple dialog using python-vlc to play a single audio stream URL.
    It automatically closes when playback finishes or encounters an error.
    """
    def __init__(self, parent, audio_url: str, title="Audio Preview"):
        """
        Initializes the player dialog.

        Args:
            parent: The parent window.
            audio_url: The URL of the audio stream to play.
            title: The title for the dialog window.
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)

        self.audio_url = audio_url
        self._vlc_instance = None
        self._media_player = None
        self._event_manager = None
        self._playback_started = False

        self._init_ui()
        self._init_vlc()

        self.Bind(wx.EVT_CHAR_HOOK, self.on_escape)
        self.Bind(wx.EVT_CLOSE, self.on_dialog_close)

        # Attempt to play shortly after dialog is shown and event loop is running
        wx.CallLater(100, self.start_playback)
        self.CentreOnParent()

    def _init_ui(self):
        """Initialize UI elements."""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.play_button = wx.Button(panel, wx.ID_PLAY, label="&Play")
        self.close_button = wx.Button(panel, wx.ID_CLOSE, label="&Close")
        self.play_button.Disable()

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer(1)
        button_sizer.Add(self.play_button, 0, wx.ALL, 5)
        button_sizer.Add(self.close_button, 0, wx.ALL, 5)
        button_sizer.AddStretchSpacer(1)

        sizer.AddStretchSpacer(1)
        sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)
        sizer.AddStretchSpacer(1)

        panel.SetSizer(sizer)
        self.SetMinSize((400, 250))

    def _init_vlc(self):
        """Initialize VLC instance, player, and events."""
        try:
            self._vlc_instance = vlc.Instance("--no-video --quiet") # No video, less output
            self._media_player = self._vlc_instance.media_player_new()
            self._event_manager = self._media_player.event_manager()

            # Attach events - these callbacks run in a VLC thread
            self._event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.handle_vlc_playing)
            self._event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.handle_vlc_end_reached)
            self._event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.handle_vlc_error)
            self._event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self.handle_vlc_stopped)
            self.play_button.Enable()

        except Exception as e:
            wx.MessageBox(f"Failed to initialize Audio player.\n\nError: {e}",
                          "Player Error", wx.OK | wx.ICON_ERROR, self)
            wx.CallAfter(self.cleanup_and_close) # Close dialog if VLC fails

    def start_playback(self):
        """Loads the MRL and starts playback."""
        if not self._media_player or not self.audio_url:
            return

        try:
            media = self._vlc_instance.media_new(self.audio_url)
            media.add_option('network-caching=1000')
            self._media_player.set_media(media)
            media.release()

            play_result = self._media_player.play()
            if play_result == -1:
                wx.CallAfter(wx.MessageBox, "Failed to start audio playback.", "Playback Error", wx.OK | wx.ICON_ERROR, self)
                wx.CallAfter(self.cleanup_and_close)
            else:
                self.play_button.SetLabel("&Pause")
                self._playback_started = True

        except Exception as e:
            wx.MessageBox(f"Failed to load or play audio URL.\n\nError: {e}", "Playback Error", wx.OK | wx.ICON_ERROR, self)
            wx.CallAfter(self.cleanup_and_close)

    def toggle_play_pause(self, event=None):
        """Toggles playback state."""
        if not self._media_player: return

        if self._media_player.is_playing():
            self._media_player.pause()
            self.play_button.SetLabel("&Play")
        elif self._playback_started:
             # Check if stopped or paused
             state = self._media_player.get_state()
             if state == vlc.State.Paused or state == vlc.State.Stopped:
                 self._media_player.play()
                 self.play_button.SetLabel("&Pause")
        else:
             # If not started yet, trigger start_playback (e.g., if initial auto-play failed)
             self.start_playback()

    def on_play_button(self, event):
        """Handles the Play/Pause button click."""
        self.toggle_play_pause()

    def on_close_button(self, event):
        """Handles the Close button click."""
        self.cleanup_and_close()

    def on_dialog_close(self, event):
        """Handles the dialog being closed via window controls or Escape."""
        self.cleanup_and_close()

    def on_escape(self, event):
        """Handles the Escape key press."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.cleanup_and_close()
        else:
            event.Skip()

    def handle_vlc_playing(self, event):
        """Called when playback actually starts."""
        wx.CallAfter(self.play_button.SetLabel, "&Pause")

    def handle_vlc_end_reached(self, event):
        """Called when playback finishes normally."""
        wx.CallAfter(self.cleanup_and_close)

    def handle_vlc_error(self, event):
        """Called when a playback error occurs."""
        wx.CallAfter(wx.MessageBox, "An error occurred during playback.", "Playback Error", wx.OK | wx.ICON_ERROR, self)
        wx.CallAfter(self.cleanup_and_close)

    def handle_vlc_stopped(self, event):
        """Called when playback stops (manually or otherwise)."""
        # Reset button label if stopped not due to end/error
        if self._playback_started:
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
