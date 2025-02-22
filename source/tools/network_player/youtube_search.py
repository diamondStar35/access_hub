import wx
from tools.network_player.youtube_player import YoutubePlayer, EVT_VLC_READY
from tools.network_player.download_dialog import DownloadDialog
from youtubesearchpython import VideosSearch
from speech import speak
import yt_dlp
import threading
from wx.lib.newevent import NewEvent
import os

# Event for search completion
YoutubeSearchEvent, EVT_YOUTUBE_SEARCH = NewEvent()

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
        download_button.Bind(wx.EVT_BUTTON, self.onDownloadVideo)
        vbox.Add(download_button, 0, wx.ALL | wx.ALIGN_RIGHT, 5)

        panel.SetSizer(vbox)
        self.results = []
        self.populate_results_listbox(results['result'])
        self.Bind(wx.EVT_SHOW, self.onShow)
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Bind(wx.EVT_CHAR_HOOK, self.onKey)
        self.results_listbox.Bind(wx.EVT_CONTEXT_MENU, self.onContextMenu)
        self.results_listbox.Bind(wx.EVT_LISTBOX, self.onListBox)


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
            ydl_opts = {
                'quiet': True,
                'noplaylist': True,
            }

            if quality == "low":
                ydl_opts['format'] = 'worst[height<=480]'
            elif quality == "medium":
                ydl_opts['format'] = 'best[height<=720]'
            elif quality == "best":
                ydl_opts['format'] = 'best[ext=mp4]/best'

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                media_url = info_dict.get('url', None)
                if not media_url:
                    raise ValueError(f"No playable URL found for {quality} quality.")

                wx.CallAfter(self.create_and_show_player, title, media_url, info_dict['description'], url)
        except Exception as e:
            wx.CallAfter(self.destroy_loading_dialog)
            wx.CallAfter(wx.MessageBox, f"Could not play: {e}", "Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Show)

    def onPlay(self, event, play_as_audio=False):
        selection = self.results_listbox.GetSelection()
        if selection != -1:
            selected_video = self.results[selection]
            threading.Thread(target=self.get_direct_link_and_play, args=(selected_video['link'], selected_video['title'], play_as_audio)).start()

    def get_direct_link_and_play(self, url, title, play_as_audio):
        try:
            if play_as_audio:
                wx.CallAfter(self.show_loading_dialog, title, True)
            else:
                wx.CallAfter(self.show_loading_dialog, title)
            wx.CallAfter(self.Hide)
            ydl_opts = {
                'format': 'bestaudio/best' if play_as_audio else 'best[ext=mp4]/best',
                'quiet': True,
                'noplaylist': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                media_url = info_dict.get('url', None)
                if not media_url:
                    raise ValueError("No playable video URL found.")

                wx.CallAfter(self.create_and_show_player, title, media_url, info_dict['description'], url)
        except Exception as e:
            wx.CallAfter(self.destroy_loading_dialog)
            wx.CallAfter(wx.MessageBox, f"Could not play video: {e}", "Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Show)

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

        download_menu = wx.Menu()
        download_video_item = wx.MenuItem(download_menu, wx.ID_ANY, "Video")
        download_menu.Append(download_video_item)
        self.Bind(wx.EVT_MENU, self.onDownloadVideo, download_video_item)

        download_audio_item = wx.MenuItem(download_menu, wx.ID_ANY, "Audio")
        download_menu.Append(download_audio_item)
        self.Bind(wx.EVT_MENU, self.onDownloadAudioFromMenu, download_audio_item)
        download_parent_item = wx.MenuItem(self.context_menu, wx.ID_ANY, "Download")
        self.context_menu.AppendSubMenu(download_menu, "Download") # Appending the submenu
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

    def onDownloadVideo(self, event):
        selection = self.results_listbox.GetSelection()
        if selection != -1:
            selected_video = self.results[selection]
            self.download(selected_video['link'],selected_video['title'], is_audio=False)
        else:
            wx.MessageBox("Please select a video to download.", "Error", wx.OK | wx.ICON_INFORMATION)

    def onDownloadAudioFromMenu(self, event):
        selection = self.results_listbox.GetSelection()
        if selection != -1:
            selected_video = self.results[selection]
            self.download(selected_video['link'], selected_video['title'],is_audio=True)
        else:
            wx.MessageBox("Please select a video to download.", "Error", wx.OK | wx.ICON_INFORMATION)

    def download(self, url, title, is_audio=False):
        try:
           with wx.DirDialog(self, "Choose download directory", style=wx.DD_DEFAULT_STYLE) as dialog:
               if dialog.ShowModal() == wx.ID_OK:
                    download_path = dialog.GetPath()
                    download_dlg = DownloadDialog(self, f"Downloading: {title}", is_audio)
                    download_dlg.download_task(url, title, download_path)
               else:
                   return
        except Exception as e:
             wx.MessageBox(f"Could not start download: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def onClose(self, event):
        if self.parent:
            self.parent.Show()
        self.Destroy()
