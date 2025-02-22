import wx
import yt_dlp
from tools.network_player.youtube_player import YoutubePlayer
from speech import speak
import concurrent.futures

class YoutubeStreamer(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Play YouTube Link", size=(400, 300))
        self.parent = parent
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        url_label = wx.StaticText(panel, label="Enter YouTube Link:")
        vbox.Add(url_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.url_text = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.url_text.Bind(wx.EVT_TEXT_ENTER, self.on_ok)
        vbox.Add(self.url_text, 0, wx.ALL | wx.EXPAND, 10)

        play_as_label = wx.StaticText(panel, label="Play as:")
        vbox.Add(play_as_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.play_as_choices = ["Video", "Audio"]
        self.play_as_radio = wx.RadioBox(panel, choices=self.play_as_choices, majorDimension=1)
        vbox.Add(self.play_as_radio, 0, wx.ALL | wx.EXPAND, 10)

        quality_label = wx.StaticText(panel, label="Video Quality:")
        vbox.Add(quality_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.quality_choices = ["Low", "Medium", "Best"]
        self.quality_combo = wx.ComboBox(panel, choices=self.quality_choices, style=wx.CB_READONLY)
        self.quality_combo.SetSelection(0)
        vbox.Add(self.quality_combo, 0, wx.ALL | wx.EXPAND, 10)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(panel, id=wx.ID_OK, label="OK")
        ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
        hbox.Add(ok_button, 0, wx.ALL, 10)

        cancel_button = wx.Button(panel, id=wx.ID_CANCEL, label="Cancel")
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        hbox.Add(cancel_button, 0, wx.ALL, 10)
        vbox.Add(hbox, 0, wx.ALIGN_CENTER_HORIZONTAL, 10)

        panel.SetSizer(vbox)
        self.Centre()

    def on_ok(self, event):
        url = self.url_text.GetValue()
        if not url:
            wx.MessageBox("Please enter a YouTube link.", "Error", wx.OK | wx.ICON_ERROR)
            return

        play_as_audio = self.play_as_radio.GetSelection() == 1
        quality = self.quality_choices[self.quality_combo.GetSelection()].lower()

        loading_msg = "Loading Audio..." if play_as_audio else "Loading Video..."
        loading_dlg = wx.ProgressDialog("Loading", loading_msg, maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
        future = self.executor.submit(self.extract_and_play, url, play_as_audio, quality)
        self.executor.submit(self.handle_future, future, loading_dlg, url)

    def handle_future(self, future, loading_dlg, url):
        """Handles the result of the future (stream extraction)."""
        try:
            result = future.result()
            if result:
                media_url, title, description = result
                wx.CallAfter(loading_dlg.Destroy)
                wx.CallAfter(self.play_in_youtube_player, media_url, title, description, url)
            else:
                wx.CallAfter(loading_dlg.Destroy)
                wx.CallAfter(wx.MessageBox, "Failed to extract stream information.", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.CallAfter(loading_dlg.Destroy)
            wx.CallAfter(wx.MessageBox, f"Error: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_cancel(self, event):
        self.Destroy()

    def extract_and_play(self, url, play_as_audio, quality):
        """Extracts the direct stream URL and title using yt_dlp."""
        try:
            ydl_opts = {
                'quiet': True,
                'noplaylist': True,
                'format': self.get_format_string(play_as_audio, quality)
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                media_url = info_dict.get('url', None)
                title = info_dict.get('title', "")
                description = info_dict.get('description', "")
                if not media_url:
                    raise ValueError("No playable URL found.")

                return media_url, title, description
        except Exception as e:
            print(f"Error during extraction: {e}")
            return None

    def get_format_string(self, play_as_audio, quality):
        """Returns the appropriate format string for yt_dlp based on user choices."""
        if play_as_audio:
            return 'bestaudio/best'
        else:
            if quality == "low":
                return 'worst[ext=mp4]/worst'
            elif quality == "medium":
                return 'best[height<=720][ext=mp4]/best[ext=mp4]/best'
            else:  # Best
                return 'best[ext=mp4]/best'

    def play_in_youtube_player(self, media_url, title, description, original_youtube_link):
        """Creates and shows the YoutubePlayer with the extracted stream."""
        wx.CallAfter(self._do_play_in_youtube_player, media_url, title, description, original_youtube_link)

    def _do_play_in_youtube_player(self, media_url, title, description, original_youtube_link):
        """Actual creation and showing of the YoutubePlayer (must be done in the main thread)."""
        player = YoutubePlayer(self.parent, title, media_url, None, description, original_youtube_link, None, None)
        player.Bind(wx.EVT_CLOSE, player.OnClose)
        player.Show()
        self.Destroy()