import wx
import os
import threading

class BatchEntryDialog(wx.Dialog):
    """Dialog for adding a manual text entry."""
    def __init__(self, parent, title="Add Text Entry"):
        super().__init__(parent, title=title, size=(400, 300))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        vbox.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(panel, wx.ID_OK, "OK")
        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        hbox.Add(ok_button, 0, wx.ALL, 5)
        hbox.Add(cancel_button, 0, wx.ALL, 5)
        vbox.Add(hbox, 0, wx.ALIGN_CENTER_HORIZONTAL, 0)

        panel.SetSizer(vbox)
        self.Centre()

    def GetText(self):
        return self.text_ctrl.GetValue()

class OnlineTTSBatch(wx.Dialog):
    """Dialog for batch processing text-to-speech."""
    def __init__(self, parent, generate_speech_callback):
        super().__init__(parent, title="Batch Text-to-Speech", size=(750, 500))
        self.generate_speech_callback = generate_speech_callback
        self.entries = []
        self.progress_dlg = None
        self.thread = None

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(panel, label="Items to Convert:")
        vbox.Add(label, 0, wx.ALL, 5)

        self.list_box = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.list_box.Bind(wx.EVT_LISTBOX, self.on_listbox_select)
        vbox.Add(self.list_box, 1, wx.EXPAND | wx.ALL, 10)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.add_button = wx.Button(panel, label="Add Text")
        self.add_button.Bind(wx.EVT_BUTTON, self.on_add_text)
        hbox.Add(self.add_button, 0, wx.ALL, 5)

        self.select_files_button = wx.Button(panel, label="Select Files")
        self.select_files_button.Bind(wx.EVT_BUTTON, self.on_select_files)
        hbox.Add(self.select_files_button, 0, wx.ALL, 5)

        self.remove_button = wx.Button(panel, label="Remove")
        self.remove_button.Bind(wx.EVT_BUTTON, self.on_remove)
        self.remove_button.Disable()  # Initially disabled
        hbox.Add(self.remove_button, 0, wx.ALL, 5)

        self.generate_button = wx.Button(panel, label="Generate")
        self.generate_button.Bind(wx.EVT_BUTTON, self.on_generate)
        hbox.Add(self.generate_button, 0, wx.ALL, 5)
        vbox.Add(hbox, 0, wx.ALIGN_CENTER_HORIZONTAL, 0)
        panel.SetSizer(vbox)
        self.Centre()


    def on_listbox_select(self, event):
        """Enable/disable the Remove button based on selection."""
        if self.list_box.GetSelection() != wx.NOT_FOUND:
            self.remove_button.Enable()
        else:
            self.remove_button.Disable()

    def on_add_text(self, event):
        """Opens a dialog to add a manual text entry."""
        dlg = BatchEntryDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            text = dlg.GetText()
            if text.strip():  # Don't add empty entries
                self.entries.append(("text", text))
                self.update_listbox()
        dlg.Destroy()

    def on_select_files(self, event):
        """Opens a file dialog to select multiple files."""
        with wx.FileDialog(self, "Select Files",
                           wildcard="All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_OK:
                filepaths = fileDialog.GetPaths()
                for filepath in filepaths:
                     self.entries.append(("file", filepath))
                self.update_listbox()

    def on_remove(self, event):
        """Removes the selected entry from the list."""
        selected_index = self.list_box.GetSelection()
        if selected_index != wx.NOT_FOUND:
            del self.entries[selected_index]
            self.update_listbox()
            # Disable remove button if nothing is selected
            if not self.entries:
                self.remove_button.Disable()

    def update_listbox(self):
        """Updates the listbox with the current entries."""
        self.list_box.Clear()
        for entry_type, entry_value in self.entries:
            if entry_type == "file":
                display_text = f"File: {entry_value}"
            else:
                display_text = f"Text: {entry_value[:50]}{'...' if len(entry_value) > 50 else ''}" # Limit display length
            self.list_box.Append(display_text)

    def on_generate(self, event):
        if not self.entries:
            wx.MessageBox("No entries to process.", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        with wx.DirDialog(self, "Choose Output Directory", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dirDialog:
            if dirDialog.ShowModal() == wx.ID_CANCEL:
                return
            output_dir = dirDialog.GetPath()

        self.progress_dlg = wx.ProgressDialog("Generating Speech", "Processing...", maximum=len(self.entries), parent=self, style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_AUTO_HIDE)
        self.progress_count = 0
        self.thread = threading.Thread(target=self.run_batch_generation, args=(output_dir,))
        self.thread.start()

    def run_batch_generation(self, output_dir):
        """Performs the batch generation in a separate thread."""
        for entry_type, entry_value in self.entries:
            if self.progress_dlg.WasCancelled():
                break

            wx.CallAfter(self.progress_dlg.Update, self.progress_count + 1, f"Processing item {self.progress_count + 1} of {len(self.entries)}")
            wx.CallAfter(wx.YieldIfNeeded)

            if entry_type == "file":
                try:
                    with open(entry_value, "r", encoding="utf-8") as f:
                        text = f.read()
                    filename = os.path.splitext(os.path.basename(entry_value))[0] + ".mp3"
                except Exception as e:
                    wx.CallAfter(wx.MessageBox, f"Error reading file {entry_value}: {e}", "Error", wx.OK | wx.ICON_ERROR)
                    continue
            else:
                text = entry_value
                filename = f"output_{self.progress_count + 1}.mp3"

            output_path = os.path.join(output_dir, filename)
            success = self.generate_speech_callback(text, output_path)
            if not success:
               wx.CallAfter(wx.MessageBox, f"Failed to generate speech for: {filename}", "Error", wx.OK | wx.ICON_ERROR)
            self.progress_count += 1

        wx.CallAfter(self.progress_dlg.Destroy)
        wx.CallAfter(wx.MessageBox, "Batch processing complete!", "Success", wx.OK | wx.ICON_INFORMATION)


    def on_close(self, event):
        """Handles the dialog close event, ensuring the thread is cleaned up."""
        if self.thread and self.thread.is_alive():
            # If the thread is still running, try to cancel and wait
            if self.progress_dlg:
                self.progress_dlg.Destroy()
            self.thread.join(timeout=2) # Wait for the thread to finish.
        event.Skip()