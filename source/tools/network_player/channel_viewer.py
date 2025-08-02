import wx
import threading
from .youtube_player import YoutubePlayer, EVT_VLC_READY
from .utils import run_yt_dlp_json
from gui.dialogs import DescriptionDialog
from speech import speak
import app_vars
from configobj import ConfigObj
import os


class ChannelViewerFrame(wx.Frame):
    def __init__(self, parent_search_results_frame, channel_data_dict, calling_frame_to_show_on_my_close=None):
        self.channel_data_dict = channel_data_dict
        self.channel_info = {} 
        self.channel_items_list = []
        self.player = None
        self.loading_dialog = None

        _title = self.channel_data_dict.get('title', self.channel_data_dict.get('channel', 'Channel Viewer'))
        super().__init__(parent_search_results_frame, title=_title, size=(800, 650), style=wx.DEFAULT_FRAME_STYLE | wx.RESIZE_BORDER)
        self.parent_search_results_frame = parent_search_results_frame
        self.calling_frame_to_show_on_my_close = calling_frame_to_show_on_my_close
        self._extract_channel_details()
        self.load_settings()

        self.panel = wx.Panel(self)
        self.notebook = wx.Notebook(self.panel)
        self.info_panel = wx.Panel(self.notebook)
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        self.info_text_ctrl = wx.TextCtrl(self.info_panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        info_sizer.Add(self.info_text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        self.info_panel.SetSizer(info_sizer)
        self.notebook.AddPage(self.info_panel, "Basic Info")
        self._populate_basic_info_tab()

        self.content_panel = wx.Panel(self.notebook)
        content_sizer = wx.BoxSizer(wx.VERTICAL)
        self.content_list_ctrl = wx.ListBox(self.content_panel)
        content_sizer.Add(wx.StaticText(self.content_panel, label="Channel Content:"), 0, wx.ALL, 5)
        content_sizer.Add(self.content_list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        content_buttons_panel = wx.Panel(self.content_panel)
        content_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        play_button = wx.Button(content_buttons_panel, label="Open")
        download_button = wx.Button(content_buttons_panel, label="Download")
        
        content_buttons_sizer.Add(play_button, 0, wx.ALL, 5)
        content_buttons_sizer.Add(download_button, 0, wx.ALL, 5)
        content_buttons_sizer.AddStretchSpacer(1) 
        content_buttons_panel.SetSizer(content_buttons_sizer)
        content_sizer.Add(content_buttons_panel, 0, wx.EXPAND | wx.ALL, 5)

        self.content_panel.SetSizer(content_sizer)
        self.notebook.AddPage(self.content_panel, "Content")
        self._populate_content_list_tab()

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        close_button_panel = wx.Panel(self.panel)
        close_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.close_viewer_button = wx.Button(close_button_panel, label="Close")
        close_button_sizer.AddStretchSpacer(1)
        close_button_sizer.Add(self.close_viewer_button, 0, wx.ALL, 5)
        close_button_panel.SetSizer(close_button_sizer)        
        main_sizer.Add(close_button_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        self.panel.SetSizer(main_sizer)
        self.Centre()

        self.Bind(wx.EVT_CLOSE, self.on_viewer_close)
        self.close_viewer_button.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
        play_button.Bind(wx.EVT_BUTTON, self.on_item_play_open_handler)
        download_button.Bind(wx.EVT_BUTTON, self.on_item_download_handler)
        self.content_list_ctrl.Bind(wx.EVT_LISTBOX_DCLICK, self.on_item_play_open_handler)
        self.content_list_ctrl.Bind(wx.EVT_CONTEXT_MENU, self.on_item_context_menu_handler)
        self.content_list_ctrl.Bind(wx.EVT_CHAR_HOOK, self.on_content_list_key)

    def load_settings(self):
        """Loads player default settings from the main app config."""
        config_path = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name, "settings.ini")
        self.config = ConfigObj(config_path)
        youtube_settings = self.config.get('YouTube', {})
        self.default_video_quality = youtube_settings.get('video_quality', 'Medium')

    def _extract_channel_details(self):
        """Extracts basic info and items from the raw channel_data_dict."""
        self.channel_info['title'] = self.channel_data_dict.get('channel', self.channel_data_dict.get('title', 'Unknown'))
        self.channel_info['description'] = self.channel_data_dict.get('description', 'Unknown')
        self.channel_info['uploader'] = self.channel_data_dict.get('uploader', self.channel_data_dict.get('channel', 'Unknown'))
        self.channel_info['id'] = self.channel_data_dict.get('channel_id', self.channel_data_dict.get('id', 'Unknown'))
        self.channel_info['url'] = self.channel_data_dict.get('channel_url', self.channel_data_dict.get('webpage_url', 'Unknown'))
        self.channel_info['follower_count'] = self.channel_data_dict.get('channel_follower_count', 'Unknown')
        self.channel_info['view_count'] = self.channel_data_dict.get('view_count', 'Unknown')
        self.channel_info['video_count'] = self.channel_data_dict.get('playlist_count', 'Unknown')
        self.channel_items_list = self.channel_data_dict.get('entries', [])
        if not self.channel_items_list and self.channel_data_dict.get('_type') == 'playlist':
             pass

    def _populate_basic_info_tab(self):
        info_str = f"Channel: {self.channel_info.get('title', 'Unknown')}\n"
        info_str += f"Uploader: {self.channel_info.get('uploader', 'Unknown')}\n"
        info_str += f"ID: {self.channel_info.get('id')}\n"
        info_str += f"URL: {self.channel_info.get('url')}\n"
        fc = self.channel_info.get('follower_count')
        if fc is not None:
            try:
                info_str += f"Followers: {int(fc):,}\n"
            except (ValueError, TypeError): # Handle if fc is not a number, though yt-dlp should give numbers
                info_str += f"Followers: {fc}\n"
        else:
            info_str += "Followers: Unknown\n"

        vc = self.channel_info.get('view_count')
        if vc is not None:
            try:
                info_str += f"Total Views: {int(vc):,}\n"
            except (ValueError, TypeError):
                info_str += f"Total Views: {vc}\n"
        else:
            info_str += "Total Views: Unknown\n"

        info_str += f"Items in this view: {self.channel_info['video_count']} videos\n"
        info_str += f"\nDescription:\n{self.channel_info.get('description', 'N/A')}"
        self.info_text_ctrl.SetValue(info_str)

    def _populate_content_list_tab(self):
        self.content_list_ctrl.Clear()
        for item_data in self.channel_items_list:
            title = item_data.get('title', 'Untitled Item')
            playlist_info_dict = self.parent_search_results_frame.is_item_playlist(item_data)
            is_playlist = playlist_info_dict['is_playlist']
            playlist_item_count = playlist_info_dict['count']

            item_text = ""
            if is_playlist:
                if playlist_item_count is not None:
                    item_text = f"{title}: A playlist containing {playlist_item_count} videos"
                else:
                    item_text = f"{title}: Playlist"
            else:
                duration_str = self.parent_search_results_frame.format_duration(item_data.get('duration'))
                uploader_str = item_data.get('uploader') or item_data.get('channel') or self.channel_info.get('title', 'Unknown')
                item_text = f"{title}, Duration: {duration_str}, By: {uploader_str}"
            self.content_list_ctrl.Append(item_text)

    def get_selected_content_item_info_dict(self):
        """Gets the full dictionary for the selected item from self.channel_items_list."""
        selection = self.content_list_ctrl.GetSelection()
        if selection != -1 and selection < len(self.channel_items_list):
            return self.channel_items_list[selection]
        return None

    def _prepare_item_info_for_parent_handler(self, original_item_data):
        """Converts an item from channel_items_list to the format expected by parent handlers."""
        if not original_item_data: return None
        webpage_url = original_item_data.get('webpage_url') or original_item_data.get('url')
        playlist_info_dict = self.parent_search_results_frame.is_item_playlist(original_item_data)
        is_playlist = playlist_info_dict['is_playlist']
        playlist_count = playlist_info_dict['count']
        item_type_for_fav = 'video'
        if is_playlist:
            item_type_for_fav = 'playlist'

        item_info = {
            'title': original_item_data.get('title', 'Untitled'),
            'webpage_url': webpage_url,
            'duration': original_item_data.get('duration'),
            'uploader': original_item_data.get('uploader') or original_item_data.get('channel') or self.channel_info.get('title', 'Unknown'),
            'is_playlist': is_playlist,
            'is_channel': False, # This handler is for items within a channel, so they are not channels themselves
            'type': item_type_for_fav, # Crucial for favorites
            '_original_item_data': original_item_data
        }
        
        if is_playlist:
            # If it's a playlist within the channel, pass the channel's uploader as context
            item_info['playlist_uploader'] = self.channel_info.get('uploader') or self.channel_info.get('title', 'Unknown Channel')
            
        return item_info

    def on_item_play_open_handler(self, event):
        selected_original_item = self.get_selected_content_item_info_dict()
        if not selected_original_item:
            if event: event.Skip()
            return

        item_info_for_parent_ysr = self._prepare_item_info_for_parent_handler(selected_original_item)
        if not item_info_for_parent_ysr:
            if event: event.Skip()
            return

        from .youtube_search import YoutubeSearchResults        
        is_playlist = item_info_for_parent_ysr.get('is_playlist', False)
        if is_playlist:
            if self.calling_frame_to_show_on_my_close and \
               isinstance(self.calling_frame_to_show_on_my_close, YoutubeSearchResults):
                self.calling_frame_to_show_on_my_close.onPlayOrOpenPlaylist(event=None, item_info=item_info_for_parent_ysr, calling_frame_to_hide_override=self)
            else:
                wx.MessageBox("Error: Could not delegate playlist opening. Invalid parent context.", "Context Error", wx.OK | wx.ICON_ERROR)
        else:
            self.Hide()
            self.play_channel_video(selected_original_item, play_as_audio=False)
        if event: event.Skip()

    def play_channel_video(self, video_item_data, play_as_audio=False):
        """Plays a video from the channel_items_list."""
        video_url = video_item_data.get('webpage_url') or video_item_data.get('url')
        video_title = video_item_data.get('title', 'Untitled Video')
        if not video_url:
            wx.MessageBox("Video link was not found for this item.", "Playback Error", wx.OK | wx.ICON_ERROR)
            return

        self.show_loading_dialog(f"Loading: {video_title}")
        # self.Hide() # Player will handle this via search_results_frame.Hide()
        threading.Thread(target=self._fetch_and_play_video_from_channel,
                         args=(video_url, video_title, video_item_data, play_as_audio)).start()

    def _fetch_and_play_video_from_channel(self, video_url, video_title, video_item_data, play_as_audio):
        try:
            format_selector = None
            if play_as_audio:
                format_selector = 'ba/b'
            else:
                quality = self.default_video_quality
                if quality == "Low": format_selector = 'worst[ext=mp4]/worstvideo[ext=mp4]/worst'
                elif quality == "Medium": format_selector = 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'
                elif quality == "Best": format_selector = 'best[ext=mp4]/bestvideo[ext=mp4]/best'
                else: format_selector = 'best[height<=?720][ext=mp4]/bestvideo[height<=?720][ext=mp4]/best[height<=?720]'

            info_dict = run_yt_dlp_json(video_url, format_selector=format_selector)
            if not info_dict:
                raise ValueError("Failed to get video stream info from yt-dlp.")

            media_url = info_dict.get('url')
            description = info_dict.get('description', '')
            if not media_url:
                formats = info_dict.get('formats', [])
                if formats: media_url = formats[0].get('url')
            if not media_url:
                raise ValueError("No playable media URL found.")

            wx.CallAfter(self._create_and_show_channel_player, video_title, media_url, description, video_url, video_item_data)

        except Exception as e:
            wx.CallAfter(self.destroy_loading_dialog)
            wx.CallAfter(self.Show)
            wx.CallAfter(wx.MessageBox, f"Could not play video from channel: {e}", "Error", wx.OK | wx.ICON_ERROR)


    def _create_and_show_channel_player(self, title, media_url, description, original_youtube_link, played_item_data):
        """Instantiates YoutubePlayer with channel's items for navigation."""
        current_idx = -1
        try:
            current_idx = self.channel_items_list.index(played_item_data)
        except ValueError:
            # Should not happen if played_item_data is from self.channel_items_list
            pass
        
        self.player = YoutubePlayer(None, title, media_url, self, description, original_youtube_link, self.channel_items_list, current_idx)
        self.player.Bind(EVT_VLC_READY, self.on_player_ready)

    def on_player_ready(self, event):
        self.destroy_loading_dialog()
        if self.player:
            self.Hide()
            self.player.Show()
        event.Skip()

    def on_item_download_handler(self, event):
        selected_original_item = self.get_selected_content_item_info_dict()
        if selected_original_item:
            item_info_for_parent = self._prepare_item_info_for_parent_handler(selected_original_item)
            if item_info_for_parent:
                self.parent_search_results_frame.onDownloadSelectedVideo(event=None, video_info=item_info_for_parent)
        if event: event.Skip()

    def on_item_context_menu_handler(self, event):
        selected_original_item = self.get_selected_content_item_info_dict()
        if not selected_original_item:
            return

        item_info_for_parent = self._prepare_item_info_for_parent_handler(selected_original_item)
        if not item_info_for_parent: return # Should not happen

        context_menu = wx.Menu()
        is_playlist = item_info_for_parent.get('is_playlist', False)
        if is_playlist:
            open_playlist_item = context_menu.Append(wx.ID_ANY, "Open Playlist")
            self.Bind(wx.EVT_MENU, lambda e: self.parent_search_results_frame.onPlayOrOpenPlaylist(e, item_info=item_info_for_parent), open_playlist_item)
        else:
            play_menu = wx.Menu()
            play_video_item = play_menu.Append(wx.ID_ANY, "Play Video")
            self.Bind(wx.EVT_MENU, lambda e: self.play_channel_video(selected_original_item, play_as_audio=False), play_video_item)
            context_menu.AppendSubMenu(play_menu, "Play Video")

            play_audio_item = context_menu.Append(wx.ID_ANY, "Play as Audio")
            self.Bind(wx.EVT_MENU, lambda e: self.play_channel_video(selected_original_item, play_as_audio=True), play_audio_item)

        copy_link_item = context_menu.Append(wx.ID_ANY, "Copy Link")
        self.Bind(wx.EVT_MENU, lambda e: self.parent_search_results_frame.onCopyLinkFromMenu(e, item_info=item_info_for_parent), copy_link_item)

        download_item = context_menu.Append(wx.ID_ANY, "Download...")
        self.Bind(wx.EVT_MENU, lambda e: self.parent_search_results_frame.onDownloadSelectedVideo(e, video_info=item_info_for_parent), download_item)

        direct_dl_item = context_menu.Append(wx.ID_ANY, "Direct Download")
        self.Bind(wx.EVT_MENU, lambda e: self.parent_search_results_frame.onDirectDownload(e, video_info=item_info_for_parent), direct_dl_item)

        if not is_playlist:
            desc_item = context_menu.Append(wx.ID_ANY, "Video Description")
            self.Bind(wx.EVT_MENU, lambda e: self.parent_search_results_frame.onShowDescription(e, video_info=item_info_for_parent), desc_item)

        is_fav = self.parent_search_results_frame.favorites_manager.is_favorite(item_info_for_parent.get('webpage_url'))
        fav_label = "Remove from Favorites" if is_fav else "Add to Favorites"
        fav_item = context_menu.Append(wx.ID_ANY, fav_label)
        self.Bind(wx.EVT_MENU, lambda e: self.parent_search_results_frame.onToggleFavorite(e, item_info=item_info_for_parent), fav_item)
        self.PopupMenu(context_menu)
        context_menu.Destroy()

    def on_content_list_key(self, event):
        keycode = event.GetKeyCode()
        modifiers = event.GetModifiers()
        selected_original_item = self.get_selected_content_item_info_dict()

        if not selected_original_item:
            event.Skip()
            return
        
        item_info_for_parent = self._prepare_item_info_for_parent_handler(selected_original_item)
        is_playlist = item_info_for_parent.get('is_playlist', False) if item_info_for_parent else False

        if keycode == wx.WXK_RETURN:
            if modifiers == wx.MOD_CONTROL:
                if not is_playlist:
                    self.play_channel_video(selected_original_item, play_as_audio=True)
                else:
                    wx.MessageBox("Cannot play playlist as audio with Ctrl+Enter. Use Enter to open.", "Info", wx.OK | wx.ICON_INFORMATION)
            else:
                self.on_item_play_open_handler(event=None) # Pass event=None as it's not a direct UI event for this call
        elif keycode == wx.WXK_SPACE and item_info_for_parent:
            self.parent_search_results_frame.onToggleFavorite(event=None, item_info=item_info_for_parent)
        elif keycode == ord('C') and modifiers == wx.MOD_CONTROL and item_info_for_parent:
            self.parent_search_results_frame.onCopyLinkFromMenu(event=None, item_info=item_info_for_parent)
        else:
            event.Skip()

    def show_loading_dialog(self, message, title="Loading..."):
        if self.loading_dialog:
            try: self.loading_dialog.Destroy()
            except RuntimeError: pass # May already be destroyed
        self.loading_dialog = wx.Dialog(self, title=title, style=wx.CAPTION)
        loading_text = wx.StaticText(self.loading_dialog, -1, message)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(loading_text, 0, wx.ALL | wx.CENTER, 10)
        self.loading_dialog.SetSizer(sizer)
        self.loading_dialog.Show()
        wx.Yield()

    def destroy_loading_dialog(self):
        if self.loading_dialog:
            try: self.loading_dialog.Destroy()
            except RuntimeError: pass
        self.loading_dialog = None


    def on_viewer_close(self, event):
        if self.player:
            try: self.player.Close(force=True)
            except Exception: pass
        self.destroy_loading_dialog()

        if self.calling_frame_to_show_on_my_close:
            try:
                self.calling_frame_to_show_on_my_close.Show()
                self.calling_frame_to_show_on_my_close.Raise()
            except (wx.wxAssertionError, RuntimeError):
                pass
        self.Destroy()
