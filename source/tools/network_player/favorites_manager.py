import wx
import os
import json
import app_vars
import threading
from speech import speak
from .youtube_player import YoutubePlayer, EVT_VLC_READY
from .download_dialogs import DownloadSettingsDialog, DownloadDialog
from .utils import run_yt_dlp_json
from gui.dialogs import DescriptionDialog
from configobj import ConfigObj

# Events for description fetching, playlists, and channels
DescriptionFetchEvent, EVT_DESCRIPTION_FETCH = wx.lib.newevent.NewEvent()
FavPlaylistItemsFetchEvent, EVT_FAV_PLAYLIST_ITEMS_FETCH = wx.lib.newevent.NewEvent()
FavChannelDataFetchEvent, EVT_FAV_CHANNEL_DATA_FETCH = wx.lib.newevent.NewEvent()

def get_favorites_path():
    """Gets the path to the favorites JSON file."""
    config_dir = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    return os.path.join(config_dir, "favorites.json")

class FavoritesManager:
    def __init__(self):
        self.favorites_path = get_favorites_path()
        self._favorites = self.load_favorites()

    def load_favorites(self):
        """Loads favorites from the JSON file."""
        if os.path.exists(self.favorites_path):
            try:
                with open(self.favorites_path, 'r', encoding='utf-8') as f:
                    favorites = json.load(f)
                    if isinstance(favorites, list):
                        for item in favorites:
                            if 'title' not in item:
                                item['title'] = 'Untitled'
                            if 'youtube_url' not in item:
                                item['youtube_url'] = ''
                        return favorites
                    else:
                        return []
            except (IOError, json.JSONDecodeError):
                wx.MessageBox("Error loading favorites file. It might be corrupted.", "Favorites Load Error", wx.OK | wx.ICON_ERROR)
                return []
        else:
            return []

    def save_favorites(self):
        """Saves the current favorites list to the JSON file."""
        try:
            with open(self.favorites_path, 'w', encoding='utf-8') as f:
                json.dump(self._favorites, f, indent=4)
        except (IOError, OSError) as e:
            wx.MessageBox(f"Error saving favorites: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def add_favorite(self, video_info):
        """Adds an item to the favorites list if not already present.
        item_info should be a dict with 'webpage_url', 'title', and 'item_type'.
        Optionally, it can include 'description'.
        """
        video_url = video_info.get('webpage_url')
        if not video_url: return False

        if not self.is_favorite(video_url):
            info = {
                'title': video_info.get('title', 'Untitled'),
                'youtube_url': video_url,
                'type': video_info.get('type', 'video'),
            }
            if 'description' in video_info and video_info['description'] is not None:
                info['description'] = video_info['description']            
            self._favorites.append(info)
            self.save_favorites()
            return True, f"{info['type']} added to favorites."
        return False, "Item is already in favorites."

    def remove_favorite(self, item_url):
        """Removes an item from the favorites list by URL."""
        initial_count = len(self._favorites)
        item_type_removed = 'Item'
        for fav in self._favorites:
            if fav.get('youtube_url') == item_url:
                item_type_removed = fav.get('type', 'item')
                break # Found the item

        self._favorites = [fav for fav in self._favorites if fav.get('youtube_url') != item_url]
        if len(self._favorites) < initial_count:
            self.save_favorites()
            return True, f"{item_type_removed} removed from favorites."
        return False, "Item not found in favorites."

    def is_favorite(self, video_url):
        """Checks if a video URL is already in the favorites."""
        return any(fav.get('youtube_url') == video_url for fav in self._favorites)

    def get_favorites_list(self):
        """Returns the current list of favorite videos."""
        return self._favorites

    def toggle_favorite(self, item_info):
        """Adds or removes a favorite based on its current status.
        item_info should be a dict with 'youtube_url', 'title', and 'item_type'.
        """
        item_url = item_info.get('webpage_url')
        if not item_url: 
            return False, "Cannot toggle favorite: No URL provided."

        if self.is_favorite(item_url):
            success, message = self.remove_favorite(item_url)
            return not success, message
        else:
            success, message = self.add_favorite(item_info)
            return success, message


class FavoritesFrame(wx.Frame):
    def __init__(self, parent, calling_frame_to_show_on_my_close=None):
        super().__init__(parent, title="Favorite videos", size=(800, 600), style=wx.DEFAULT_FRAME_STYLE | wx.RESIZE_BORDER)
        self.calling_frame_to_show_on_my_close = calling_frame_to_show_on_my_close
        self.parent_for_sub_frames = parent
        self.favorites_manager = FavoritesManager()
        self.current_favorites = self.favorites_manager.get_favorites_list()
        self.context_menu = None
        self.player = None
        self.loading_dialog = None

        config_path = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name, "settings.ini")
        self.config = ConfigObj(config_path)
        youtube_settings = self.config.get('YouTube', {})
        self.default_download_type = youtube_settings.get('default_download_type', 'Audio')
        self.default_video_quality = youtube_settings.get('video_quality', 'Medium')
        self.default_audio_format = youtube_settings.get('default_audio_format', 'mp3')
        self.default_audio_quality = youtube_settings.get('default_audio_quality', '128K')
        self.default_download_directory = youtube_settings.get('default_download_directory', '')

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        title_label = wx.StaticText(panel, label="Favorite Videos:")
        vbox.Add(title_label, 0, wx.ALL, 5)

        self.favorites_listbox = wx.ListBox(panel)
        vbox.Add(self.favorites_listbox, 1, wx.ALL | wx.EXPAND, 5)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        play_button = wx.Button(panel, label="Play")
        play_button.Bind(wx.EVT_BUTTON, self.onPlay)
        button_sizer.Add(play_button, 0, wx.ALL, 5)

        download_button = wx.Button(panel, label="Download...")
        download_button.Bind(wx.EVT_BUTTON, self.onDownloadSelectedVideo)
        button_sizer.Add(download_button, 0, wx.ALL, 5)

        direct_download_button = wx.Button(panel, label="Direct Download")
        direct_download_button.Bind(wx.EVT_BUTTON, self.onDirectDownload)
        button_sizer.Add(direct_download_button, 0, wx.ALL, 5)

        remove_button = wx.Button(panel, label="Remove from Favorites")
        remove_button.Bind(wx.EVT_BUTTON, self.onRemoveFromFavorites)
        button_sizer.Add(remove_button, 0, wx.ALL, 5)
        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 5)

        panel.SetSizer(vbox)
        self.populate_listbox()

        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Bind(wx.EVT_CHAR_HOOK, self.onKey)
        self.favorites_listbox.Bind(wx.EVT_CONTEXT_MENU, self.onContextMenu)
        self.favorites_listbox.Bind(wx.EVT_LISTBOX_DCLICK, self.onPlay)
        self.Bind(EVT_DESCRIPTION_FETCH, self.onDescriptionFetchComplete)
        self.Bind(EVT_FAV_PLAYLIST_ITEMS_FETCH, self.onPlaylistItemsFetched)
        self.Bind(EVT_FAV_CHANNEL_DATA_FETCH, self.onChannelDataFetched)
        self.Centre()


    def populate_listbox(self):
        """Populates the listbox with current favorites."""
        self.favorites_listbox.Clear()
        for fav in self.current_favorites:
            item_type_display = fav.get('type', 'video')
            item_text = f"{fav.get('title', 'Untitled')}: {item_type_display}"
            self.favorites_listbox.Append(item_text)

    def get_selected_video_info(self):
        """Gets the video info dictionary for the currently selected item."""
        selection = self.favorites_listbox.GetSelection()
        if selection != -1 and selection < len(self.current_favorites):
            return self.current_favorites[selection]
        return None

    def onPlay(self, event, play_as_audio=False):
        """Plays the selected favorite video or opens playlist/channel."""
        selected_item = self.get_selected_video_info()
        if not selected_item:
            wx.MessageBox("Please select an item.", "No selection", wx.OK | wx.ICON_INFORMATION)
            return

        item_url = selected_item.get('youtube_url')
        title = selected_item.get('title', 'Untitled')
        item_type = selected_item.get('type', 'video')
        if not item_url:
            wx.MessageBox(f"Could not find the link for '{title}'.", "Error", wx.OK | wx.ICON_ERROR)
            return

        self.Hide()
        if item_type == 'video':
            # Determine format_selector based on play_as_audio and settings
            format_selector = 'ba/b' if play_as_audio else self.get_video_format_selector()
            threading.Thread(target=self._fetch_and_play_video, args=(item_url, title, format_selector, play_as_audio)).start()
        elif item_type == 'playlist':
            if play_as_audio:
                self.Show()
                wx.MessageBox("Cannot play a playlist as audio directly from favorites. Please open it first.", "Info", wx.OK | wx.ICON_INFORMATION)
                return
            self.show_loading_dialog(f"Getting playlist info for: {title}", "Loading Playlist...")
            threading.Thread(target=self.fetch_playlist_items_thread, args=(item_url, title)).start()

        elif item_type == 'channel':
            if play_as_audio:
                self.Show()
                wx.MessageBox("Cannot open a channel as audio directly from favorites. Please open it first.", "Info", wx.OK | wx.ICON_INFORMATION)
                return
            self.show_loading_dialog(f"Getting channel info for: {title}", "Loading Channel...")
            threading.Thread(target=self.fetch_channel_data_thread, args=(item_url, title)).start()
        else:
            self.Show()
            wx.MessageBox(f"Unknown item type: {item_type}", "Error", wx.OK | wx.ICON_ERROR)
        if event: event.Skip()

    def get_video_format_selector(self):
        quality = self.default_video_quality.lower()
        if quality == "low": return 'worst[ext=mp4]/worstvideo[ext=mp4]/worst'
        elif quality == "medium": return 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'
        elif quality == "best": return 'best[ext=mp4]/bestvideo[ext=mp4]/best'
        return 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]' # Default

    def _fetch_and_play_video(self, youtube_url, title, format_selector, play_as_audio=False):
        """Worker thread to fetch stream info and create the player."""
        try:
            dialog_title_str = "Playing audio..." if play_as_audio else "Playing..."
            loading_message = f"Playing audio: {title}..." if play_as_audio else f"Playing: {title}..."
            wx.CallAfter(self.show_loading_dialog, loading_message, dialog_title_str)

            info_dict = run_yt_dlp_json(youtube_url, format_selector=format_selector)
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
            wx.CallAfter(self._create_and_show_player, title, media_url, description, youtube_url)

        except Exception as e:
            wx.CallAfter(self.destroy_loading_dialog)
            wx.CallAfter(wx.MessageBox, f"Could not play: {e}", "Playback Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Show)

    def fetch_playlist_items_thread(self, playlist_url, playlist_title):
        """Worker thread to fetch playlist items."""
        playlist_items = []
        error_message = None
        try:
            info_dict = run_yt_dlp_json(playlist_url, is_search=True)
            if info_dict and 'entries' in info_dict:
                playlist_items = info_dict['entries']
            elif info_dict:
                error_message = "Failed to fetch playlist items: Unexpected data structure."
            
        except Exception as e:
            error_message = f"Error fetching playlist items for '{playlist_title}': {e}"
        wx.PostEvent(self, FavPlaylistItemsFetchEvent(items=playlist_items, error=error_message, title=playlist_title))

    def onPlaylistItemsFetched(self, event):
        """Handles the completion of playlist item fetching."""
        self.destroy_loading_dialog()
        items = event.items
        error = event.error
        playlist_title = event.title

        if error:
            wx.MessageBox(error, "Playlist Error", wx.OK | wx.ICON_ERROR)
            self.Show() 
        elif items:
            from .youtube_search import YoutubeSearchResults
            playlist_viewer_frame = YoutubeSearchResults(self.parent_for_sub_frames, items, is_playlist_view=True, calling_frame_to_show_on_my_close=self)
            top_level_parent = wx.GetApp().GetTopWindow()
            if hasattr(top_level_parent, 'add_child_frame'):
                 top_level_parent.add_child_frame(playlist_viewer_frame)
            playlist_viewer_frame.Show()
        else:
            wx.MessageBox(f"No items found in the playlist '{playlist_title}' or an error occurred.", "Playlist Empty", wx.OK | wx.ICON_INFORMATION)
            self.Show()

    def fetch_channel_data_thread(self, channel_url, channel_title):
        """Worker thread to fetch channel data."""
        channel_data = None
        error_message = None
        try:
            info_dict = run_yt_dlp_json(channel_url, is_search=True)
            if info_dict:
                channel_data = info_dict
        except Exception as e:
            error_message = f"Error getting channel data for '{channel_title}': {e}"
        wx.PostEvent(self, FavChannelDataFetchEvent(data=channel_data, error=error_message, title=channel_title))

    def onChannelDataFetched(self, event):
        """Handles the completion of channel data fetching."""
        self.destroy_loading_dialog()
        channel_data = event.data
        error = event.error
        channel_title = event.title

        if error:
            wx.MessageBox(error, "Channel Error", wx.OK | wx.ICON_ERROR)
            self.Show()
        elif channel_data:
            from .channel_viewer import ChannelViewerFrame
            channel_viewer_frame = ChannelViewerFrame(self.parent_for_sub_frames, channel_data, calling_frame_to_show_on_my_close=self)
            top_level_parent = wx.GetApp().GetTopWindow()
            if hasattr(top_level_parent, 'add_child_frame'):
                 top_level_parent.add_child_frame(channel_viewer_frame)
            channel_viewer_frame.Show()
        else:
            wx.MessageBox(f"No data found for the channel '{channel_title}' or an error occurred.", "Channel Error", wx.OK | wx.ICON_INFORMATION)
            self.Show()

    def _create_and_show_player(self, title, media_url, description, original_youtube_link):
        """Creates and shows the YoutubePlayer (must be on the main thread)."""
        # YoutubePlayer's 4th arg ('search_results_frame') is the frame to show when player closes.
        # Here, it's self (FavoritesFrame).
        self.player = YoutubePlayer(None, title, media_url, self, description, original_youtube_link, None, -1)
        self.player.Bind(EVT_VLC_READY, self.show_when_ready)

    def show_when_ready(self, event):
        """Called when the YoutubePlayer is ready to show."""
        self.destroy_loading_dialog()
        if self.player:
            self.player.Show()
        event.Skip()

    def show_loading_dialog(self, message, dialog_title="Loading..."):
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            try:
                self.loading_dialog.Destroy()
            except RuntimeError:
                pass
            self.loading_dialog = None

        self.loading_dialog = wx.Dialog(self, title=dialog_title, style=wx.CAPTION)
        loading_text = wx.StaticText(self.loading_dialog, -1, message)
        loading_sizer = wx.BoxSizer(wx.VERTICAL)
        loading_sizer.Add(loading_text, 0, wx.ALL | wx.CENTER, 10)
        self.loading_dialog.SetSizer(loading_sizer)
        self.loading_dialog.Show()
        wx.Yield()

    def destroy_loading_dialog(self):
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            self.loading_dialog.Destroy()
            self.loading_dialog=None

    def onDownloadSelectedVideo(self, event):
        selected_item = self.get_selected_video_info()
        if selected_item:
            video_url = selected_item.get('youtube_url')
            video_title = selected_item.get('title', 'Untitled')
            item_type = selected_item.get('type', 'video')
            if not video_url:
                wx.MessageBox(f"Could not find the link for '{video_title}'.", "Download Error", wx.OK | wx.ICON_ERROR)
                return
            
            if item_type == 'channel':
                wx.MessageBox("Channels cannot be downloaded directly from favorites. Please open the channel to download specific content.", "Info", wx.OK | wx.ICON_INFORMATION)
                return

            settings_dialog = DownloadSettingsDialog(self, "Download Settings", video_title, video_url)
            if settings_dialog.ShowModal() == wx.ID_OK:
                download_settings = settings_dialog.settings
                if item_type == 'playlist':
                    download_settings['is_playlist'] = True
                    wx.MessageBox("Note: Downloading entire playlists uses default yt-dlp behavior for the playlist URL. Individual item download settings apply if yt-dlp processes it as a single item.", "Playlist Download", wx.OK | wx.ICON_INFORMATION)
                self.start_download_process(download_settings)
            settings_dialog.Destroy()
        else:
            wx.MessageBox("Please select an item to download.", "No Selection", wx.OK | wx.ICON_INFORMATION)

    def onDirectDownload(self, event):
        selected_item = self.get_selected_video_info()
        if not selected_item:
            wx.MessageBox("Please select an item to download.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return

        video_url = selected_item.get('youtube_url')
        video_title = selected_item.get('title', 'Untitled')
        item_type = selected_item.get('type', 'video')
        if not video_url:
            wx.MessageBox(f"Could not find the link for '{video_title}'.", "Download Error", wx.OK | wx.ICON_ERROR)
            return

        if item_type == 'channel':
            wx.MessageBox("Channels cannot be directly downloaded. Please open the channel to download its content.", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        if not self.default_download_directory or not os.path.isdir(self.default_download_directory):
            wx.MessageBox("Default download directory is not set or invalid. Please configure it in Settings.", "Direct Download Failed", wx.OK | wx.ICON_WARNING)
            return

        download_settings = {
            'url': video_url,
            'filename': video_title,
            'directory': self.default_download_directory,
            'type': self.default_download_type,
            'video_quality': self.default_video_quality,
            'audio_format': self.default_audio_format,
            'audio_quality': self.default_audio_quality,
        }
        if item_type == 'playlist':
            download_settings['is_playlist'] = True
            wx.MessageBox("Note: Direct downloading entire playlists uses default yt-dlp behavior.", "Playlist Direct Download", wx.OK | wx.ICON_INFORMATION)        
        self.start_download_process(download_settings)

    def start_download_process(self, download_settings):
        """Starts the DownloadDialog with the collected settings."""
        dlg_title = f"Downloading: {download_settings['filename']}"
        download_dlg = DownloadDialog(self, dlg_title, download_settings)
        download_dlg.download_task()

    def onRemoveFromFavorites(self, event):
        selected_item = self.get_selected_video_info()
        if selected_item:
            item_url = selected_item.get('youtube_url')
            success, message = self.favorites_manager.remove_favorite(item_url)
            if success:
                speak(message) # Message already includes item type
                self.current_favorites = self.favorites_manager.get_favorites_list()
                self.populate_listbox()
                sel_idx = self.favorites_listbox.GetSelection()
                if sel_idx == -1 and self.favorites_listbox.GetCount() > 0:
                    self.favorites_listbox.SetSelection(0)
                elif sel_idx >= self.favorites_listbox.GetCount() and self.favorites_listbox.GetCount() > 0:
                    self.favorites_listbox.SetSelection(self.favorites_listbox.GetCount() -1) # Select last if previous was out of bounds
            else:
                speak(message)

    def onKey(self, event):
        keycode = event.GetKeyCode()
        modifiers = event.GetModifiers()
        selection = self.favorites_listbox.GetSelection()
        if selection == -1:
            event.Skip()
            return

        selected_item = self.get_selected_video_info()
        item_type = selected_item.get('type', 'video')

        if keycode == wx.WXK_SPACE:
           self.onRemoveFromFavorites(event)
        elif keycode == wx.WXK_RETURN:
           if modifiers == wx.MOD_CONTROL:
               if item_type == 'video':
                   self.onPlay(event, play_as_audio=True)
               else:
                   wx.MessageBox(f"Cannot play {item_type}s as audio directly. Please open the {item_type} first.", "Info", wx.OK | wx.ICON_INFORMATION)
           else:
               self.onPlay(event, play_as_audio=False)
        elif keycode == wx.WXK_ESCAPE:
           self.Close()
        else:
           event.Skip()

    def onContextMenu(self, event):
        selection = self.favorites_listbox.GetSelection()
        if selection == -1:
            return
        selected_item = self.get_selected_video_info()
        if not selected_item: return

        item_type = selected_item.get('type', 'video')
        if self.context_menu:
            self.context_menu.Destroy()
        self.context_menu = wx.Menu()
        if item_type == 'video':
            play_menu = wx.Menu()
            play_video_item = play_menu.Append(wx.ID_ANY, "Play as video")
            play_audio_item = play_menu.Append(wx.ID_ANY, "Play as audio")
            self.context_menu.AppendSubMenu(play_menu, "Play")
            self.Bind(wx.EVT_MENU, lambda evt, ia=False: self.onPlay(evt, play_as_audio=ia), play_video_item)
            self.Bind(wx.EVT_MENU, lambda evt, ia=True: self.onPlay(evt, play_as_audio=ia), play_audio_item)
        elif item_type == 'playlist':
            open_playlist_item = self.context_menu.Append(wx.ID_ANY, "Open Playlist")
            self.Bind(wx.EVT_MENU, self.onPlay, open_playlist_item) 
        elif item_type == 'channel':
            open_channel_item = self.context_menu.Append(wx.ID_ANY, "Open Channel")
            self.Bind(wx.EVT_MENU, self.onPlay, open_channel_item)
                
        copy_item = self.context_menu.Append(wx.ID_ANY, "Copy Video Link")
        self.Bind(wx.EVT_MENU, self.onCopyLinkFromMenu, copy_item)

        if item_type == 'video' or item_type == 'playlist':
            download_item = self.context_menu.Append(wx.ID_ANY, f"Download {item_type.capitalize()}...")
            self.Bind(wx.EVT_MENU, self.onDownloadSelectedVideo, download_item)

            direct_download_item = self.context_menu.Append(wx.ID_ANY, f"Direct Download {item_type.capitalize()}")
            self.Bind(wx.EVT_MENU, self.onDirectDownload, direct_download_item)
        
        show_description_item = self.context_menu.Append(wx.ID_ANY, f"{item_type.capitalize()} Description")
        self.Bind(wx.EVT_MENU, self.onShowDescription, show_description_item)

        remove_item = self.context_menu.Append(wx.ID_ANY, "Remove from Favorites")
        self.Bind(wx.EVT_MENU, self.onRemoveFromFavorites, remove_item)
        self.PopupMenu(self.context_menu, event.GetPosition())

    def onCopyLinkFromMenu(self, event):
        selected_video = self.get_selected_video_info()
        if selected_video:
            url = selected_video.get('youtube_url')
            item_type = selected_video.get('type', 'item')
            if url:
                clipboard = wx.Clipboard.Get()
                if clipboard.Open():
                    text_data = wx.TextDataObject()
                    text_data.SetText(url)
                    clipboard.SetData(text_data)
                    clipboard.Close()
                    speak(f"{item_type} link copyed to clipboard", interrupt=True)
                else:
                    wx.MessageBox("Could not access clipboard.", "Error", wx.OK | wx.ICON_ERROR)
            else:
                 wx.MessageBox("No link is available for this favorite.", "Error", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox("Please select a video first", "Error", wx.OK | wx.ICON_INFORMATION)

    def onShowDescription(self, event):
        selected_video = self.get_selected_video_info()
        if not selected_video:
            wx.MessageBox("Please select a video to view its description.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return

        video_url = selected_video.get('youtube_url')
        video_title = selected_video.get('title', 'Untitled')
        if not video_url:
             wx.MessageBox(f"Could not find URL for '{video_title}'.", "Description Error", wx.OK | wx.ICON_ERROR)
             return

        # Check if description is already stored in the favorite item
        if 'description' in selected_video and selected_video['description'] is not None:
            desc_dlg = DescriptionDialog(self, f"{video_title} Description", selected_video['description'])
            desc_dlg.ShowModal()
            desc_dlg.Destroy()
        else:
            self.show_loading_dialog(f"Fetching description for: {video_title}")
            threading.Thread(target=self.fetch_description_thread, args=(video_url,)).start()

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
        wx.PostEvent(self, DescriptionFetchEvent(description=description, error=error_message))

    def onDescriptionFetchComplete(self, event):
        """Handles the completion of the description fetching thread."""
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
             try:
                 self.loading_dialog.Destroy()
             except Exception:
                 pass
             self.loading_dialog = None

        description = event.description
        error_message = event.error

        if error_message:
            wx.MessageBox(error_message, "Error", wx.OK | wx.ICON_ERROR)
        elif description is not None:
            desc_dlg = DescriptionDialog(self, "Video description", description)
            desc_dlg.ShowModal()
            desc_dlg.Destroy()
        else:
             wx.MessageBox("Description not available for this video.", "Description Unavailable", wx.OK | wx.ICON_INFORMATION)


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
                pass # Frame might be destroyed or already shown
        self.Destroy()
