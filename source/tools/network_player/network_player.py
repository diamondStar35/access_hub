import wx
import re
import threading
from gui.settings import load_app_config
from .media_player import DirectLinkPlayer, EVT_VLC_READY
from .youtube_search import YoutubeSearchDialog
from .youtube_streamer import YoutubeStreamer
from .favorites_manager import FavoritesFrame
from .download_dialogs import DownloadSettingsDialog, DownloadDialog
from .utils import run_yt_dlp_json
from .youtube_player import YoutubePlayer

# Constants for ClipboardActionDialog button IDs
ID_PLAY_CLIPBOARD_VIDEO = wx.NewIdRef()
ID_DOWNLOAD_CLIPBOARD_VIDEO = wx.NewIdRef()


class NetworkPlayerFrame(wx.Frame):
    def __init__(self, parent, title):
        super(NetworkPlayerFrame, self).__init__(parent, title=title, size=(400, 200))
        # parent is AccessHub
        self.access_hub_instance = parent 
        self.clipboard_loading_dlg = None
        self.player=None

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        youtube_button = wx.Button(panel, label="Search in YouTube")
        youtube_button.Bind(wx.EVT_BUTTON, self.on_youtube_search)  # Not implemented yet
        vbox.Add(youtube_button, 0, wx.ALL | wx.CENTER, 10)

        youtube_link_button = wx.Button(panel, label="Play a youtube link")
        youtube_link_button.Bind(wx.EVT_BUTTON, self.on_youtube_link)
        vbox.Add(youtube_link_button, 0, wx.ALL | wx.CENTER, 10)

        direct_link_button = wx.Button(panel, label="Play a direct Link")
        direct_link_button.Bind(wx.EVT_BUTTON, self.on_direct_link)
        vbox.Add(direct_link_button, 0, wx.ALL | wx.CENTER, 10)

        favorites_button = wx.Button(panel, label="Favorite videos")
        favorites_button.Bind(wx.EVT_BUTTON, self.on_open_favorites)
        vbox.Add(favorites_button, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(vbox)
        self.Centre()
        self.Show(True)
        # Check clipboard after the frame is initialized and shown
        wx.CallAfter(self.check_clipboard)


    def _is_youtube_video_link(self, text_to_check):
        """
        Checks if the given text is a plausible YouTube video link.
        Returns (bool, str|None): (True, matched_url) or (False, None).
        """
        if not text_to_check or not isinstance(text_to_check, str):
            return False, None

        # Regex patterns to match common YouTube video URL formats
        video_patterns = [
            re.compile(r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+(?:&[a-zA-Z0-9_=&%.-]*)?)'),
            re.compile(r'(https?://youtu\.be/[\w-]+(?:\?[a-zA-Z0-9_=&%.-]*)?)'),
            re.compile(r'(https?://m\.youtube\.com/watch\?v=[\w-]+(?:&[a-zA-Z0-9_=&%.-]*)?)')
        ]

        for pattern in video_patterns:
            match = pattern.search(text_to_check)
            if match:
                url_lower = match.group(0).lower()
                # filter to avoid triggering for playlist or channel pages copied to clipboard
                if "/playlist?list=" in url_lower or \
                   "/channel/" in url_lower or \
                   "/c/" in url_lower or \
                   "@" in url_lower.split('/')[-1]:
                    continue # This looks more like a playlist or channel page
                return True, match.group(0) # Return True and the full matched URL
        return False, None

    def check_clipboard(self):
        """Checks clipboard for a YouTube link and prompts user to download."""
        clipboard_text = ""
        try:
            if wx.TheClipboard.Open():
                if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_TEXT)):
                    data_object = wx.TextDataObject()
                    wx.TheClipboard.GetData(data_object)
                    clipboard_text = data_object.GetText()
                wx.TheClipboard.Close()
        except Exception:
            return

        if clipboard_text:
            is_youtube, youtube_url = self._is_youtube_video_link(clipboard_text)
            if is_youtube and youtube_url:
                action_dialog = ClipboardActionDialog(self, youtube_url)
                result = action_dialog.ShowModal()
                action_dialog.Destroy()

                play_id = ID_PLAY_CLIPBOARD_VIDEO.GetId()
                download_id = ID_DOWNLOAD_CLIPBOARD_VIDEO.GetId()
                if result == play_id:
                    self.Hide()
                    parent_for_loading = self.access_hub_instance if self.access_hub_instance else wx.GetApp().GetTopWindow()
                    self.clipboard_loading_dlg = wx.ProgressDialog("Loading Video", "Getting video information, please wait...", maximum=100, parent=parent_for_loading, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
                    self.clipboard_loading_dlg.Show()
                    threading.Thread(target=self._fetch_and_prepare_clipboard_play, args=(youtube_url,)).start()

                elif result == download_id:
                    settings_dialog = DownloadSettingsDialog(self, "Download Settings", "Youtube video", youtube_url)
                    if settings_dialog.ShowModal() == wx.ID_OK:
                        download_settings = settings_dialog.settings
                        dlg_title = f"Downloading: {download_settings['filename']}"
                        download_dlg = DownloadDialog(self, dlg_title, download_settings)
                        download_dlg.download_task()
                    settings_dialog.Destroy()

    def _fetch_and_prepare_clipboard_play(self, youtube_url):
        """Worker thread to fetch video info for clipboard playback."""
        try:
            config = self.access_hub_instance.config if self.access_hub_instance and hasattr(self.access_hub_instance, 'config') else load_app_config()
            youtube_settings = config.get('YouTube', {})
            default_video_quality = youtube_settings.get('video_quality', 'Medium').lower()

            format_selector = 'best[ext=mp4]/bestvideo[ext=mp4]/best' # Default
            if default_video_quality == "low":
                format_selector = 'worst[ext=mp4]/worstvideo[ext=mp4]/worst'
            elif default_video_quality == "medium":
                format_selector = 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'

            info_dict = run_yt_dlp_json(youtube_url, format_selector=format_selector)
            if not info_dict:
                raise ValueError("Failed to retrieve video information using yt-dlp.")

            media_url = info_dict.get('url')
            title = info_dict.get('title', 'YouTube Video')
            description = info_dict.get('description', '')
            if not media_url:
                formats = info_dict.get('formats', [])
                if formats: media_url = formats[0].get('url')

            if not media_url:
                raise ValueError("No playable media URL found in the video information.")

            wx.CallAfter(self._launch_clipboard_player, title, media_url, description, youtube_url)

        except Exception as e:
            wx.CallAfter(self._destroy_clipboard_loading_dialog)
            error_parent = self.access_hub_instance if self.access_hub_instance else self
            wx.CallAfter(wx.MessageBox, f"Could not play video from clipboard: {e}", "Playback Error", wx.OK | wx.ICON_ERROR, error_parent)
            wx.CallAfter(self.Show)

    def _launch_clipboard_player(self, title, media_url, description, original_youtube_link):
        """Creates and shows the YoutubePlayer from clipboard link info."""
        wx.CallAfter(self._destroy_clipboard_loading_dialog)
        self.player = YoutubePlayer(parent=None, title=title, url=media_url, search_results_frame=self, description=description, original_youtube_link=original_youtube_link, results=None, current_index=-1)

    def _destroy_clipboard_loading_dialog(self):
        if self.clipboard_loading_dlg:
            try:
                self.clipboard_loading_dlg.Destroy()
            except RuntimeError:
                pass
            self.clipboard_loading_dlg = None

    def on_youtube_search(self, event):
        searchdlg = YoutubeSearchDialog(self, self)
        searchdlg.ShowModal()
        searchdlg.Destroy()

    def on_direct_link(self, event):
        dlg = wx.TextEntryDialog(self, "Enter the direct link:", "Play stream from a direct link")
        if dlg.ShowModal() == wx.ID_OK:
            link = dlg.GetValue()
            self.play_video(link)
        dlg.Destroy()

    def on_youtube_link(self, event):
        streamerdlg = YoutubeStreamer(self)
        streamerdlg.ShowModal()
        streamerdlg.Destroy()

    def on_open_favorites(self, event):
        """Opens the Favorites window."""
        self.Hide()
        favorites_frame = FavoritesFrame(self.access_hub_instance, calling_frame_to_show_on_my_close=self)
        self.access_hub_instance.add_child_frame(favorites_frame)
        favorites_frame.Show()

    def play_video(self, link):
        self.player = DirectLinkPlayer(self, "Direct link Player", link)
        self.player.Bind(EVT_VLC_READY, self.player.onVlcReady)
        self.player.Bind(wx.EVT_CLOSE, self.player.OnClose)

    def OnClose(self, event):
        if hasattr(self, 'player') and self.player:
            self.player.Close()
        event.Skip()

class ClipboardActionDialog(wx.Dialog):
    def __init__(self, parent, youtube_url):
        super().__init__(parent, title="YouTube Link Detected", style=wx.DEFAULT_DIALOG_STYLE)
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        message_text = f"Access Hub detected a YouTube link in your clipboard:\n\nWhat would you like to do?"
        message_label = wx.StaticText(panel, label=message_text)
        main_sizer.Add(message_label, 0, wx.ALL | wx.EXPAND, 15)

        button_sizer = wx.StdDialogButtonSizer()
        play_button = wx.Button(panel, ID_PLAY_CLIPBOARD_VIDEO, "Play Video")
        download_button = wx.Button(panel, ID_DOWNLOAD_CLIPBOARD_VIDEO, "Download Video")
        cancel_button = wx.Button(panel, wx.ID_CANCEL)

        button_sizer.AddButton(play_button)
        button_sizer.AddButton(download_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM | wx.TOP, 10)
        panel.SetSizerAndFit(main_sizer)
        self.Fit()
        self.CentreOnParent()

        play_button.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(ID_PLAY_CLIPBOARD_VIDEO.GetId()))
        download_button.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(ID_DOWNLOAD_CLIPBOARD_VIDEO.GetId()))
