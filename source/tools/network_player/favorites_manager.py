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

# Events for description fetching
DescriptionFetchEvent, EVT_DESCRIPTION_FETCH = wx.lib.newevent.NewEvent()

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
        """Adds a video to the favorites list if not already present."""
        video_url = video_info.get('link')
        if not video_url: return False

        if not self.is_favorite(video_url):
            info = {
                'title': video_info.get('title', 'Untitled'),
                'youtube_url': video_url,
            }
            self._favorites.append(info)
            self.save_favorites()
            return True
        return False # Already exists

    def remove_favorite(self, video_url):
        """Removes a video from the favorites list by URL."""
        initial_count = len(self._favorites)
        self._favorites = [fav for fav in self._favorites if fav.get('youtube_url') != video_url]
        if len(self._favorites) < initial_count:
            self.save_favorites()
            return True
        return False # Not found

    def is_favorite(self, video_url):
        """Checks if a video URL is already in the favorites."""
        return any(fav.get('youtube_url') == video_url for fav in self._favorites)

    def get_favorites_list(self):
        """Returns the current list of favorite videos."""
        return self._favorites

    def toggle_favorite(self, video_info):
        """Adds or removes a favorite based on its current status."""
        video_url = video_info.get('link')
        if not video_url: return False, "No URL provided."

        if self.is_favorite(video_url):
            if self.remove_favorite(video_url):
                return False, "Removed from favorites."
            else:
                return False, "Failed to remove from favorites." # Should not happen if is_favorite is true
        else:
            if self.add_favorite(video_info):
                return True, "Added to favorites."
            else:
                return True, "Failed to add to favorites." # Should not happen if is_favorite is false


