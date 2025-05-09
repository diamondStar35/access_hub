import wx
from gui.custom_controls import CustomVirtualList
from .search_utils import SearchWorkerThread, EVT_SEARCH_PROGRESS, EVT_SEARCH_DONE
from speech import speak
import subprocess
import os
import webbrowser
import ctypes

class AdvancedSearchDialog(wx.Dialog):
    """
    A dialog for configuring and starting an advanced file search.
    Allows searching by filename/pattern (optionally regex) within
    specified drives or the entire device.
    """
    def __init__(self, parent):
        super(AdvancedSearchDialog, self).__init__(parent, title="Advanced File Search", size=(500, 280))
        self.panel = wx.Panel(self)
        self.search_thread = None
        self.progress_dialog = None

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        params_fgs = wx.FlexGridSizer(3, 2, 5, 5)
        params_fgs.AddGrowableCol(1, 1)

        params_fgs.Add(wx.StaticText(self.panel, label="File Name/Pattern:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.search_term_text = wx.TextCtrl(self.panel)
        params_fgs.Add(self.search_term_text, 1, wx.EXPAND)

        params_fgs.AddSpacer(0)
        self.use_regex_cb = wx.CheckBox(self.panel, label="Use Regular Expression")
        params_fgs.Add(self.use_regex_cb, 1, wx.EXPAND)

        params_fgs.Add(wx.StaticText(self.panel, label="Look In:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)        
        partitions = ["Entire Device"]
        partitions.extend(self.get_drives())
        
        self.look_in_combo = wx.ComboBox(self.panel, choices=partitions, style=wx.CB_READONLY)
        self.look_in_combo.SetValue("Entire Device")
        params_fgs.Add(self.look_in_combo, 1, wx.EXPAND)        
        main_sizer.Add(params_fgs, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        self.start_search_btn = wx.Button(self.panel, wx.ID_OK, label="Start Searching")
        self.start_search_btn.SetDefault()
        cancel_btn = wx.Button(self.panel, wx.ID_CANCEL)
        btn_sizer.AddButton(self.start_search_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.start_search_btn.Bind(wx.EVT_BUTTON, self.on_start_search)
        self.panel.SetSizer(main_sizer)
        self.Layout()
        self.Centre()

        self.Bind(EVT_SEARCH_PROGRESS, self.on_search_progress)
        self.Bind(EVT_SEARCH_DONE, self.on_search_done)
        self.Bind(wx.EVT_CLOSE, self.on_dialog_close)

    def get_drives(self):
        """Uses ctypes to get a list of available logical drives on Windows."""
        drives = []
        try:
            bitmask = ctypes.cdll.kernel32.GetLogicalDrives()
            for i in range(26):
                if bitmask & (1 << i):
                    drive_letter = f"{chr(65 + i)}:\\"
                    drives.append(drive_letter)
        except Exception as e:
            return []
        return drives

    def on_start_search(self, event):
        """Handles the Start Searching button click."""
        search_term = self.search_term_text.GetValue()
        if not search_term:
            wx.MessageBox("Please enter a search term.", "Input Error", wx.OK | wx.ICON_ERROR)
            return

        selected_loc = self.look_in_combo.GetValue()
        search_roots = []
        if selected_loc == "Entire Device":
            search_roots = self.get_drives()
        else:
            search_roots.append(selected_loc)
        
        if not search_roots:
            wx.MessageBox("No search location specified or found.", "Input Error", wx.OK | wx.ICON_ERROR)
            return

        use_regex = self.use_regex_cb.IsChecked()
        self.progress_dialog = wx.ProgressDialog(
            "Searching Files", "Initializing search...", maximum=100, parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME | wx.PD_CAN_ABORT | wx.PD_SMOOTH
        )
        self.progress_dialog.Show()
        self.progress_dialog.Bind(wx.EVT_UPDATE_UI, lambda evt: None)
        self.progress_dialog.Bind(wx.EVT_CLOSE, self.on_cancel_search_progress_external)

        self.search_thread = SearchWorkerThread(self, search_term, search_roots, use_regex)
        if self.search_thread.error_message:
            wx.MessageBox(self.search_thread.error_message, "Regex Error", wx.OK | wx.ICON_ERROR)
            self.on_search_cancelled_or_failed()
            return
        self.search_thread.start()

    def on_search_progress(self, event):
        """Updates the progress dialog during the search."""
        if self.progress_dialog:
            msg = f"Files Searched: {event.files_searched}, Matches Found: {event.matches_found}"
            keep_going, _ = self.progress_dialog.Pulse(msg)
            if not keep_going:
                self.on_cancel_search_progress_internal()

    def on_cancel_search_progress_external(self, event):
        """Called when user closes progress dialog directly."""
        self.on_cancel_search_progress_internal()
        if self.progress_dialog: self.progress_dialog.Destroy()
        self.progress_dialog = None
        event.Skip()

    def on_cancel_search_progress_internal(self):
        """Internal logic for cancelling search."""
        if self.search_thread and self.search_thread.is_alive():
            self.search_thread.stop()
        self.on_search_cancelled_or_failed()

    def on_search_cancelled_or_failed(self):
        """Common cleanup for cancellation or failure before results."""
        if self.progress_dialog:
            self.progress_dialog.Destroy()
            self.progress_dialog = None

    def on_search_done(self, event):
        """Handles the completion of the search thread."""
        if self.progress_dialog:
            self.progress_dialog.Destroy()
            self.progress_dialog = None

        if event.error == "Cancelled": return
        if event.error:
            wx.MessageBox(f"Search failed: {event.error}", "Search Error", wx.OK | wx.ICON_ERROR)
            return

        results = event.results
        if not results:
            wx.MessageBox("No files found matching your criteria.", "Search Complete", wx.OK | wx.ICON_INFORMATION)
        else:
            results_dialog = SearchResultsDialog(self, "Search Results", results)
            results_dialog.ShowModal()
            results_dialog.Destroy()

    def on_dialog_close(self, event):
        """Handles closing the AdvancedSearchDialog itself."""
        if self.search_thread and self.search_thread.is_alive():
            self.search_thread.stop()
        if self.progress_dialog:
            self.progress_dialog.Destroy()
            self.progress_dialog = None
        self.EndModal(wx.ID_CANCEL)


class SearchResultsDialog(wx.Dialog):
    """
    A dialog to display the results of a file search.
    Allows copying file paths or showing files in the file explorer.
    """
    def __init__(self, parent, title, results_data):
        """
        Initializes the SearchResultsDialog.

        Args:
            parent: The parent wx.Window.
            title (str): The dialog title.
            results_data (list): A list of tuples (filename, filepath, size) of search results.
        """
        super(SearchResultsDialog, self).__init__(parent, title=title, size=(700, 400))
        self.results_data = results_data

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        results_label = wx.StaticText(panel, label=f"Found {len(self.results_data)} items:")
        font = results_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        results_label.SetFont(font)
        main_sizer.Add(results_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        list_style = wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES | wx.LC_VIRTUAL
        self.results_list_ctrl = CustomVirtualList(panel, style=list_style)
        self.results_list_ctrl.InsertColumn(0, "File Name", width=200)
        self.results_list_ctrl.InsertColumn(1, "Full Path", width=350)
        self.results_list_ctrl.InsertColumn(2, "Size (Bytes)", width=100, format=wx.LIST_FORMAT_RIGHT)
        self.results_list_ctrl.SetDataSource(self.results_data, self._get_display_text_for_item)        
        main_sizer.Add(self.results_list_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        copy_path_btn = wx.Button(panel, label="Copy Path")
        show_in_folder_btn = wx.Button(panel, label="Show in Folder")
        close_btn = wx.Button(panel, wx.ID_OK, label="Close")

        btn_sizer.Add(copy_path_btn, 0, wx.ALL, 5)
        btn_sizer.Add(show_in_folder_btn, 0, wx.ALL, 5)
        btn_sizer.AddStretchSpacer(1)
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        copy_path_btn.Bind(wx.EVT_BUTTON, self.on_copy_path)
        show_in_folder_btn.Bind(wx.EVT_BUTTON, self.on_show_in_folder)
        close_btn.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_OK))

        panel.SetSizer(main_sizer)
        self.Layout()
        self.Centre()

    def _get_display_text_for_item(self, item_idx, col_idx):
        """
        Retriever function passed to VirtualListCtrl.
        Gets data from self.results_data for the given row and column.
        """
        if item_idx < 0 or item_idx >= len(self.results_data):
            return "" 

        name, path, size = self.results_data[item_idx]        
        if col_idx == 0:
            return name
        elif col_idx == 1:
            return path
        elif col_idx == 2:
            return str(size) if size != -1 else "N/A"
        return ""

    def _get_selected_path(self):
        """Gets the full path of the selected item in the list."""
        selected_index = self.results_list_ctrl.GetFirstSelected()
        if selected_index == -1:
            wx.MessageBox("Please select a file from the list first.", "No Selection", wx.OK | wx.ICON_WARNING)
            return None

        item_data_index = self.results_list_ctrl.GetItemData(selected_index)
        return self.results_data[selected_index][1]

    def on_copy_path(self, event):
        """Copies the full path of the selected item to the clipboard."""
        path = self._get_selected_path()
        if path:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(path))
                wx.TheClipboard.Close()
                speak("Path copied to clipboard.")
            else:
                wx.MessageBox("Could not open clipboard.", "Error", wx.OK | wx.ICON_ERROR)

    def on_show_in_folder(self, event):
        """Opens the folder containing the selected file in the file explorer."""
        filepath = self._get_selected_path()
        if filepath:
            try:
                subprocess.run(['explorer', '/select,', filepath], startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=subprocess.SW_HIDE))
            except subprocess.CalledProcessError as e:
                 wx.MessageBox(f"Error showing file in folder: {e}", "Error", wx.OK | wx.ICON_ERROR, self)
            except Exception as e:
                 wx.MessageBox(f"An unexpected error occurred: {e}", "Error", wx.OK | wx.ICON_ERROR, self)
