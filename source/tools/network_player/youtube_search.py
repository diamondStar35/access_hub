import wx
from .youtube_player import YoutubePlayer, EVT_VLC_READY
from .download_dialogs import DownloadSettingsDialog, DownloadDialog
from .utils import run_yt_dlp_json
from youtubesearchpython import VideosSearch
from speech import speak
from configobj import ConfigObj
from gui.dialogs import DescriptionDialog
import app_vars
import threading
from wx.lib.newevent import NewEvent
import os

# Events for search completion and description
YoutubeSearchEvent, EVT_YOUTUBE_SEARCH = NewEvent()
DescriptionFetchEvent, EVT_DESCRIPTION_FETCH = NewEvent()

class YoutubeSearchDialog(wx.Dialog):
    def __init__(self, parent, network_player_frame):
        super().__init__(parent, title="YouTube Search", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.parent_window = network_player_frame
        self.search=None

        self.SetSize((500, 350))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        search_label = wx.StaticText(panel, label="Search:")
        vbox.Add(search_label, 0, wx.ALL, 5)

        self.search_text = wx.TextCtrl(panel)
        vbox.Add(self.search_text, 1, wx.ALL | wx.EXPAND, 5)

        search_button = wx.Button(panel, label="Search")
        search_button.Bind(wx.EVT_BUTTON, self.onSearch)
        search_button.SetDefault()
        vbox.Add(search_button, 0, wx.ALL | wx.ALIGN_RIGHT, 5)

        panel.SetSizer(vbox)
        self.Centre()


    def onSearch(self, event):
        search_term = self.search_text.GetValue()
        if not search_term: # Don't search if textbox is empty.
            return

        self.loading_dialog = wx.Dialog(self, title="Searching...", style=wx.CAPTION)
        loading_text = wx.StaticText(self.loading_dialog, -1, "Searching...")
        loading_sizer = wx.BoxSizer(wx.VERTICAL)
        loading_sizer.Add(loading_text, 0, wx.ALL | wx.CENTER, 10)
        self.loading_dialog.SetSizer(loading_sizer)
        self.loading_dialog.Show()

        threading.Thread(target=self.search_youtube, args=(search_term,)).start()
        self.Bind(EVT_YOUTUBE_SEARCH, self.onSearchResults)

    def search_youtube(self, search_term):
        try:
            self.search = VideosSearch(search_term, limit=20)
            results = self.search.result()
            wx.PostEvent(self, YoutubeSearchEvent(results=results, search_instance=self.search))
        except Exception as e:
            print(f"Error during YouTube search: {e}")
            wx.PostEvent(self, YoutubeSearchEvent(results=[], search_instance=None))

    def onSearchResults(self, event):
        results = event.results
        search_instance = event.search_instance
        self.loading_dialog.Destroy()

        if results:
            youtube_results = YoutubeSearchResults(self.parent_window, results, search_instance)
            youtube_results.Show()
        else:
            wx.MessageBox("No results found.", "YouTube Search", wx.OK | wx.ICON_INFORMATION)
        self.Destroy()


class YoutubeSearchResults(wx.Frame):
    def __init__(self, parent, results, search_instance):
        super().__init__(parent, title="Search Results", size=(800, 650), style=wx.DEFAULT_DIALOG_STYLE| wx.RESIZE_BORDER)
        self.player=None
        self.parent=parent
        self.context_menu=None
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.ffmpeg_path = os.path.join(project_root, 'ffmpeg.exe')
        self.search_instance = search_instance
        self.loading_more = False
        self.no_more_results = False
        self.load_settings()

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.results_label = wx.StaticText(panel, -1, "Search Results:")
        vbox.Add(self.results_label, 0, wx.ALL, 5)

        self.results_listbox = wx.ListBox(panel)
        vbox.Add(self.results_listbox, 1, wx.ALL | wx.EXPAND, 5)

        play_button = wx.Button(panel, label="Play")
        play_button.Bind(wx.EVT_BUTTON, self.onPlay)
        play_button.SetDefault()
        vbox.Add(play_button, 0, wx.ALL | wx.ALIGN_RIGHT, 5)

        download_button = wx.Button(panel, label="Download")
        download_button.Bind(wx.EVT_BUTTON, self.onDownloadSelectedVideo)
        vbox.Add(download_button, 0, wx.ALL | wx.ALIGN_RIGHT, 5)

        panel.SetSizer(vbox)
        self.results = []
        self.populate_results_listbox(results['result'])
        self.Bind(wx.EVT_SHOW, self.onShow)
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Bind(wx.EVT_CHAR_HOOK, self.onKey)
        self.results_listbox.Bind(wx.EVT_CONTEXT_MENU, self.onContextMenu)
        self.results_listbox.Bind(wx.EVT_LISTBOX, self.onListBox)
        self.Bind(EVT_DESCRIPTION_FETCH, self.onDescriptionFetchComplete)


    def onListBox(self, event):
        if self.results_listbox.GetSelection() == self.results_listbox.GetCount() - 1:
            if not self.loading_more and not self.no_more_results:
                self.loadMoreVideos()
        event.Skip()

    def populate_results_listbox(self, results): #Corrected the loop and result appending.
        for result in results:
            title = result['title']
            duration = self.format_duration(result['duration'])
            uploader = result['channel']['name']
            item_text = f"{title} , Duration: {duration}, By: {uploader}"
            self.results_listbox.Append(item_text)
            self.results.append(result)

    def load_settings(self):
        """Loads settings from the config file."""
        config_path = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name, "settings.ini")
        self.config = ConfigObj(config_path)
        youtube_settings = self.config.get('YouTube', {})
        self.default_quality = youtube_settings.get('video_quality', 'Medium')

    def loadMoreVideos(self):
        self.loading_more = True
        speak("Loading more videos...")

        def get_more_results():
            try:
                if self.search_instance.next():
                    new_results = self.search_instance.result()['result']
                    wx.CallAfter(self.addMoreResults, new_results)
                else:
                    self.no_more_results = True
                    wx.CallAfter(speak, "No more videos to load.")
            except Exception as e:
                print(f"Error during YouTube search: {e}")
                wx.CallAfter(speak, "Error loading more videos.")
            finally:
                self.loading_more = False

        threading.Thread(target=get_more_results).start()

    def addMoreResults(self, new_results):
        start_index = len(self.results)  # Get the index to start appending new items
        for result in new_results:
            title = result['title']
            duration = self.format_duration(result['duration'])
            uploader = result['channel']['name']
            item_text = f"{title} , Duration: {duration}, By: {uploader}"
            self.results_listbox.Append(item_text)
            self.results.append(result)
        speak("Finished loading.")

    def format_duration(self, duration_str):
        if duration_str is None:
            return "Unknown"

        try:
           minutes, seconds = map(int,duration_str.split(':'))
           total_seconds = minutes*60 + seconds
           hours, remainder = divmod(total_seconds, 3600)
           minutes, seconds = divmod(remainder, 60)
           return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

        except ValueError:
            return duration_str

    def onPlayQuality(self, event, quality):
        selection = self.results_listbox.GetSelection()
        if selection != -1:
            selected_video = self.results[selection]
            threading.Thread(target=self.get_direct_link_and_play_with_quality, args=(selected_video['link'], selected_video['title'], quality)).start()

    def get_direct_link_and_play_with_quality(self, url, title, quality):
        try:
            wx.CallAfter(self.show_loading_dialog, title)
            wx.CallAfter(self.Hide)

            format_selector = None
            if quality == "low":
                # Try worst MP4 first, then worst video MP4, then absolute worst combined
                format_selector = 'worst[ext=mp4]/worstvideo[ext=mp4]/worst'
            elif quality == "medium":
                 # Try best combined MP4 <=720p, then best video MP4 <=720p, then best combined <=720p
                format_selector = 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'
            elif quality == "best":
                 # Try best combined MP4, then best video MP4, then best combined overall
                format_selector = 'best[ext=mp4]/bestvideo[ext=mp4]/best'

            info_dict = run_yt_dlp_json(url, format_selector=format_selector)
            if not info_dict:
                raise ValueError("Failed to get video info from yt-dlp.")

            media_url = info_dict.get('url')
            description = info_dict.get('description', '') # Get description from JSON

            if not media_url:
                # Fallback: Check 'formats' list if top-level 'url' isn't populated (less common with -f)
                formats = info_dict.get('formats', [])
                if formats:
                    media_url = formats[0].get('url') # Assume the first format is the chosen one

            if not media_url:
                print("Could not find media URL in yt-dlp JSON output.")
                raise ValueError("No playable URL found in yt-dlp output.")

            wx.CallAfter(self.create_and_show_player, title, media_url, description, url)

        except Exception as e:
            wx.CallAfter(self.destroy_loading_dialog)
            wx.CallAfter(wx.MessageBox, f"Could not play: {e}", "Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Show) # Show the results window again on failure

    def onPlay(self, event, play_as_audio=False):
        selection = self.results_listbox.GetSelection()
        if selection != -1:
            selected_video = self.results[selection]
            threading.Thread(target=self.get_direct_link_and_play, args=(selected_video['link'], selected_video['title'], play_as_audio)).start()

    def get_direct_link_and_play(self, url, title, play_as_audio):
        try:
            wx.CallAfter(self.show_loading_dialog, title, play_as_audio)
            wx.CallAfter(self.Hide)

            format_selector = None
            if play_as_audio:
                format_selector = 'ba/b'
            else:
                if self.default_quality == "Low":
                    format_selector = 'worst[ext=mp4]/worstvideo[ext=mp4]/worst'
                elif self.default_quality == "Medium":
                    format_selector = 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'
                elif self.default_quality == "Best":
                    format_selector = 'best[ext=mp4]/bestvideo[ext=mp4]/best'
                else:
                    format_selector = 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'

            info_dict = run_yt_dlp_json(url, format_selector=format_selector)
            if not info_dict:
                raise ValueError("Failed to get video info from yt-dlp.")

            media_url = info_dict.get('url')
            description = info_dict.get('description', '') # Get description from JSON

            if not media_url:
                formats = info_dict.get('formats', [])
                if formats:
                    media_url = formats[0].get('url')
            if not media_url:
                print("Could not find media URL in yt-dlp JSON output.")
                raise ValueError("No playable URL found in yt-dlp output.")

            wx.CallAfter(self.create_and_show_player, title, media_url, description, url)

        except Exception as e:
            wx.CallAfter(self.destroy_loading_dialog)
            wx.CallAfter(wx.MessageBox, f"Could not play video: {e}", "Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Show) # Show the results window again on failure

    def create_and_show_player(self, title, url, description, original_youtube_link):
        self.player = YoutubePlayer(None, title, url, self, description, original_youtube_link, self.results, self.results_listbox.GetSelection())
        self.player.Bind(EVT_VLC_READY, self.show_when_ready)
        self.player.Bind(wx.EVT_CLOSE, self.player.OnClose)

    def show_when_ready(self, event):
        self.destroy_loading_dialog()
        self.player.Show()
        event.Skip()

    def show_loading_dialog(self, title, is_audio=False):
        if is_audio:
            self.loading_dialog = wx.Dialog(None, title="Playing audio...", style=wx.CAPTION)
            loading_text = wx.StaticText(self.loading_dialog, -1, f"Playing audio: {title}...")
        else:
            self.loading_dialog = wx.Dialog(None, title="Playing...", style=wx.CAPTION)
            loading_text = wx.StaticText(self.loading_dialog, -1, f"Playing: {title}...")
        loading_sizer = wx.BoxSizer(wx.VERTICAL)
        loading_sizer.Add(loading_text, 0, wx.ALL | wx.CENTER, 10)
        self.loading_dialog.SetSizer(loading_sizer)
        self.loading_dialog.Show()

    def destroy_loading_dialog(self, event=None):
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            self.loading_dialog.Destroy()
            self.loading_dialog=None
        if event:
            event.Skip()

    def onKey(self, event):
        keycode = event.GetKeyCode()
        modifiers = event.GetModifiers()

        if keycode == ord('C') and modifiers == wx.MOD_CONTROL:
            self.onCopyLinkFromMenu(event)
        elif keycode == wx.WXK_ESCAPE:
           self.Close()
        elif keycode == wx.WXK_RETURN and event.ControlDown():
            self.onPlay(event, play_as_audio=True)
        else:
           event.Skip()

    def onShow(self, event):
        if self.parent:
           self.parent.Hide()
        event.Skip()

    def onContextMenu(self, event):
        if self.context_menu:
            self.context_menu.Destroy()
        self.context_menu = wx.Menu()
        play_menu = wx.Menu()
        play_low_item = wx.MenuItem(play_menu, wx.ID_ANY, "Low Quality")
        play_medium_item = wx.MenuItem(play_menu, wx.ID_ANY, "Medium Quality")
        play_best_item = wx.MenuItem(play_menu, wx.ID_ANY, "Best Quality")
        play_menu.Append(play_low_item)
        play_menu.Append(play_medium_item)
        play_menu.Append(play_best_item)
        self.Bind(wx.EVT_MENU, lambda e: self.onPlayQuality(e, "low"), play_low_item)
        self.Bind(wx.EVT_MENU, lambda e: self.onPlayQuality(e, "medium"), play_medium_item)
        self.Bind(wx.EVT_MENU, lambda e: self.onPlayQuality(e, "best"), play_best_item)
        play_parent_item = wx.MenuItem(self.context_menu, wx.ID_ANY, "Play")
        self.context_menu.AppendSubMenu(play_menu, "Play")

        copy_item = wx.MenuItem(self.context_menu, wx.ID_ANY, "Copy Video Link")
        self.context_menu.Append(copy_item)
        self.Bind(wx.EVT_MENU, self.onCopyLinkFromMenu, copy_item)

        download_item = wx.MenuItem(self.context_menu, wx.ID_ANY, "Download video...")
        self.context_menu.Append(download_item)
        self.Bind(wx.EVT_MENU, self.onDownloadSelectedVideo, download_item)

        direct_download_item = wx.MenuItem(self.context_menu, wx.ID_ANY, "Direct Download")
        self.context_menu.Append(direct_download_item)
        self.Bind(wx.EVT_MENU, self.onDirectDownload, direct_download_item)

        show_description_item = wx.MenuItem(self.context_menu, wx.ID_ANY, "Video description")
        self.context_menu.Append(show_description_item)
        self.Bind(wx.EVT_MENU, self.onShowDescription, show_description_item) # Bind to new handler

        self.PopupMenu(self.context_menu, event.GetPosition())

    def onCopyLinkFromMenu(self, event):
        selection = self.results_listbox.GetSelection()
        if selection != -1:
            selected_video = self.results[selection]
            self.copy_to_clipboard(selected_video['link'])
        else:
            wx.MessageBox("Please select a video first", "Error", wx.OK | wx.ICON_INFORMATION)

    def copy_to_clipboard(self, text):
        clipboard = wx.Clipboard.Get()
        if clipboard.Open():
            text_data = wx.TextDataObject()
            text_data.SetText(text)

            # Check if SetDataObject is available, if not use SetData
            if hasattr(clipboard, 'SetDataObject'):
                clipboard.SetDataObject(text_data)
            else:
                clipboard.SetData(text_data)
            clipboard.Close()
            speak("Link copyed to clipboard", interrupt=True)
        else:
            wx.MessageBox("Could not access clipboard.", "Error", wx.OK | wx.ICON_ERROR)

    def onShowDescription(self, event):
        selection = self.results_listbox.GetSelection()
        if selection != -1:
            selected_video = self.results[selection]
            video_url = selected_video['link']
            video_title = selected_video['title'] # Get title for loading message

            self.show_loading_dialog(f"Fetching description for: {video_title}")
            threading.Thread(target=self.fetch_description_thread, args=(video_url,)).start()
        else:
            wx.MessageBox("Please select a video to view its description.", "Error", wx.OK | wx.ICON_INFORMATION)

    def fetch_description_thread(self, video_url):
        """Worker thread to fetch video description using yt-dlp."""
        description = None
        error_message = None
        try:
            info_dict = run_yt_dlp_json(video_url)

            if info_dict:
                description = info_dict.get('description', 'No description available.')
            else:
                 error_message = "Failed to fetch video information."

        except FileNotFoundError:
             error_message = "Error: yt-dlp.exe not found. Cannot fetch description."
        except Exception as e:
            error_message = f"Error fetching description: {e}"
            print(f"Error fetching description for {video_url}: {e}")
        wx.PostEvent(self, DescriptionFetchEvent(description=description, error=error_message))

    def onDescriptionFetchComplete(self, event):
        """Handles the completion of the description fetching thread."""
        self.destroy_loading_dialog()

        description = event.description
        error_message = event.error

        if error_message:
            wx.MessageBox(error_message, "Error Fetching Description", wx.OK | wx.ICON_ERROR)
        elif description is not None:
            desc_dlg = DescriptionDialog(self, "Video description", description)
            desc_dlg.ShowModal()
            desc_dlg.Destroy()
        else:
             wx.MessageBox("Description not available for this video.", "Description Unavailable", wx.OK | wx.ICON_INFORMATION)

    def onDownloadSelectedVideo(self, event):
        selection = self.results_listbox.GetSelection()
        if selection != -1:
            selected_video = self.results[selection]
            video_url = selected_video['link']
            video_title = selected_video['title']

            settings_dialog = DownloadSettingsDialog(self, "Download Settings", video_title, video_url)
            if settings_dialog.ShowModal() == wx.ID_OK:
                download_settings = settings_dialog.settings
                self.start_download_process(download_settings)
            settings_dialog.Destroy()
        else:
            wx.MessageBox("Please select a video to download.", "Error", wx.OK | wx.ICON_INFORMATION)

    def onDirectDownload(self, event):
        selection = self.results_listbox.GetSelection()
        if selection != -1:
            selected_video = self.results[selection]
            video_url = selected_video['link']
            video_title = selected_video['title']

            youtube_settings = self.config.get('YouTube', {})
            default_type = youtube_settings.get('default_download_type', 'Video')
            default_video_quality = youtube_settings.get('default_video_quality', 'Medium')
            default_audio_format = youtube_settings.get('default_audio_format', 'mp3')
            default_audio_quality = youtube_settings.get('default_audio_quality', '128K')
            default_directory = youtube_settings.get('default_download_directory', '')

            # Validate default directory
            if not default_directory or not os.path.isdir(default_directory):
                wx.MessageBox("Default download directory is not set or invalid. Please configure it in Settings.", "Direct Download Failed", wx.OK | wx.ICON_WARNING)
                return

            download_settings = {
                'url': video_url,
                'filename': video_title,
                'directory': default_directory,
                'type': default_type,
                'video_quality': default_video_quality,
                'audio_format': default_audio_format,
                'audio_quality': default_audio_quality,
            }
            self.start_download_process(download_settings)
        else:
            wx.MessageBox("Please select a video to download.", "Error", wx.OK | wx.ICON_INFORMATION)

    def start_download_process(self, download_settings):
        """Starts the DownloadDialog with the collected settings."""
        dlg_title = f"Downloading: {download_settings['filename']}"
        download_dlg = DownloadDialog(self, dlg_title, download_settings)
        download_dlg.download_task()


    def onClose(self, event):
        if self.parent:
            wx.CallAfter(self.parent.Show)
        self.Destroy()
