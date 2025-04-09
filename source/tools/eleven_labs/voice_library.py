import wx, concurrent.futures, json, requests
from gui.custom_controls import CustomSlider
from .settings_editor import EditVoiceSettings
from .audio_player import SimplePlayer


class VoiceLibraryDialog(wx.Dialog):
    """Dialog to display the user's ElevenLabs voice library."""
    def __init__(self, parent, api_key):
        super().__init__(parent, title="Voice Library", size=(600, 400),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.api_key = api_key
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.all_voices = []
        self.selected_voice_id = None
        self.selected_list_index = -1

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_VRULES | wx.LC_SINGLE_SEL)
        self.list_ctrl.InsertColumn(0, "Name", width=200)
        self.list_ctrl.InsertColumn(1, "Category", width=100)
        self.list_ctrl.InsertColumn(2, "Description", width=250)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_list_item_selected)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_list_item_deselected)
        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.edit_button = wx.Button(panel, label="&Edit Settings")
        self.edit_button.Bind(wx.EVT_BUTTON, self.on_edit)
        self.edit_button.Disable() # Disabled initially

        self.preview_button = wx.Button(panel, label="&Preview")
        self.preview_button.Bind(wx.EVT_BUTTON, self.on_preview)
        self.preview_button.Disable()

        self.delete_button = wx.Button(panel, label="&Delete Voice")
        self.delete_button.Bind(wx.EVT_BUTTON, self.on_delete)
        self.delete_button.Disable()

        close_button = wx.Button(panel, wx.ID_CLOSE)
        close_button.Bind(wx.EVT_BUTTON, self.on_close)

        button_sizer.Add(self.edit_button, 0, wx.ALL, 5)
        button_sizer.Add(self.preview_button, 0, wx.ALL, 5)
        button_sizer.Add(self.delete_button, 0, wx.ALL, 5)
        button_sizer.AddStretchSpacer(1)
        button_sizer.Add(close_button, 0, wx.ALL, 5)
        sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(sizer)
        self.Layout()
        self.CentreOnParent()
        self.load_voices()


    def on_edit(self, event):
        if not self.selected_voice_id:
            wx.MessageBox("Please select a voice from the list first.", "No Selection", wx.OK | wx.ICON_WARNING)
            return

        voice_name = self.list_ctrl.GetItemText(self.selected_list_index)
        edit_dialog = EditVoiceSettings(self, self.api_key, self.selected_voice_id, voice_name)
        edit_dialog.ShowModal()
        edit_dialog.Destroy()

    def on_preview(self, event):
        """Plays the preview audio for the selected voice."""
        if self.selected_list_index == -1:
            wx.MessageBox("Please select a voice from the list first.", "No Selection", wx.OK | wx.ICON_WARNING)
            return

        try:
            selected_voice_data = self.all_voices[self.selected_list_index]
            preview_url = selected_voice_data.get('preview_url')
            if preview_url:
                player_dialog = SimplePlayer(self, preview_url, title=f"Preview: {selected_voice_data.get('name', 'Voice')}")
                player_dialog.ShowModal() # Blocks until player closes
            else:
                wx.MessageBox("No preview URL available for this voice.", "Preview Not Found", wx.OK | wx.ICON_INFORMATION)

        except IndexError:
             wx.MessageBox("Error retrieving voice data. Please try selecting again.", "Selection Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"An unexpected error occurred trying to play the preview:\n{e}", "Preview Error", wx.OK | wx.ICON_ERROR)

    def on_delete(self, event):
        if not self.selected_voice_id or self.selected_list_index < 0:
            wx.MessageBox("Please select a voice from the list first.", "No Selection", wx.OK | wx.ICON_WARNING)
            return

        voice_name = self.list_ctrl.GetItemText(self.selected_list_index)
        confirm = wx.MessageBox(f"Are you sure you want to delete the voice '{voice_name}'?\nThis action cannot be undone.",
                                "Confirm Deletion", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self)

        if confirm == wx.YES:
            self.progress_dialog = wx.ProgressDialog(
                "Deleting Voice", f"Deleting '{voice_name}'...",
                parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
            )
            self.progress_dialog.Show()

            # Store index before starting worker, as selection might change
            index_to_delete = self.selected_list_index
            voice_id_to_delete = self.selected_voice_id
            delete_future = self.executor.submit(self.delete_voice_worker, voice_id_to_delete)
            delete_future.add_done_callback(lambda f: self.on_voice_deleted(f, index_to_delete, voice_id_to_delete))

    def delete_voice_worker(self, voice_id):
        """Worker thread function to delete a voice."""
        headers = {'xi-api-key': self.api_key}
        url = f"https://api.elevenlabs.io/v1/voices/{voice_id}"
        try:
            response = requests.delete(url, headers=headers)
            response.raise_for_status() # Check for HTTP errors (4xx, 5xx)
            data = response.json()
            if data.get('status') == 'ok':
                return True
            else:
                error_detail = data.get('detail', {}).get('message', 'Unknown error from API')
                raise RuntimeError(f"API reported failure: {error_detail}")

        except requests.exceptions.RequestException as e:
            error_msg = f"Network or API error: {e}"
            if e.response is not None:
                 error_msg += f" (Status Code: {e.response.status_code})"
                 try:
                     error_detail = e.response.json().get('detail', {}).get('message', '')
                     if error_detail: error_msg += f" - {error_detail}"
                 except json.JSONDecodeError:
                     pass
            raise ConnectionError(error_msg) from e
        except Exception as e: # Catch other potential errors
            raise RuntimeError(f"An unexpected error occurred during deletion: {e}") from e

    def on_voice_deleted(self, future, deleted_index, deleted_voice_id):
        """Callback executed when voice deletion attempt is complete."""
        if self.progress_dialog:
            wx.CallAfter(self.progress_dialog.Destroy)
        self.list_ctrl.Enable()

        try:
            success = future.result() # Will re-raise exception if one occurred
            if success:
                wx.CallAfter(wx.MessageBox, "Voice deleted successfully.", "Success", wx.OK | wx.ICON_INFORMATION, self)
                current_index = -1
                for i, voice in enumerate(self.all_voices):
                    if voice.get('voice_id') == deleted_voice_id:
                        current_index = i
                        break

                if current_index != -1:
                    del self.all_voices[current_index]
                    wx.CallAfter(self.populate_list_ctrl)
                else:
                    wx.CallAfter(self.populate_list_ctrl)

            else:
                # This case might not be reachable if worker raises exceptions for failures
                wx.CallAfter(wx.MessageBox, "Voice deletion failed. API did not report success.", "Deletion Failed", wx.OK | wx.ICON_ERROR, self)
                wx.CallAfter(self.check_selection_and_enable_buttons)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Failed to delete voice:\n{e}", "Deletion Error", wx.OK | wx.ICON_ERROR, self)
            # Re-enable buttons if deletion failed but item still exists
            wx.CallAfter(self.check_selection_and_enable_buttons)

    def check_selection_and_enable_buttons(self):
        """Checks if an item is selected and enables buttons accordingly."""
        if self.selected_list_index != -1 and self.selected_voice_id:
             self.edit_button.Enable()
             self.delete_button.Enable()
        else:
             self.edit_button.Disable()
             self.delete_button.Disable()

    def on_list_item_selected(self, event):
        self.selected_list_index = event.GetIndex()
        # Find the actual voice_id based on the sorted list's current index
        if 0 <= self.selected_list_index < len(self.all_voices):
            self.selected_voice_id = self.all_voices[self.selected_list_index].get('voice_id')
            self.edit_button.Enable()
            self.preview_button.Enable()
            self.delete_button.Enable()
        else: # Should not happen if list is populated, but be safe
            self.selected_voice_id = None
            self.edit_button.Disable()
            self.preview_button.Disable()
            self.delete_button.Disable()
        event.Skip()

    def on_list_item_deselected(self, event):
        self.selected_list_index = -1
        self.selected_voice_id = None
        self.edit_button.Disable()
        self.preview_button.Disable()
        self.delete_button.Disable()
        event.Skip()

    def load_voices(self):
        """Initiates fetching voices in a background thread."""
        self.progress_dialog = wx.GenericProgressDialog(
            "Loading Voices", "Fetching voice data from ElevenLabs...",
            parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        self.progress_dialog.Show()
        self.future = self.executor.submit(self.fetch_all_voices_worker)
        self.future.add_done_callback(self.on_voices_loaded)

    def fetch_all_voices_worker(self):
        """Worker thread function to fetch all voices, handling pagination."""
        voices = []
        page_size = 100
        next_page_token = None
        headers = {'xi-api-key': self.api_key}
        url = "https://api.elevenlabs.io/v2/voices"
        page_count = 0

        while True:
            page_count += 1
            params = {'page_size': page_size}
            if next_page_token:
                params['next_page_token'] = next_page_token

            # Update progress dialog message (safely using CallAfter)
            wx.CallAfter(self.progress_dialog.Pulse, f"Fetching page {page_count}...")

            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                page_voices = data.get('voices', [])
                if not page_voices:
                    break

                voices.extend(page_voices)

                next_page_token = data.get('next_page_token')
                if not next_page_token:
                    break

            except requests.exceptions.RequestException as e:
                raise ConnectionError(f"Network error fetching voices: {e}") from e
            except json.JSONDecodeError as e:
                raise ValueError(f"Error decoding API response: {e}") from e
            except Exception as e:
                raise RuntimeError(f"An unexpected error occurred: {e}") from e

        # Sort voices alphabetically by name (case-insensitive)
        voices.sort(key=lambda voice: voice.get('name', '').lower())
        return voices

    def on_voices_loaded(self, future):
        """Callback executed when voice fetching is complete."""
        wx.CallAfter(self.progress_dialog.Destroy)

        try:
            self.all_voices = future.result()
            wx.CallAfter(self.populate_list_ctrl)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Failed to load voices:\n{e}", "Error", wx.OK | wx.ICON_ERROR, self)

    def populate_list_ctrl(self):
        """Populates the list control with the fetched voice data."""
        self.list_ctrl.DeleteAllItems()
        self.selected_list_index = -1
        self.selected_voice_id = None

        if not self.all_voices:
            index = self.list_ctrl.InsertItem(0, "No voices found.")
            self.list_ctrl.SetItemTextColour(index, wx.Colour("gray"))
            return

        for index, voice in enumerate(self.all_voices):
            name = voice.get('name', 'N/A')
            category = voice.get('category', 'N/A')
            description = voice.get('description', '')
            if description is None: description = ''

            # Insert item and set column data
            self.list_ctrl.InsertItem(index, name)
            self.list_ctrl.SetItem(index, 1, category)
            self.list_ctrl.SetItem(index, 2, description)
        self.list_ctrl.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        self.list_ctrl.SetColumnWidth(1, wx.LIST_AUTOSIZE)
        self.list_ctrl.SetColumnWidth(2, wx.LIST_AUTOSIZE_USEHEADER)

    def on_close(self, event):
        """Closes the dialog and shuts down the executor."""
        self.executor.shutdown(wait=False) # Don't block UI if threads are still running unexpectedly
        self.Destroy()

    def __del__(self):
        if hasattr(self, 'executor') and self.executor:
            if not self.executor._shutdown:
                self.executor.shutdown(wait=False)
