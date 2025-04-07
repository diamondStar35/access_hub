import wx
import concurrent.futures
import requests
import json
import os
import mimetypes

class VoiceCloningDialog(wx.Dialog):
    def __init__(self, parent, api_key):
        super().__init__(parent, title="Create Voice Clone", size=(550, 450),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.api_key = api_key
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.file_paths = []

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(panel, label="Voice Name:", size=(100,-1))
        self.name_text = wx.TextCtrl(panel)
        self.name_text.Bind(wx.EVT_TEXT, self.on_input_change) # Bind text change
        name_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        name_sizer.Add(self.name_text, 1, wx.EXPAND)
        main_sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 10)

        desc_sizer = wx.BoxSizer(wx.HORIZONTAL)
        desc_label = wx.StaticText(panel, label="Description:", size=(100,-1))
        self.description_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 60))
        desc_sizer.Add(desc_label, 0, wx.RIGHT, 5) # Align top by default
        desc_sizer.Add(self.description_text, 1, wx.EXPAND)
        main_sizer.Add(desc_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        files_label = wx.StaticText(panel, label="Audio Files:")
        main_sizer.Add(files_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.files_listbox = wx.ListBox(panel, size=(-1, 100))
        self.files_listbox.Bind(wx.EVT_LISTBOX, self.on_listbox_select)
        main_sizer.Add(self.files_listbox, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        files_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_button = wx.Button(panel, label="Add File")
        self.remove_button = wx.Button(panel, label="Remove")
        self.add_button.Bind(wx.EVT_BUTTON, self.on_add_files)
        self.remove_button.Bind(wx.EVT_BUTTON, self.on_remove_file)
        self.remove_button.Disable()

        files_button_sizer.Add(self.add_button, 0, wx.RIGHT, 5)
        files_button_sizer.Add(self.remove_button, 0)
        main_sizer.Add(files_button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.remove_noise_checkbox = wx.CheckBox(panel, label="Remove Background Noise")
        main_sizer.Add(self.remove_noise_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        action_button_sizer = wx.StdDialogButtonSizer()
        self.clone_button = wx.Button(panel, label="Clone Voice")
        self.clone_button.SetDefault()
        self.clone_button.Disable() # Initially disabled
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        self.clone_button.Bind(wx.EVT_BUTTON, self.on_clone)
        action_button_sizer.AddButton(self.clone_button)
        action_button_sizer.AddButton(cancel_button)
        action_button_sizer.Realize()

        main_sizer.AddStretchSpacer(1)
        main_sizer.Add(action_button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        self.Layout()
        self.CentreOnParent()


    def on_input_change(self, event):
        """Called when name text changes or files are added/removed."""
        self.update_clone_button_state()
        event.Skip()

    def on_add_files(self, event):
        wildcard = "Audio files (*.mp3;*.wav;*.flac;*.aac;*.ogg;*.m4a)|*.mp3;*.wav;*.flac;*.aac;*.ogg;*.m4a|All files (*.*)|*.*"
        with wx.FileDialog(self, "Select Audio Files for Cloning",
                           wildcard=wildcard,
                           style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            paths = fileDialog.GetPaths()
            added_count = 0
            for path in paths:
                if path not in self.file_paths:
                    self.file_paths.append(path)
                    self.files_listbox.Append(os.path.basename(path))
                    added_count += 1
            if added_count > 0:
                self.update_clone_button_state()

    def on_remove_file(self, event):
        """Removes the selected file from the list and internal paths."""
        selected_index = self.files_listbox.GetSelection()
        if selected_index != wx.NOT_FOUND:
            del self.file_paths[selected_index]
            self.files_listbox.Delete(selected_index)
            self.remove_button.Disable()
            self.update_clone_button_state()

    def on_listbox_select(self, event):
        """Enables the remove button when an item is selected."""
        if self.files_listbox.GetSelection() != wx.NOT_FOUND:
            self.remove_button.Enable()
        else:
            self.remove_button.Disable()
        event.Skip()

    def update_clone_button_state(self):
        """Enables the Clone button only if name is filled and files are added."""
        can_clone = bool(self.name_text.GetValue().strip() and self.file_paths)
        self.clone_button.Enable(can_clone)

    def on_clone(self, event):
        """Starts the voice cloning process."""
        name = self.name_text.GetValue().strip()
        description = self.description_text.GetValue().strip()
        remove_noise = self.remove_noise_checkbox.GetValue()
        files_to_upload = list(self.file_paths)

        if not name or not files_to_upload:
            wx.MessageBox("Please provide a voice name and add at least one audio file.",
                          "Missing Information", wx.OK | wx.ICON_WARNING, self)
            return

        self.progress_dialog = wx.ProgressDialog(
            "Cloning Voice", f"Uploading files...",
            parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        self.progress_dialog.Show()

        clone_future = self.executor.submit(self.clone_voice_worker, name, description, files_to_upload, remove_noise)
        clone_future.add_done_callback(self.on_cloning_complete)

    def clone_voice_worker(self, name, description, file_paths, remove_noise):
        url = "https://api.elevenlabs.io/v1/voices/add"
        headers = {'xi-api-key': self.api_key}
        data = {'name': name}
        if description:
            data['description'] = description
        data['remove_background_noise'] = str(remove_noise).lower()

        files_payload = []
        opened_files = []
        try:
            for f_path in file_paths:
                filename = os.path.basename(f_path)
                content_type, _ = mimetypes.guess_type(f_path)
                if content_type is None:
                    content_type = 'application/octet-stream'

                file_obj = open(f_path, 'rb')
                opened_files.append(file_obj)
                files_payload.append(('files', (filename, file_obj, content_type)))

            response = requests.post(url, headers=headers, data=data, files=files_payload)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {e}"
            if e.response is not None:
                 error_msg += f" (Status Code: {e.response.status_code})"
                 try:
                     error_detail = e.response.json().get('detail', {}).get('message', '')
                     if error_detail: error_msg += f" - {error_detail}"
                     validation_errors = e.response.json().get('detail', {}).get('validation_errors', None)
                     if validation_errors: error_msg += f"\nDetails: {validation_errors}"
                 except json.JSONDecodeError: pass # Ignore if response is not JSON
            raise ConnectionError(error_msg) from e
        except FileNotFoundError as e:
             raise FileNotFoundError(f"Could not find file to upload: {e.filename}") from e
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred during cloning: {e}") from e
        finally:
            for f_obj in opened_files:
                try:
                    f_obj.close()
                except Exception as close_err:
                    print(f"Warning: Error closing file handle: {close_err}")

    def on_cloning_complete(self, future):
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
             wx.CallAfter(self.progress_dialog.Destroy)
             self.progress_dialog = None

        try:
            result = future.result()
            voice_id = result.get('voice_id')
            if voice_id:
                wx.CallAfter(wx.MessageBox, f"Successfully added Voice '{self.name_text.GetValue()}'!\nNew Voice ID: {voice_id}",
                              "Cloning Successful", wx.OK | wx.ICON_INFORMATION, self)
                wx.CallAfter(self.EndModal, wx.ID_OK)
            else:
                # Should be caught by exceptions, but as fallback
                wx.CallAfter(wx.MessageBox, "Cloning process finished, but no Voice ID was returned by the API.",
                              "Cloning Failed", wx.OK | wx.ICON_ERROR, self)

        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Failed to clone voice:\n{e}",
                          "Cloning Error", wx.OK | wx.ICON_ERROR, self)

    def __del__(self):
        if hasattr(self, 'executor') and self.executor and not self.executor._shutdown:
             self.executor.shutdown(wait=False)
