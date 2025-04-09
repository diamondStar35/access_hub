import wx
import requests
import concurrent.futures
import json
import os
from .audio_player import SimplePlayer


class SharedVoicesDialog(wx.Dialog):
    PAGE_SIZE = 100

    def __init__(self, parent, api_key):
        super().__init__(parent, title="Shared Voice Library", size=(850, 600), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX)
        self.api_key = api_key
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.current_page = 0
        self.current_search_query = ""
        self.page_cache = {}
        self.displayed_voices_on_page = []
        self.has_more_pages = False
        self.selected_voice_info = {}
        self.fetch_progress_dialog = None
        self.add_progress_dialog = None

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_label = wx.StaticText(panel, label="Search:")
        self.search_text = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_button = wx.Button(panel, label="Search")
        self.clear_search_button = wx.Button(panel, label="Clear")

        self.search_text.Bind(wx.EVT_TEXT_ENTER, self.on_search)
        self.search_button.Bind(wx.EVT_BUTTON, self.on_search)
        self.clear_search_button.Bind(wx.EVT_BUTTON, self.on_clear_search)

        search_sizer.Add(search_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)
        search_sizer.Add(self.search_text, 1, wx.EXPAND | wx.RIGHT, 5)
        search_sizer.Add(self.search_button, 0, wx.RIGHT, 5)
        main_sizer.Add(search_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_VRULES | wx.LC_SINGLE_SEL)
        self.list_ctrl.InsertColumn(0, "Name", width=150)
        self.list_ctrl.InsertColumn(1, "Accent", width=100)
        self.list_ctrl.InsertColumn(2, "Language", width=80)
        self.list_ctrl.InsertColumn(3, "Gender", width=70)
        self.list_ctrl.InsertColumn(4, "Age", width=50)
        self.list_ctrl.InsertColumn(5, "Usage Status", width=150)
        self.list_ctrl.InsertColumn(6, "Clones", width=100)
        self.list_ctrl.InsertColumn(7, "Description", width=150)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_list_item_selected)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_list_item_deselected)
        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.preview_button = wx.Button(panel, label="&Preview")
        self.preview_button.Disable()
        self.prev_button = wx.Button(panel, label="Previous Page")
        self.next_button = wx.Button(panel, label="Next Page")
        self.page_info_text = wx.StaticText(panel, label="Page 1")
        self.add_button = wx.Button(panel, label="Add to My Voices...")
        self.add_button.Disable()
        close_button = wx.Button(panel, wx.ID_CLOSE)

        self.preview_button.Bind(wx.EVT_BUTTON, self.on_preview)
        self.prev_button.Bind(wx.EVT_BUTTON, self.on_previous_page)
        self.next_button.Bind(wx.EVT_BUTTON, self.on_next_page)
        self.add_button.Bind(wx.EVT_BUTTON, self.on_add_voice)
        close_button.Bind(wx.EVT_BUTTON, self.on_close)

        bottom_sizer.Add(self.prev_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        bottom_sizer.Add(self.next_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)
        bottom_sizer.Add(self.page_info_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)
        bottom_sizer.AddStretchSpacer(1) # Pushes Add/Close to the right
        bottom_sizer.Add(self.add_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        bottom_sizer.Add(close_button, 0, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(bottom_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(main_sizer)
        self.Layout()
        self.CentreOnParent()
        self.update_navigation_buttons()
        self.request_page_update(self.current_page)


    def on_search(self, event):
        """Initiates a search based on the text control content."""
        query = self.search_text.GetValue().strip()
        if query != self.current_search_query: # Trigger even if same query entered again
            self.current_search_query = query
            self.current_page = 0 # Reset to first page for new search
            self.page_cache = {}
            self.request_page_update(self.current_page)

    def on_clear_search(self, event):
        """Clears the search query and reloads the first page."""
        if self.current_search_query: # Only reload if there was an active search
            self.search_text.SetValue("")
            self.current_search_query = ""
            self.current_page = 0
            self.page_cache = {}
            self.request_page_update(self.current_page)
        else:
             self.search_text.SetValue("") # Just clear the box if no search active

    def on_preview(self, event):
        """Plays the preview audio for the selected shared voice."""
        if not self.selected_voice_info:
            wx.MessageBox("Please select a voice from the list first.", "No Selection", wx.OK | wx.ICON_WARNING)
            return

        try:
            preview_url = self.selected_voice_info.get('preview_url')
            voice_name = self.selected_voice_info.get('name', 'Shared Voice')
            if preview_url:
                player_dialog = SimplePlayer(self, preview_url, title=f"Preview: {voice_name}")
                player_dialog.ShowModal()
            else:
                wx.MessageBox(f"No preview URL is available for the shared voice '{voice_name}'.",
                              "Preview Not Available", wx.OK | wx.ICON_INFORMATION)

        except Exception as e:
            wx.MessageBox(f"An unexpected error occurred trying to play the preview:\n{e}",
                          "Preview Error", wx.OK | wx.ICON_ERROR)

    def on_previous_page(self, event):
        if self.current_page > 0:
            self.current_page -= 1
            self.request_page_update(self.current_page)

    def on_next_page(self, event):
        if self.has_more_pages:
             self.current_page += 1
             self.request_page_update(self.current_page)

    def on_list_item_selected(self, event):
        """Updates selection state and enables Add button."""
        selected_index = -1
        if event:
            selected_index = event.GetIndex()
        else:
            selected_index = self.list_ctrl.GetFirstSelected()

        if 0 <= selected_index < len(self.displayed_voices_on_page):
            self.selected_voice_info = self.displayed_voices_on_page[selected_index]
            self.preview_button.Enable(True)
            self.add_button.Enable(True)
        else:
            self.selected_voice_info = {}
            self.preview_button.Disable()
            self.add_button.Disable()
        if event: event.Skip()

    def on_list_item_deselected(self, event):
        """Disables Add button when selection is lost."""
        self.selected_voice_info = {}
        self.preview_button.Disable()
        self.add_button.Disable()
        event.Skip()

    def request_page_update(self, page_number):
        """Requests data for a specific page, checking cache first."""
        self.list_ctrl.DeleteAllItems()
        self.displayed_voices_on_page = []
        self.selected_voice_info = {}
        self.add_button.Disable()
        self.page_info_text.SetLabel(f"Page: {page_number + 1}")
        self.has_more_pages = False

        cache_key = (page_number, self.current_search_query)
        if cache_key in self.page_cache:
            voices_on_page, has_more = self.page_cache[cache_key]
            self.has_more_pages = has_more
            self.populate_list_ctrl(voices_on_page)
            self.update_navigation_buttons()
            wx.CallAfter(self.on_list_item_selected, None) # Re-check selection
        else:
            if self.fetch_progress_dialog:
                wx.CallAfter(self.fetch_progress_dialog.Destroy)

            self.fetch_progress_dialog = wx.GenericProgressDialog(
                "Loading Voices", f"Fetching page {page_number + 1}...",
                parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
            )
            self.fetch_progress_dialog.Show()
            fetch_future = self.executor.submit(self.fetch_page_worker, page_number, self.current_search_query)
            fetch_future.add_done_callback(lambda f: self.on_page_load_complete(f, page_number, self.current_search_query))

    def fetch_page_worker(self, page_number, search_term):
        """Worker thread function to fetch a single page of shared voices."""
        headers = {'xi-api-key': self.api_key}
        url = "https://api.elevenlabs.io/v1/shared-voices"
        params = {'page_size': self.PAGE_SIZE, 'page': page_number}
        if search_term:
            params['search'] = search_term

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            voices = data.get('voices', [])
            has_more = data.get('has_more', False)
            return (voices, has_more)

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Network error fetching page {page_number}: {e}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding API response for page {page_number}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error fetching page {page_number}: {e}") from e

    def on_page_load_complete(self, future, page_number, search_query_used):
        """Callback executed when voice page fetching is complete."""
        if hasattr(self, 'fetch_progress_dialog') and self.fetch_progress_dialog:
            wx.CallAfter(self.fetch_progress_dialog.Destroy)
            self.fetch_progress_dialog = None

        try:
            voices_on_page, has_more = future.result()
            cache_key = (page_number, search_query_used)
            self.page_cache[cache_key] = (voices_on_page, has_more)

            if self.current_page == page_number and self.current_search_query == search_query_used:
                self.has_more_pages = has_more
                wx.CallAfter(self.populate_list_ctrl, voices_on_page)
                wx.CallAfter(self.update_navigation_buttons)
                wx.CallAfter(self.on_list_item_selected, None)

        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Failed to load page {page_number + 1}:\n{e}", "Error", wx.OK | wx.ICON_ERROR, self)
            wx.CallAfter(self.update_navigation_buttons)

    def populate_list_ctrl(self, voices_list):
        """Populates the list control with the given voice data."""
        self.list_ctrl.DeleteAllItems()
        self.displayed_voices_on_page = voices_list

        if not voices_list:
            index = self.list_ctrl.InsertItem(0, "No voices found for this page or search.")
            self.list_ctrl.SetItemTextColour(index, wx.Colour("gray"))
            self.last_fetch_count = 0
            return

        # Sort the current page's voices alphabetically before display
        voices_list.sort(key=lambda voice: voice.get('name', '').lower())

        for index, voice in enumerate(voices_list):
            name = voice.get('name', 'Unknown')
            accent = voice.get('accent', 'Unknown')
            language = voice.get('language', '')
            gender = voice.get('gender', 'Unknown')
            age = voice.get('age', 'Unknown')
            description = voice.get('description', '')
            clones = voice.get('cloned_by_count', 0)
            free_allowed = voice.get('free_users_allowed', False)
            usage_status = "Free users are allowed to use this voice" if free_allowed else "Requires paid subscription"
            clone_text = f"Cloned by {clones}"

            list_index = self.list_ctrl.InsertItem(index, name)
            self.list_ctrl.SetItem(list_index, 1, accent if accent else 'Unknown')
            self.list_ctrl.SetItem(list_index, 2, language if language else 'Unknown')
            self.list_ctrl.SetItem(list_index, 3, gender if gender else 'Unknown')
            self.list_ctrl.SetItem(list_index, 4, age if age else 'Unknown')
            self.list_ctrl.SetItem(list_index, 5, usage_status)
            self.list_ctrl.SetItem(list_index, 6, clone_text)
            self.list_ctrl.SetItem(list_index, 7, description if description else '')

    def update_navigation_buttons(self):
        """Enables/disables Previous/Next buttons based on current state."""
        self.prev_button.Enable(self.current_page > 0)
        self.next_button.Enable(self.has_more_pages)
        self.page_info_text.SetLabel(f"Page: {self.current_page + 1}")

    def on_add_voice(self, event):
        """Handles the 'Add to My Voices' button click."""
        if not self.selected_voice_info:
            wx.MessageBox("Please select a voice from the list first.", "No Selection", wx.OK | wx.ICON_WARNING)
            return

        default_name = self.selected_voice_info.get('name', 'Unnamed Shared Voice')
        public_owner_id = self.selected_voice_info.get('public_owner_id')
        voice_id = self.selected_voice_info.get('voice_id')
        if not public_owner_id or not voice_id:
             wx.MessageBox("Selected voice data is incomplete (missing owner or voice ID). Cannot add.", "Error", wx.OK | wx.ICON_ERROR)
             return

        add_dialog = AddSharedVoiceDialog(self, default_name)
        return_code = add_dialog.ShowModal()
        new_name = add_dialog.GetName() # Get name even if cancelled, though we won't use it
        add_dialog.Destroy()

        if return_code == wx.ID_OK and new_name:
            # User confirmed, proceed with adding
            self.add_progress_dialog = wx.ProgressDialog(
                "Adding Voice", f"Adding '{new_name}' to your voices...",
                parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
            )
            self.add_progress_dialog.Show()
            add_future = self.executor.submit(self.add_voice_to_library_worker, public_owner_id, voice_id, new_name)
            add_future.add_done_callback(self.on_voice_added)
        elif return_code == wx.ID_OK and not new_name:
             wx.MessageBox("Please enter a name for the voice.", "Name Required", wx.OK | wx.ICON_WARNING)

    def add_voice_to_library_worker(self, public_user_id, voice_id, new_name):
        """Worker thread to add the shared voice via API POST."""
        url = f"https://api.elevenlabs.io/v1/voices/add/{public_user_id}/{voice_id}"
        headers = {'xi-api-key': self.api_key, 'Content-Type': 'application/json'}
        payload = {'new_name': new_name}

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {e}"
            if e.response is not None:
                 error_msg += f" (Status Code: {e.response.status_code})"
                 try:
                     error_data = e.response.json()
                     detail = error_data.get('detail')
                     if isinstance(detail, dict):
                        if 'message' in detail: error_msg += f" - {detail['message']}"
                        if 'validation_errors' in detail: error_msg += f"\nDetails: {detail['validation_errors']}"
                     elif isinstance(detail, str):
                         error_msg += f" - {detail}"
                 except json.JSONDecodeError: pass # Ignore if response is not JSON
            raise ConnectionError(error_msg) from e
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred adding voice: {e}") from e

    def on_voice_added(self, future):
        """Callback after attempting to add the voice."""
        if hasattr(self, 'add_progress_dialog') and self.add_progress_dialog:
             wx.CallAfter(self.add_progress_dialog.Destroy)
             self.add_progress_dialog = None

        try:
            result = future.result()
            new_voice_id = result.get('voice_id')
            if new_voice_id:
                 wx.CallAfter(wx.MessageBox, f"Voice added successfully to your library!",
                               "Success", wx.OK | wx.ICON_INFORMATION, self)
            else:
                 wx.CallAfter(wx.MessageBox, "Voice adding finished, but API did not return a new Voice ID.",
                               "Add Failed", wx.OK | wx.ICON_ERROR, self)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Failed to add voice to library:\n{e}",
                          "Add Error", wx.OK | wx.ICON_ERROR, self)

    def on_close(self, event):
        """Closes the dialog and shuts down the executor."""
        if hasattr(self, 'executor') and self.executor:
            self.executor.shutdown(wait=False)
        if hasattr(self, 'fetch_progress_dialog') and self.fetch_progress_dialog:
            wx.CallAfter(self.fetch_progress_dialog.Destroy)
        if hasattr(self, 'add_progress_dialog') and self.add_progress_dialog:
            wx.CallAfter(self.add_progress_dialog.Destroy)
        self.Destroy()

    def __del__(self):
        # Fallback executor shutdown
        if hasattr(self, 'executor') and self.executor and not self.executor._shutdown:
            self.executor.shutdown(wait=False)


class AddSharedVoiceDialog(wx.Dialog):
    """Simple dialog to get the new name for an added shared voice."""
    def __init__(self, parent, default_name):
        super().__init__(parent, title="Add Voice to Library", size=(350, 150))

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        instruction = wx.StaticText(panel, label="Enter the name for this voice in your library:")
        self.name_text = wx.TextCtrl(panel, value=default_name)
        sizer.Add(instruction, 0, wx.ALL, 10)
        sizer.Add(self.name_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)

    def GetName(self):
        """Returns the entered name."""
        return self.name_text.GetValue().strip()
