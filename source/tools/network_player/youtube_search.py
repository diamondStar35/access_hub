import wx
from .youtube_player import YoutubePlayer, EVT_VLC_READY
from .download_dialogs import DownloadSettingsDialog, DownloadDialog
from .favorites_manager import FavoritesManager
from .channel_viewer import ChannelViewerFrame
from .utils import run_yt_dlp_json
from gui.settings import get_file_path
from gui.custom_controls import CustomTextCtrl
from speech import speak
from configobj import ConfigObj
from gui.dialogs import DescriptionDialog
import app_vars
from wx.lib.newevent import NewEvent
import os, json, threading

# Events for search completion and description
YoutubeSearchEvent, EVT_YOUTUBE_SEARCH = NewEvent()
DescriptionFetchEvent, EVT_DESCRIPTION_FETCH = NewEvent()
PlaylistItemsFetchEvent, EVT_PLAYLIST_ITEMS_FETCH = NewEvent()
ChannelDataFetchEvent, EVT_CHANNEL_DATA_FETCH = NewEvent()


class YoutubeSearchDialog(wx.Dialog):
    def __init__(self, parent, network_player_frame):
        super().__init__(parent, title="YouTube Search", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame_to_manage = network_player_frame
        self.history_path = get_file_path("search_history.json")
        self._history = self.load_history()

        self.SetSize((500, 350))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        search_label = wx.StaticText(panel, label="Search:")
        vbox.Add(search_label, 0, wx.ALL, 5)

        self.search_text = CustomTextCtrl(panel, style=wx.TE_PROCESS_ENTER, history=self._history)
        self.search_text.Bind(wx.EVT_TEXT_ENTER, self.onSearch)
        vbox.Add(self.search_text, 1, wx.ALL | wx.EXPAND, 5)

        search_button = wx.Button(panel, label="Search")
        search_button.Bind(wx.EVT_BUTTON, self.onSearch)
        search_button.SetDefault()
        vbox.Add(search_button, 0, wx.ALL | wx.ALIGN_RIGHT, 5)

        panel.SetSizer(vbox)
        self.Centre()

    def load_history(self):
        """Loads search history from a JSON file."""
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    if isinstance(history, list):
                        return history
                    else:
                        return []
            except (IOError, json.JSONDecodeError) as e:
                return []
        else:
            return []

    def save_history(self):
        """Saves the current search history to a JSON file."""
        history_to_save = self.search_text.GetHistory()
        history_to_save = history_to_save[:50]

        try:
            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(history_to_save, f, indent=4)
        except (IOError, OSError) as e:
            pass

    def onSearch(self, event):
        search_term = self.search_text.GetValue().strip()
        if not search_term: # Don't search if textbox is empty.
            return

        self.search_text.AddHistory(search_term)
        self.save_history()
        self.loading_dialog = wx.Dialog(self, title="Searching...", style=wx.CAPTION)
        loading_text = wx.StaticText(self.loading_dialog, -1, "Searching...")
        loading_sizer = wx.BoxSizer(wx.VERTICAL)
        loading_sizer.Add(loading_text, 0, wx.ALL | wx.CENTER, 10)
        self.loading_dialog.SetSizer(loading_sizer)
        self.loading_dialog.Show()
        wx.Yield()

        threading.Thread(target=self.search_youtube, args=(search_term,)).start()
        self.Bind(EVT_YOUTUBE_SEARCH, self.onSearchResults)

    def search_youtube(self, search_term):
        """Performs YouTube search using yt-dlp."""
        results_list = []
        config_path = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name, "settings.ini")
        config = ConfigObj(config_path)
        youtube_settings = config.get('YouTube', {})
        search_results_count_str = youtube_settings.get('search_results_count', "5")

        search_query_url = ""
        if search_results_count_str.lower() == "automatic":
            search_query_url = f"ytsearchall:{search_term}"
        else:
            try:
                num_results = int(search_results_count_str)
                search_query_url = f"ytsearch{num_results}:{search_term}"
            except ValueError:
                search_query_url = f"ytsearch5:{search_term}"
                
        try:
            info_dict = run_yt_dlp_json(search_query_url, is_search=True)             
            if info_dict and 'entries' in info_dict:
                results_list = info_dict['entries']
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"An unexpected error occurred while initiating the search: {e}", "Search Error", wx.OK | wx.ICON_ERROR)
        
        wx.PostEvent(self, YoutubeSearchEvent(results=results_list, search_instance=None))

    def onSearchResults(self, event):
        results = event.results        
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            try:
                self.loading_dialog.Destroy()
            except RuntimeError: pass # It might have been destroyed
            self.loading_dialog = None

        if results:
            if self.frame_to_manage:
                try:
                    self.frame_to_manage.Hide()
                except (wx.wxAssertionError, RuntimeError): pass

            if self.frame_to_manage:
                if hasattr(self.frame_to_manage, 'access_hub_instance'):
                    wx_parent_for_results = self.frame_to_manage.access_hub_instance
                else: # Fallback to NPF's direct parent
                    wx_parent_for_results = self.frame_to_manage.GetParent()
            if not wx_parent_for_results:
                 wx_parent_for_results = wx.GetApp().GetTopWindow()

            youtube_results_frame = YoutubeSearchResults(wx_parent_for_results, results, is_playlist_view=False, calling_frame_to_show_on_my_close=self.frame_to_manage)
            # Add to AccessHub's child tracking if AccessHub is the parent or known
            access_hub_ref = None
            if isinstance(wx_parent_for_results, wx.Frame) and hasattr(wx_parent_for_results, 'add_child_frame'):
                access_hub_ref = wx_parent_for_results
            elif self.frame_to_manage and hasattr(self.frame_to_manage, 'access_hub_instance'):
                access_hub_ref = self.frame_to_manage.access_hub_instance

            if access_hub_ref and hasattr(access_hub_ref, 'add_child_frame'):
                access_hub_ref.add_child_frame(youtube_results_frame)
            youtube_results_frame.Show()
        else:
            wx.MessageBox("No results found or error fetching results.", "YouTube Search", wx.OK | wx.ICON_INFORMATION)        
        self.Destroy()