class FavoritesFrame(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Favorite videos", size=(800, 600), style=wx.DEFAULT_FRAME_STYLE | wx.RESIZE_BORDER)
        self.parent = parent
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
        self.Bind(EVT_DESCRIPTION_FETCH, self.onDescriptionFetchComplete)
        self.Centre()


    def populate_listbox(self):
        """Populates the listbox with current favorites."""
        self.favorites_listbox.Clear()
        for fav in self.current_favorites:
            self.favorites_listbox.Append(fav.get('title', 'Untitled'))

    def get_selected_video_info(self):
        """Gets the video info dictionary for the currently selected item."""
        selection = self.favorites_listbox.GetSelection()
        if selection != -1 and selection < len(self.current_favorites):
            return self.current_favorites[selection]
        return None

    def onPlay(self, event, play_as_audio=False):
        """Plays the selected favorite video after fetching stream info."""
        selected_video = self.get_selected_video_info()
        if selected_video:
            youtube_url = selected_video.get('youtube_url')
            title = selected_video.get('title', 'Untitled')
            if not youtube_url:
                 wx.MessageBox(f"Could not find URL for '{title}'.", "Playback Error", wx.OK | wx.ICON_ERROR)
                 return

            quality = self.default_video_quality.lower()
            if quality == "low":
                format_selector = 'worst[ext=mp4]/worstvideo[ext=mp4]/worst'
            elif quality == "medium":
                 format_selector = 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'
            elif quality == "best":
                 format_selector = 'best[ext=mp4]/bestvideo[ext=mp4]/best'
            else:
                format_selector = 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'
            threading.Thread(target=self._fetch_and_play, args=(youtube_url, title, format_selector)).start()

    def _fetch_and_play(self, youtube_url, title, format_selector):
        """Worker thread to fetch stream info and create the player."""
        try:
            wx.CallAfter(self.show_loading_dialog, f"Playing: {title}...")

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
            wx.CallAfter(wx.MessageBox, f"Could not play the video: {e}", "Playback Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Show)

    def _create_and_show_player(self, title, media_url, description, original_youtube_link):
        """Creates and shows the YoutubePlayer (must be on the main thread)."""
        self.player = YoutubePlayer(self, title, media_url, None, description, original_youtube_link, None, None)
        self.player.Bind(EVT_VLC_READY, self.show_when_ready)
        self.player.Bind(wx.EVT_CLOSE, self.player.OnClose)

    def show_when_ready(self, event):
        """Called when the YoutubePlayer is ready to show."""
        self.destroy_loading_dialog()
        if self.player:
            self.Hide()
            self.player.Show()
        event.Skip()

    def destroy_loading_dialog(self):
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            self.loading_dialog.Destroy()
            self.loading_dialog=None

    def onDownloadSelectedVideo(self, event):
        """Opens the download settings dialog for the selected video."""
        selected_video = self.get_selected_video_info()
        if selected_video:
            video_url = selected_video.get('youtube_url')
            video_title = selected_video.get('title', 'Untitled')
            if not video_url:
                 wx.MessageBox(f"Could not find URL for '{video_title}'.", "Download Error", wx.OK | wx.ICON_ERROR)
                 return

            settings_dialog = DownloadSettingsDialog(self, "Download Settings", video_title, video_url)
            if settings_dialog.ShowModal() == wx.ID_OK:
                download_settings = settings_dialog.settings
                self.start_download_process(download_settings)
            settings_dialog.Destroy()
        else:
            wx.MessageBox("Please select a video to download.", "No Selection", wx.OK | wx.ICON_INFORMATION)

    def onDirectDownload(self, event):
        """Directly downloads the selected video using default settings."""
        selected_video = self.get_selected_video_info()
        if not selected_video:
            wx.MessageBox("Please select a video to download.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return

        video_url = selected_video.get('youtube_url')
        video_title = selected_video.get('title', 'Untitled')
        if not video_url:
            wx.MessageBox(f"Could not find URL for '{video_title}'.", "Download Error", wx.OK | wx.ICON_ERROR)
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
        self.start_download_process(download_settings)

    def start_download_process(self, download_settings):
        """Starts the DownloadDialog with the collected settings."""
        dlg_title = f"Downloading: {download_settings['filename']}"
        download_dlg = DownloadDialog(self, dlg_title, download_settings)
        download_dlg.download_task()

    def onRemoveFromFavorites(self, event):
        """Removes the selected video from favorites."""
        selected_video = self.get_selected_video_info()
        if selected_video:
            video_url = selected_video.get('youtube_url')
            if self.favorites_manager.remove_favorite(video_url):
                speak("Removed from favorites.")
                self.current_favorites = self.favorites_manager.get_favorites_list()
                self.populate_listbox()
            else:
                 speak("Failed to remove from favorites.")

    def onKey(self, event):
        keycode = event.GetKeyCode()
        selection = self.favorites_listbox.GetSelection()

        if keycode == wx.WXK_SPACE and selection != -1:
           self.onRemoveFromFavorites(event)
        elif keycode == wx.WXK_RETURN and selection != -1:
           self.onPlay(event)
        elif keycode == wx.WXK_ESCAPE:
           self.Close()
        else:
           event.Skip()

    def onContextMenu(self, event):
        selection = self.favorites_listbox.GetSelection()
        if selection == -1:
            return

        if self.context_menu:
            self.context_menu.Destroy()
        self.context_menu = wx.Menu()

        play_item = self.context_menu.Append(wx.ID_ANY, "Play")
        self.Bind(wx.EVT_MENU, self.onPlay, play_item)

        copy_item = self.context_menu.Append(wx.ID_ANY, "Copy Video Link")
        self.Bind(wx.EVT_MENU, self.onCopyLinkFromMenu, copy_item)

        download_item = self.context_menu.Append(wx.ID_ANY, "Download video...")
        self.Bind(wx.EVT_MENU, self.onDownloadSelectedVideo, download_item)

        direct_download_item = self.context_menu.Append(wx.ID_ANY, "Direct Download")
        self.Bind(wx.EVT_MENU, self.onDirectDownload, direct_download_item)

        show_description_item = self.context_menu.Append(wx.ID_ANY, "Video description")
        self.context_menu.Append(show_description_item)
        self.Bind(wx.EVT_MENU, self.onShowDescription, show_description_item)

        remove_item = self.context_menu.Append(wx.ID_ANY, "Remove from Favorites")
        self.Bind(wx.EVT_MENU, self.onRemoveFromFavorites, remove_item)
        self.PopupMenu(self.context_menu, event.GetPosition())

    def onCopyLinkFromMenu(self, event):
        selected_video = self.get_selected_video_info()
        if selected_video:
            url = selected_video.get('youtube_url')
            if url:
                clipboard = wx.Clipboard.Get()
                if clipboard.Open():
                    text_data = wx.TextDataObject(url)
                    clipboard.SetDataObject(text_data)
                    clipboard.Close()
                    speak("Link copyed to clipboard", interrupt=True)
                else:
                    wx.MessageBox("Could not access clipboard.", "Error", wx.OK | wx.ICON_ERROR)
            else:
                 wx.MessageBox("No URL available for this favorite.", "Error", wx.OK | wx.ICON_INFORMATION)
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


    def show_loading_dialog(self, message):
        self.loading_dialog = wx.Dialog(self, title="Playing...", style=wx.CAPTION)
        loading_text = wx.StaticText(self.loading_dialog, -1, message)
        loading_sizer = wx.BoxSizer(wx.VERTICAL)
        loading_sizer.Add(loading_text, 0, wx.ALL | wx.CENTER, 10)
        self.loading_dialog.SetSizer(loading_sizer)
        self.loading_dialog.Show()
        wx.Yield()

    def onClose(self, event):
        if hasattr(self, 'player') and self.player:
            self.player.Close()
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
             try:
                 self.loading_dialog.Destroy()
             except Exception:
                 pass
        if self.parent:
            wx.CallAfter(self.parent.Show)
        self.Destroy()
