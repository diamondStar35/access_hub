import wx
from wx.lib.newevent import NewEvent
from gui.custom_controls import CustomButton
import vlc
import sys
import threading
from speech import speak
import time

# Create a custom event for when VLC is ready
VlcReadyEvent, EVT_VLC_READY = NewEvent()

class DirectLinkPlayer(wx.Frame):
    def __init__(self, parent, title, url, show_loading_dialog=True):
        super().__init__(parent, title=title, size=(640, 480))
        self.panel = wx.Panel(self)
        self.url = url
        self.instance = None
        self.player = None
        self.loading_dialog = None

        # Create custom buttons
        self.rewind_button = CustomButton(self.panel, label="Rewind")
        self.pause_button = CustomButton(self.panel, label="Pause")
        self.forward_button = CustomButton(self.panel, label="Forward")

        # Bind button events
        self.rewind_button.Bind(wx.EVT_BUTTON, self.onRewind)
        self.pause_button.Bind(wx.EVT_BUTTON, self.onPause)
        self.forward_button.Bind(wx.EVT_BUTTON, self.onForward)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL) # Create button sizer
        button_sizer.Add(self.rewind_button, 0, wx.ALL, 5)
        button_sizer.Add(self.pause_button, 0, wx.ALL, 5)
        button_sizer.Add(self.forward_button, 0, wx.ALL, 5)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(button_sizer, 0, wx.ALIGN_CENTER|wx.ALL, 15)
        self.panel.SetSizer(sizer)
        sizer.Fit(self.panel)

        # Bind keyboard shortcuts
        self.Bind(wx.EVT_CHAR_HOOK, self.onKey)

        if show_loading_dialog:
            self.loading_dialog = wx.Dialog(self, title="Loading...", style=wx.CAPTION)
            loading_text = wx.StaticText(self.loading_dialog, -1, "Loading...")
            loading_sizer = wx.BoxSizer(wx.VERTICAL)
            loading_sizer.Add(loading_text, 0, wx.ALL | wx.CENTER, 10)
            self.loading_dialog.SetSizer(loading_sizer)
            self.loading_dialog.Show()
        else:
           self.Show()

        # Initialize VLC in a separate thread
        threading.Thread(target=self.init_vlc_thread).start()
        self.Bind(EVT_VLC_READY, self.onVlcReady)


    def init_vlc_thread(self):
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        media = self.instance.media_new(self.url)
        self.player.set_media(media)

        if sys.platform == "win32":
             self.player.set_hwnd(self.panel.GetHandle())
        elif sys.platform == "darwin":
            self.player.set_nsobject(self.panel.GetHandle())
        else:
            self.player.set_xwindow(self.panel.GetHandle())

        # Attach event handler for MediaPlayerOpening
        event_manager = self.player.event_manager()
        event_manager.event_attach(vlc.EventType.MediaPlayerOpening, self.on_media_opening)
        self.player.play()
        wx.PostEvent(self, VlcReadyEvent())  # Post the event after play()

    def on_media_opening(self, event):
        wx.PostEvent(self, VlcReadyEvent())

    def onVlcReady(self, event):
        if self.loading_dialog:
            self.loading_dialog.Destroy()
        self.Show()
        self.SetFocus() #Give focus to the main frame

    def onRewind(self, event):
        self.player.set_time(self.player.get_time() - 5000)

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
        self.player.set_time(self.player.get_time() + 5000)

    def onKey(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_SPACE:
           self.onPause(event)
        elif keycode == wx.WXK_LEFT:
            self.onRewind(event)
        elif keycode == wx.WXK_RIGHT:
            self.onForward(event)
        elif keycode == wx.WXK_UP:
            self.onVolumeUp(event)
        elif keycode == wx.WXK_DOWN:
            self.onVolumeDown(event)
        elif keycode == ord('V') or keycode == ord('v'):
            self.onAnnounceVolume(event)
        elif keycode == ord('E') or keycode == ord('e'):
            self.onAnnounceElapsedTime(event)
        elif keycode == ord('R') or keycode == ord('r'):
            self.onAnnounceRemainingTime(event)
        elif keycode == ord('T') or keycode == ord('t'):
            self.onAnnounceTotalTime(event)
        elif keycode == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

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

    def OnClose(self, event):
        if self.player:
            self.player.stop()
            self.player.release()
            self.instance.release()
            self.player = None
        if self.loading_dialog: #Close the dialog if it still exists.
            self.loading_dialog.Destroy()
        self.Destroy()