class YoutubeSearchResults(wx.Frame):
    def __init__(self, parent, results_list, is_playlist_view=False, calling_frame_to_show_on_my_close=None, playlist_uploader=None):
        self.is_playlist_view = is_playlist_view
        self.playlist_uploader = playlist_uploader
        title = "Playlist Viewer" if is_playlist_view else "Search Results"
        super().__init__(parent, title=title, size=(800, 650), style=wx.DEFAULT_DIALOG_STYLE| wx.RESIZE_BORDER)
        self.calling_frame_to_show_on_my_close = calling_frame_to_show_on_my_close
        self.player=None
        self.parent_for_sub_frames = parent
        self.favorites_manager = FavoritesManager()
        self.context_menu=None
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.ffmpeg_path = os.path.join(project_root, 'ffmpeg.exe')
        self.load_settings()

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        label_text = "Playlist Items:" if is_playlist_view else "Search Results:"
        self.results_label = wx.StaticText(panel, -1, label_text)
        vbox.Add(self.results_label, 0, wx.ALL, 5)

        self.results_listbox = wx.ListBox(panel)
        vbox.Add(self.results_listbox, 1, wx.ALL | wx.EXPAND, 5)

        play_button = wx.Button(panel, label="Play")
        play_button.Bind(wx.EVT_BUTTON, lambda event: self.onPlayOrOpenPlaylist(event, item_info=self.get_selected_item_info_from_listbox(), calling_frame_to_hide_override=self))
        vbox.Add(play_button, 0, wx.ALL | wx.ALIGN_RIGHT, 5)

        download_button = wx.Button(panel, label="Download")
        download_button.Bind(wx.EVT_BUTTON, self.onDownloadSelectedVideo)
        vbox.Add(download_button, 0, wx.ALL | wx.ALIGN_RIGHT, 5)

        panel.SetSizer(vbox)
        self.results = []
        self.populate_results_listbox(results_list)
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Bind(wx.EVT_CHAR_HOOK, self.onKey)
        self.results_listbox.Bind(wx.EVT_CONTEXT_MENU, self.onContextMenu)
        self.results_listbox.Bind(wx.EVT_LISTBOX_DCLICK, lambda event: self.onPlayOrOpenPlaylist(event, item_info=self.get_selected_item_info_from_listbox()))
        self.Bind(EVT_DESCRIPTION_FETCH, self.onDescriptionFetchComplete)
        self.Bind(EVT_PLAYLIST_ITEMS_FETCH, self.onPlaylistItemsFetched)
        self.Bind(EVT_CHANNEL_DATA_FETCH, self.onChannelDataFetched)
        self.Centre()


    def is_item_playlist(self, item_data):
        """
        Checks if the given yt-dlp item data represents a playlist and returns its status and count.
        Returns:
            dict: {'is_playlist': bool, 'count': int or None}
        """
        if isinstance(item_data, dict):
            item_type = item_data.get('_type')
            ie_key = item_data.get('ie_key', '').lower()
            if item_type == 'playlist' or item_type == 'playlist_result':
                return {'is_playlist': True, 'count': item_data.get('playlist_count')}
            if 'playlist' in ie_key: # Covers cases like 'youtube:playlist'
                return {'is_playlist': True, 'count': item_data.get('playlist_count')}
        return {'is_playlist': False, 'count': None}

    def is_item_channel(self, item_data):
        """Checks if the given yt-dlp item data represents a channel from search results."""
        if isinstance(item_data, dict):
            if item_data.get('_type') == 'channel':
                return True
            ie_key = item_data.get('ie_key', '')
            if 'YoutubeTab' in ie_key and 'playlist' not in ie_key:
                return True
        return False

    def populate_results_listbox(self, results): #Corrected the loop and result appending.
        self.results_listbox.Clear()
        self.results = []
        for result_item in results:
            title = result_item.get('title', 'Untitled Video')
            webpage_url = result_item.get('url')
            uploader = 'Unknown Uploader'
            if self.is_playlist_view and self.playlist_uploader:
                uploader = self.playlist_uploader
            else:
                uploader = result_item.get('channel') or result_item.get('uploader', 'Unknown Uploader')

            duration_seconds = result_item.get('duration')
            playlist_info = self.is_item_playlist(result_item)
            is_playlist = playlist_info['is_playlist']
            playlist_item_count = playlist_info['count']
            is_channel = self.is_item_channel(result_item)

            item_text = ""
            item_type_for_fav = 'unknown'
            if is_channel:
                item_text = f"{title}: Channel"
                item_type_for_fav = 'channel'
            elif is_playlist:
                if playlist_item_count is not None:
                    item_text = f"{title}: A playlist containing {playlist_item_count} videos (by {uploader})"
                else:
                    item_text = f"{title}: Playlist (by {uploader})"
                item_type_for_fav = 'playlist'
            else:
                duration_display = self.format_duration(duration_seconds)
                item_text = f"{title} , Duration: {duration_display}, By: {uploader}"            
                item_type_for_fav = 'video'
            self.results_listbox.Append(item_text)
            results_info = {
                'title': title,
                'webpage_url': webpage_url,
                'duration': duration_seconds,
                'uploader': uploader,
                'is_playlist': is_playlist,
                'playlist_count': playlist_item_count,
                'is_channel': is_channel,
                'type': item_type_for_fav,
                '_original_item_data': result_item
            }
            self.results.append(results_info)

    def load_settings(self):
        """Loads settings from the config file."""
        config_path = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name, "settings.ini")
        self.config = ConfigObj(config_path)
        youtube_settings = self.config.get('YouTube', {})
        self.default_quality = youtube_settings.get('video_quality', 'Medium')

    def get_selected_item_info_from_listbox(self):
        """Helper to get the full info dict for the selected listbox item."""
        selection = self.results_listbox.GetSelection()
        if selection != -1 and selection < len(self.results):
            return self.results[selection]
        return None

    def format_duration(self, total_seconds_num):
        """Formats duration from seconds to HH:MM:SS or MM:SS string."""
        if total_seconds_num is None:
            return "Unknown"
        try:
            seconds_int = int(total_seconds_num)
            hours, remainder = divmod(seconds_int, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except (ValueError, TypeError):
            return str(total_seconds_num)

    def onPlayOrOpenPlaylist(self, event, item_info=None, calling_frame_to_hide_override=None):
        """Handles playing a video, opening a playlist, or opening a channel."""
        if not item_info:
            item_info = self.get_selected_item_info_from_listbox()
        if not item_info:
            if event: event.Skip()
            return

        # frame_to_hide is the frame that should be hidden when launching the new view.
        # This is typically 'self' (the current YSR instance) unless overridden
        frame_to_hide = calling_frame_to_hide_override if calling_frame_to_hide_override else self        
        action_taken = False
        if item_info.get('is_channel'):
            channel_url = item_info.get('webpage_url')
            channel_title = item_info.get('title', 'Untitled Channel')
            if channel_url:
                try: frame_to_hide.Hide()
                except (wx.wxAssertionError, RuntimeError): pass
                self.show_loading_dialog(f"Getting channel info for: {channel_title}", "Loading Channel...")
                threading.Thread(target=self.fetch_channel_data_thread, args=(channel_url, frame_to_hide)).start()
                action_taken = True
            else:
                wx.MessageBox("Channel link is missing or not found.", "Error", wx.OK | wx.ICON_ERROR)
        elif item_info.get('is_playlist'):
            playlist_url = item_info.get('webpage_url')
            playlist_title = item_info.get('title', 'Untitled Playlist')
            current_playlist_uploader = item_info.get('uploader')
            if playlist_url:
                try: frame_to_hide.Hide()
                except (wx.wxAssertionError, RuntimeError): pass
                self.show_loading_dialog(f"Getting playlist info for: {playlist_title}", "Loading Playlist...")
                threading.Thread(target=self.fetch_playlist_items_thread, args=(playlist_url, current_playlist_uploader, frame_to_hide)).start()
                action_taken = True
            else:
                wx.MessageBox("Playlist link is missing or not found.", "Error", wx.OK | wx.ICON_ERROR)
        else:
            self.onPlay(event, item_info=item_info, play_as_audio=False, frame_that_should_be_hidden_and_reactivated=frame_to_hide)
            action_taken = True

        if not action_taken and frame_to_hide != self: # If error and called by other, show caller back
            try: frame_to_hide.Show()
            except (wx.wxAssertionError, RuntimeError): pass
        elif not action_taken and frame_to_hide == self:
            self.Show()
        if event: event.Skip()
    
    def fetch_playlist_items_thread(self, playlist_url, playlist_uploader=None, frame_to_activate=None):
        """Worker thread to fetch playlist items using yt-dlp."""
        playlist_items = []
        error_message = None
        try:
            info_dict = run_yt_dlp_json(playlist_url, is_search=True)
            if info_dict and 'entries' in info_dict:
                playlist_items = info_dict['entries']
            elif info_dict:
                error_message = "Failed to fetch playlist items: Unexpected data structure."
            
        except Exception as e:
            error_message = f"Error fetching playlist items: {e}"
        wx.PostEvent(self, PlaylistItemsFetchEvent(items=playlist_items, error=error_message, playlist_uploader=playlist_uploader, originating_frame_to_reactivate=frame_to_reactivate))

    def onPlaylistItemsFetched(self, event):
        """Handles the completion of playlist item fetching."""
        self.destroy_loading_dialog()
        items = event.items
        error = event.error
        playlist_uploader = event.playlist_uploader
        originating_frame_to_reactivate = event.originating_frame_to_reactivate

        if error:
            wx.MessageBox(error, "Playlist Error", wx.OK | wx.ICON_ERROR)
            if originating_frame_to_reactivate:
                try: originating_frame_to_reactivate.Show()
                except (wx.wxAssertionError, RuntimeError): pass
        elif items:
            # originating_frame_to_reactivate remains hidden.
            # New YSR (playlist view) will show originating_frame_to_reactivate on its close.
            wx_parent_playlist_view = originating_frame_to_reactivate.GetParent() if originating_frame_to_reactivate else self.parent_for_sub_frames
            playlist_viewer_frame = YoutubeSearchResults(wx_parent_playlist_view, items, is_playlist_view=True,calling_frame_to_show_on_my_close=originating_frame_to_reactivate, playlist_uploader=playlist_uploader)
            top_level_parent = wx.GetApp().GetTopWindow()
            if hasattr(top_level_parent, 'add_child_frame'):
                top_level_parent.add_child_frame(playlist_viewer_frame)
            playlist_viewer_frame.Show()
        else:
            wx.MessageBox("No items found in the playlist or an error occurred.", "Playlist Empty", wx.OK | wx.ICON_INFORMATION)
            if originating_frame_to_reactivate:
                try: originating_frame_to_reactivate.Show()
                except (wx.wxAssertionError, RuntimeError): pass

    def fetch_channel_data_thread(self, channel_url, frame_to_activate):
        """Worker thread to fetch channel data."""
        channel_data = None
        error_message = None
        try:
            info_dict = run_yt_dlp_json(channel_url, extra_args=['--no-playlist'], is_search=True)
            if info_dict:
                channel_data = info_dict
            else:
                error_message = "Failed to fetch channel data: No information returned."
        except Exception as e:
            error_message = f"Error getting channel data: {e}"
        wx.PostEvent(self, ChannelDataFetchEvent(data=channel_data, error=error_message, originating_frame_to_reactivate=frame_to_reactivate))

    def onChannelDataFetched(self, event):
        """Handles the completion of channel data fetching."""
        self.destroy_loading_dialog()
        channel_data = event.data
        error = event.error
        originating_frame_to_reactivate = event.originating_frame_to_reactivate

        if error:
            wx.MessageBox(error, "Channel Error", wx.OK | wx.ICON_ERROR)
            if originating_frame_to_reactivate:
                try: originating_frame_to_reactivate.Show()
                except (wx.wxAssertionError, RuntimeError): pass
        elif channel_data:
            wx_parent_cvf = originating_frame_to_reactivate.GetParent() if originating_frame_to_reactivate else self.parent_for_sub_frames
            channel_viewer_frame = ChannelViewerFrame(wx_parent_cvf, channel_data, calling_frame_to_show_on_my_close=originating_frame_to_reactivate)
            top_level_parent = wx.GetApp().GetTopWindow()
            if hasattr(top_level_parent, 'add_child_frame'):
                top_level_parent.add_child_frame(channel_viewer_frame)
            channel_viewer_frame.Show()
        else:
            wx.MessageBox("No data found for the channel or an error occurred.", "Channel Error", wx.OK | wx.ICON_INFORMATION)
            if originating_frame_to_reactivate:
                try: originating_frame_to_reactivate.Show()
                except (wx.wxAssertionError, RuntimeError): pass

    def onPlayQuality(self, event, quality, item_info=None):
        if not item_info:
            item_info = self.get_selected_item_info_from_listbox()
        if not item_info:
            wx.MessageBox("Please select a video.", "No selection", wx.OK | wx.ICON_ERROR, self)
            return

        if item_info.get('is_playlist') or item_info.get('is_channel'):
            wx.MessageBox("Cannot play a playlist or channel directly with quality selection. Please open it first.", "Info", wx.OK | wx.ICON_INFORMATION, self)
            return

        video_url = item_info.get('webpage_url')
        video_title = item_info.get('title', 'Untitled')
        if not video_url:
            wx.MessageBox("The video link was not found for this item.", "Playback Error", wx.OK | wx.ICON_ERROR, self)
            return

        threading.Thread(target=self.get_direct_link_and_play_with_quality, args=(video_url, video_title, quality, item_info)).start()
        if event: event.Skip()

    def get_direct_link_and_play_with_quality(self, url, title, quality, item_info_for_player_context):
        try:
            wx.CallAfter(self.show_loading_dialog, f"Playing: {video_title}", "Playing video...")
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
                formats = info_dict.get('formats', [])
                if formats:
                    media_url = formats[0].get('url') # Assume the first format is the chosen one

            if not media_url:
                raise ValueError("No playable URL found in yt-dlp output.")

            selected_idx = -1
            try:
                selected_idx = self.results.index(item_info_for_player_context)
            except ValueError:
                selected_idx = self.results_listbox.GetSelection()

            wx.CallAfter(self.create_and_show_player, title, media_url, description, url)
        except Exception as e:
            wx.CallAfter(self.destroy_loading_dialog)
            wx.CallAfter(wx.MessageBox, f"Could not play: {e}", "Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Show) # Show the results window again on failure

    def onPlay(self, event, play_as_audio=False, item_info=None, frame_that_should_be_hidden_and_reactivated=None):
        if not item_info: # If called directly, e.g. from context menu
            item_info = self.get_selected_item_info_from_listbox()
            if not frame_that_should_be_hidden_and_reactivated: # If not specified, 'self' is the frame
                frame_that_should_be_hidden_and_reactivated = self
        
        if not item_info:
            wx.MessageBox("Please select an item to play.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            if frame_that_should_be_hidden_and_reactivated:
                 try: frame_that_should_be_hidden_and_reactivated.Show()
                 except (wx.wxAssertionError, RuntimeError): pass
            return

        if item_info.get('is_playlist') or item_info.get('is_channel'):
            self.onPlayOrOpenPlaylist(event, item_info=item_info, calling_frame_to_hide_override=frame_that_should_be_hidden_and_reactivated)
            return

        video_url = item_info.get('webpage_url')
        video_title = item_info.get('title', 'Untitled')
        if not video_url:
            wx.MessageBox("The video link was not found for this item.", "Playback Error", wx.OK | wx.ICON_ERROR)
            if frame_that_should_be_hidden_and_reactivated:
                 try: frame_that_should_be_hidden_and_reactivated.Show()
                 except (wx.wxAssertionError, RuntimeError): pass
            return

        if frame_that_should_be_hidden_and_reactivated:
            try:
                frame_that_should_be_hidden_and_reactivated.Hide()
            except (wx.wxAssertionError, RuntimeError): pass

        format_selector = 'ba/b' if play_as_audio else self.get_video_format_selector_for_play()
        threading.Thread(target=self.get_direct_link_and_play, args=(video_url, video_title, format_selector, item_info, frame_that_should_be_hidden_and_reactivated, play_as_audio)).start()
        if event: event.Skip()

    def get_video_format_selector_for_play(self):
        quality = self.default_quality
        if quality == "Low": return 'worst[ext=mp4]/worstvideo[ext=mp4]/worst'
        elif quality == "Medium": return 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'
        elif quality == "Best": return 'best[ext=mp4]/bestvideo[ext=mp4]/best'
        return 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'

    def get_direct_link_and_play(self, url, title, format_selector, item_info_for_player_context, frame_to_reactivate_on_player_close, play_as_audio):
        try:
            dialog_title = "Playing audio..." if play_as_audio else "Playing video..."
            wx.CallAfter(self.show_loading_dialog, f"Playing: {title}", dialog_title)

            info_dict = run_yt_dlp_json(url, format_selector=format_selector)
            if not info_dict:
                raise ValueError("Failed to get video info from yt-dlp.")

            media_url = info_dict.get('url')
            description = info_dict.get('description', '')

            if not media_url:
                formats = info_dict.get('formats', [])
                if formats:
                    media_url = formats[0].get('url')
            if not media_url:
                raise ValueError("No playable URL found in yt-dlp output.")

            selected_idx = -1
            try:
                selected_idx = self.results.index(item_info_for_player_context)
            except ValueError:
                # Fallback if not found, though it should be.
                selected_idx = self.results_listbox.GetSelection()
            wx.CallAfter(self.create_and_show_player, title, media_url, description, url, self.results, selected_idx, frame_to_reactivate_on_player_close)

        except Exception as e:
            wx.CallAfter(self.destroy_loading_dialog)
            wx.CallAfter(wx.MessageBox, f"Could not play video: {e}", "Error", wx.OK | wx.ICON_ERROR)
            if frame_to_reactivate_on_player_close:
                try: frame_to_reactivate_on_player_close.Show()
                except (wx.wxAssertionError, RuntimeError): pass

    def create_and_show_player(self, title, url, description, original_youtube_link, results_for_player_nav, current_index_in_nav_list, frame_to_reactivate_on_player_close):
        self.player = YoutubePlayer(None, title, url, frame_to_reactivate_on_player_close, description, original_youtube_link, results_for_player_nav, current_index_in_nav_list)
        self.player.Bind(EVT_VLC_READY, self.show_when_ready)

    def show_when_ready(self, event):
        self.destroy_loading_dialog()
        self.player.Show()
        event.Skip()

    def show_loading_dialog(self, message_content, dialog_title_override=None):
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            try:
                self.loading_dialog.Destroy()
            except RuntimeError: # It might have been destroyed
                pass
            self.loading_dialog = None

        actual_dialog_title = dialog_title_override if dialog_title_override else "Loading..." # Default title
        self.loading_dialog = wx.Dialog(self, title=actual_dialog_title, style=wx.CAPTION)
        loading_text = wx.StaticText(self.loading_dialog, -1, message_content)
        loading_sizer = wx.BoxSizer(wx.VERTICAL)
        loading_sizer.Add(loading_text, 0, wx.ALL | wx.CENTER, 10)
        self.loading_dialog.SetSizer(loading_sizer)
        self.loading_dialog.CentreOnParent()
        self.loading_dialog.Show()
        wx.Yield() # Process events to show dialog

    def destroy_loading_dialog(self, event=None):
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            self.loading_dialog.Destroy()
            self.loading_dialog=None
        if event:
            event.Skip()

    def onKey(self, event):
        keycode = event.GetKeyCode()
        modifiers = event.GetModifiers()
        selected_item = self.get_selected_item_info_from_listbox()
        if not selected_item:
            event.Skip()
            return
        if not self.IsShown():
            event.Skip() # Don't process keys if the frame is not visible
            return

        if keycode == ord('C') and modifiers == wx.MOD_CONTROL:
            self.onCopyLinkFromMenu(event, item_info=selected_item)
        elif keycode == wx.WXK_SPACE:
             self.onToggleFavorite(event)
        elif keycode == wx.WXK_ESCAPE:
           self.Close()
        elif keycode == wx.WXK_RETURN:
            if modifiers == wx.MOD_CONTROL:
                if selected_item.get('is_playlist') or selected_item.get('is_channel'):
                     wx.MessageBox("Cannot play playlists or channels as audio directly. Please open them first.", "Info", wx.OK|wx.ICON_INFORMATION)
                else:
                    self.onPlay(event, play_as_audio=True, item_info=selected_item)
            else:
                self.onPlayOrOpenPlaylist(event, item_info=selected_item)
        else:
           event.Skip()

    def onToggleFavorite(self, event, item_info=None):
        """Adds or removes the selected item from favorites."""
        if item_info is not None:
            current_item_info=item_info
        else:
            current_item_info = self.get_selected_item_info_from_listbox()
        if not current_item_info:
            wx.MessageBox("Please select an item first.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return
        
        fav_entry_info = {
            'title': current_item_info.get('title'),
            'webpage_url': current_item_info.get('webpage_url'),
            'type': current_item_info.get('type'),
            'description': current_item_info.get('_original_item_data', {}).get('description')
        }
        
        if not fav_entry_info.get('webpage_url'):
            wx.MessageBox("Cannot add to favorites: The selected item has no link.", "Error", wx.OK | wx.ICON_ERROR)
            return
            
        is_added, message = self.favorites_manager.toggle_favorite(fav_entry_info)
        speak(message)        
        if event: event.Skip()

    def onContextMenu(self, event):
        selected_item_info = self.get_selected_item_info_from_listbox()
        if not selected_item_info:
            return

        is_playlist_item = selected_item_info.get('is_playlist', False)
        is_channel_item = selected_item_info.get('is_channel', False)

        if self.context_menu:
            self.context_menu.Destroy()
        self.context_menu = wx.Menu()
        if is_channel_item:
            open_channel_item = self.context_menu.Append(wx.ID_ANY, "Open Channel")
            self.Bind(wx.EVT_MENU, lambda e: self.onPlayOrOpenPlaylist(e, item_info=selected_item_info), open_channel_item)
        elif is_playlist_item:
            open_playlist_item = self.context_menu.Append(wx.ID_ANY, "Open Playlist")
            self.Bind(wx.EVT_MENU, lambda e: self.onPlayOrOpenPlaylist(e, item_info=selected_item_info), open_playlist_item)
        else: # It's a video
            play_menu = wx.Menu()
            play_low_item = play_menu.Append(wx.ID_ANY, "Low Quality")
            play_medium_item = play_menu.Append(wx.ID_ANY, "Medium Quality")
            play_best_item = play_menu.Append(wx.ID_ANY, "Best Quality")
            self.Bind(wx.EVT_MENU, lambda e: self.onPlayQuality(e, "low", item_info=selected_item_info), play_low_item)
            self.Bind(wx.EVT_MENU, lambda e: self.onPlayQuality(e, "medium", item_info=selected_item_info), play_medium_item)
            self.Bind(wx.EVT_MENU, lambda e: self.onPlayQuality(e, "best", item_info=selected_item_info), play_best_item)
            self.context_menu.AppendSubMenu(play_menu, "Play Video")

            play_audio_item = self.context_menu.Append(wx.ID_ANY, "Play as Audio")
            self.Bind(wx.EVT_MENU, lambda e: self.onPlay(e, play_as_audio=True, item_info=selected_item_info), play_audio_item)

        copy_item = self.context_menu.Append(wx.ID_ANY, "Copy Link")
        self.Bind(wx.EVT_MENU, lambda e: self.onCopyLinkFromMenu(e, item_info=selected_item_info), copy_item)

        if not is_channel_item: # Channels themselves aren't downloaded this way
            download_item = self.context_menu.Append(wx.ID_ANY, "Download...")
            self.Bind(wx.EVT_MENU, lambda e: self.onDownloadSelectedVideo(e, video_info=selected_item_info), download_item)

            direct_download_item = self.context_menu.Append(wx.ID_ANY, "Direct Download")
            self.Bind(wx.EVT_MENU, lambda e: self.onDirectDownload(e, video_info=selected_item_info), direct_download_item)

        if not is_playlist_item:
            show_description_item = self.context_menu.Append(wx.ID_ANY, "Video description")
            self.Bind(wx.EVT_MENU, lambda e: self.onShowDescription(e, video_info=selected_item_info), show_description_item)

        is_favorite = False
        video_url = selected_item_info.get('webpage_url')
        if video_url:
            is_favorite = self.favorites_manager.is_favorite(video_url)

        fav_item_label = "Remove from Favorites" if is_favorite else "Add to Favorites"
        toggle_favorite_item = wx.MenuItem(self.context_menu, wx.ID_ANY, fav_item_label)
        self.context_menu.Append(toggle_favorite_item)
        self.Bind(wx.EVT_MENU, self.onToggleFavorite, toggle_favorite_item)

        self.PopupMenu(self.context_menu, event.GetPosition())

    def onCopyLinkFromMenu(self, event, item_info=None):
        if not item_info:
            item_info = self.get_selected_item_info_from_listbox()
        if not item_info:
            wx.MessageBox("Please select an item first", "Error", wx.OK | wx.ICON_INFORMATION)
            return

        url_to_copy = item_info.get('webpage_url')
        if url_to_copy:
            self.copy_to_clipboard(url_to_copy)
        else:
            wx.MessageBox("No link is available for this item.", "Copy Error", wx.OK | wx.ICON_WARNING)
        if event: event.Skip()

    def copy_to_clipboard(self, text):
        clipboard = wx.Clipboard.Get()
        if clipboard.Open():
            text_data = wx.TextDataObject()
            text_data.SetText(text)
            clipboard.SetData(text_data)
            clipboard.Close()
            clipboard.Flush()
            speak("Link copyed to clipboard", interrupt=True)
        else:
            wx.MessageBox("Could not access clipboard.", "Error", wx.OK | wx.ICON_ERROR)

    def onShowDescription(self, event, video_info=None):
        if not video_info:
            video_info = self.get_selected_item_info_from_listbox()
        if not video_info:
            wx.MessageBox("Please select a video to view its description.", "Error", wx.OK | wx.ICON_INFORMATION)
            return

        if video_info.get('is_playlist') or video_info.get('is_channel'):
            desc = video_info.get('_original_item_data', {}).get('description')
            if desc:
                 desc_dlg = DescriptionDialog(self, f"{video_info.get('title')} Description", desc)
                 desc_dlg.ShowModal()
                 desc_dlg.Destroy()
            else:
                 item_url = video_info.get('webpage_url')
                 item_title = video_info.get('title')
                 if item_url:
                    self.show_loading_dialog(f"Fetching description for: {item_title}")
                    threading.Thread(target=self.fetch_description_thread, args=(item_url,)).start()
                 else:
                    wx.MessageBox("Description not available (no URL).", "Info", wx.OK | wx.ICON_INFORMATION)
            if event: event.Skip()
            return

        video_url = video_info.get('webpage_url')
        video_title = video_info.get('title')
        # Check if description is already in _original_item_data from search
        original_data = video_info.get('_original_item_data', {})
        if 'description' in original_data and original_data['description'] is not None:
            wx.CallAfter(self.onDescriptionFetchComplete, DescriptionFetchEvent(description=original_data['description'], error=None))
        elif video_url:
            self.show_loading_dialog(f"Getting description for: {video_title}")
            threading.Thread(target=self.fetch_description_thread, args=(video_url,)).start()
        else:
            wx.MessageBox("Cannot get description without a video URL.", "Critical Error", wx.OK | wx.ICON_ERROR)
        if event: event.Skip()

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

    def onDownloadSelectedVideo(self, event, video_info=None):
        if not video_info:
            video_info = self.get_selected_item_info_from_listbox()
        if not video_info:
            wx.MessageBox("Please select an item to download.", "Error", wx.OK | wx.ICON_INFORMATION)
            return

        if video_info.get('is_channel'): # Channels are not downloaded directly
            wx.MessageBox("Cannot download a channel directly. Please open the channel to download its content.", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        video_url = video_info.get('webpage_url')
        video_title = video_info.get('title')
        if not video_url:
            wx.MessageBox("No link is available for download.", "Download Error", wx.OK | wx.ICON_ERROR)
            return

        settings_dialog = DownloadSettingsDialog(self, "Download Settings", video_title, video_url)
        if settings_dialog.ShowModal() == wx.ID_OK:
            download_settings = settings_dialog.settings
            if video_info.get('is_playlist'):
                wx.MessageBox("Note: Downloading entire playlists uses default yt-dlp behavior for the playlist URL. Individual item download settings apply if yt-dlp processes it as a single item.", "Playlist Download", wx.OK | wx.ICON_INFORMATION)
                download_settings['is_playlist'] = True
            self.start_download_process(download_settings)
        settings_dialog.Destroy()
        if event: event.Skip()

    def onDirectDownload(self, event, video_info=None):
        if not video_info:
            video_info = self.get_selected_item_info_from_listbox()
        if not video_info:
            wx.MessageBox("Please select an item to download.", "Error", wx.OK | wx.ICON_INFORMATION)
            return

        if video_info.get('is_channel'):
            wx.MessageBox("Cannot download a channel directly.", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        video_url = video_info.get('webpage_url')
        video_title = video_info.get('title')
        if not video_url:
            wx.MessageBox("No link is available for direct download.", "Download Error", wx.OK | wx.ICON_ERROR)
            return

        youtube_settings = self.config.get('YouTube', {})
        default_type = youtube_settings.get('default_download_type', 'Video')
        default_video_quality = youtube_settings.get('default_video_quality', 'Medium')
        default_audio_format = youtube_settings.get('default_audio_format', 'mp3')
        default_audio_quality = youtube_settings.get('default_audio_quality', '128K')
        default_directory = youtube_settings.get('default_download_directory', '')
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
        if video_info.get('is_playlist'):
            download_settings['is_playlist'] = True
            wx.MessageBox("Note: Direct downloading entire playlists uses default yt-dlp behavior.", "Playlist Direct Download", wx.OK | wx.ICON_INFORMATION)
        self.start_download_process(download_settings)
        if event: event.Skip()

    def start_download_process(self, download_settings):
        """Starts the DownloadDialog with the collected settings."""
        dlg_title = f"Downloading: {download_settings['filename']}"
        download_dlg = DownloadDialog(self, dlg_title, download_settings)
        download_dlg.download_task()


    def onClose(self, event):
        if hasattr(self, 'player') and self.player:
            try: self.player.Close(force=True)
            except: pass
        self.destroy_loading_dialog()

        if self.calling_frame_to_show_on_my_close:
            try:
                self.calling_frame_to_show_on_my_close.Show()
                self.calling_frame_to_show_on_my_close.Raise()
            except (wx.wxAssertionError, RuntimeError):
                pass
        self.Destroy()
