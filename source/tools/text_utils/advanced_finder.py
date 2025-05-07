import wx
from gui.dialogs import MultilineTextEditDialog, ReplacementEntryDialog
from speech import speak
import uuid
import os
import shutil
import re
import threading


class ModifiedTextsViewerDialog(wx.Dialog):
    def __init__(self, parent, title="Modified Text Inputs", modified_texts_map=None):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetSize((600, 400))
        self.modified_texts_map = modified_texts_map

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(panel)
        if not modified_texts_map:
            # Should not happen if dialog is called correctly, but handle gracefully
            no_items_panel = wx.Panel(self.notebook)
            no_items_sizer = wx.BoxSizer(wx.VERTICAL)
            no_items_lbl = wx.StaticText(no_items_panel, label="No text inputs were modified or provided.")
            no_items_sizer.Add(no_items_lbl, 0, wx.ALL | wx.ALIGN_CENTER, 20)
            no_items_panel.SetSizer(no_items_sizer)
            self.notebook.AddPage(no_items_panel, "Info")
        else:
            for display_name, content in self.modified_texts_map.items():
                page_panel = wx.Panel(self.notebook)
                page_sizer = wx.BoxSizer(wx.VERTICAL)
                text_ctrl = wx.TextCtrl(page_panel, value=content, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.VSCROLL)
                page_sizer.Add(text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
                
                copy_btn = wx.Button(page_panel, label=f"Copy Content of '{display_name}'")
                copy_btn.Bind(wx.EVT_BUTTON, lambda evt, tc=text_ctrl, dn=display_name: self.OnCopyContent(evt, tc, dn))
                page_sizer.Add(copy_btn, 0, wx.ALIGN_CENTER | wx.ALL, 5)

                page_panel.SetSizer(page_sizer)
                self.notebook.AddPage(page_panel, display_name)        
        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        close_button = wx.Button(panel, wx.ID_CLOSE)
        sizer.Add(close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)
        self.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK), id=wx.ID_CLOSE)

    def OnCopyContent(self, event, text_ctrl, display_name):
        content = text_ctrl.GetValue()
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(content))
            wx.TheClipboard.Close()
            speak("Copied to clipboard.")
        else:
            wx.MessageBox("Unable to open clipboard.", "Error", wx.ICON_ERROR, self)


class AdvancedFinderResultsDialog(wx.Dialog):
    COL_MATCH_TEXT = 0
    COL_REPLACEMENT = 1
    COL_STATUS = 2
    COL_SOURCE = 3
    COL_LINE_NUM = 4
    COL_ORIGINAL_LINE = 5

    def __init__(self, parent, title="Advanced Find Results", found_results=None, source_items_metadata=None):
        # found_results: list of dicts from search thread
        # source_items_metadata: list of dicts from AdvancedFinderFrame.source_items
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX)
        self.SetSize((900, 700))
        self.raw_found_results = found_results
        self.raw_source_items_metadata = source_items_metadata
        self.source_items_metadata = {item['id']: item for item in source_items_metadata}
        self.displayable_results = self._prepare_displayable_results(found_results)
        self.output_destination = ""

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        results_label = wx.StaticText(panel, label="Found matches:")
        main_sizer.Add(results_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        self.results_list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES)
        self.results_list_ctrl.InsertColumn(self.COL_MATCH_TEXT, "Found Text", width=200)
        self.results_list_ctrl.InsertColumn(self.COL_REPLACEMENT, "Replacement", width=150)
        self.results_list_ctrl.InsertColumn(self.COL_STATUS, "Status", width=100)
        self.results_list_ctrl.InsertColumn(self.COL_SOURCE, "File/Source", width=150)
        self.results_list_ctrl.InsertColumn(self.COL_LINE_NUM, "Line", width=60)
        self.results_list_ctrl.InsertColumn(self.COL_ORIGINAL_LINE, "Original Line Context", width=300)
        self._populate_results_list()
        main_sizer.Add(self.results_list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        actions_sizer = wx.BoxSizer(wx.HORIZONTAL)
        replace_selected_btn = wx.Button(panel, label="Replace Selected...")
        replace_selected_btn.Bind(wx.EVT_BUTTON, self.OnReplaceSelected)
        actions_sizer.Add(replace_selected_btn, 0, wx.ALL, 5)

        replace_all_btn = wx.Button(panel, label="Replace All Found...")
        replace_all_btn.Bind(wx.EVT_BUTTON, self.OnReplaceAll)
        actions_sizer.Add(replace_all_btn, 0, wx.ALL, 5)

        stats_btn = wx.Button(panel, label="Show Statistics...")
        stats_btn.Bind(wx.EVT_BUTTON, self.OnShowStatistics)
        actions_sizer.Add(stats_btn, 0, wx.ALL, 5)

        main_sizer.Add(actions_sizer, 0, wx.ALIGN_LEFT | wx.LEFT | wx.RIGHT, 5)

        save_group_box = wx.StaticBox(panel, label="Save Settings")
        save_sizer = wx.StaticBoxSizer(save_group_box, wx.VERTICAL)
        dest_sizer = wx.BoxSizer(wx.HORIZONTAL)
        dest_label = wx.StaticText(panel, label="Output Destination Folder:")
        dest_sizer.Add(dest_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.dest_text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        dest_sizer.Add(self.dest_text_ctrl, 1, wx.EXPAND)
        browse_btn = wx.Button(panel, label="Browse...")
        browse_btn.Bind(wx.EVT_BUTTON, self.OnBrowseDestination)
        dest_sizer.Add(browse_btn, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 5)
        save_sizer.Add(dest_sizer, 0, wx.EXPAND | wx.ALL, 5)

        save_btn = wx.Button(panel, label="Save Modified Files & Texts")
        save_btn.Bind(wx.EVT_BUTTON, self.OnSave)
        save_sizer.Add(save_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        main_sizer.Add(save_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        close_button = wx.Button(panel, wx.ID_CLOSE, "Close")
        main_sizer.Add(close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        self.Layout()
        self.Centre()
        self.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL), id=wx.ID_CLOSE)


    def _prepare_displayable_results(self, found_results):
        displayable = []
        for res in found_results:
            displayable.append({
                'result_id': uuid.uuid4(),
                'source_id': res['source_id'],
                'source_display_name': res['source_display_name'],
                'line_number': res['line_num'], # 1-based
                'original_line_content': res['line_text'],
                'match_start_char_in_line': res['match_start'], # 0-based
                'match_end_char_in_line': res['match_end'],    
                'matched_text': res['matched_text'],
                'replacement_text': None,
                'status': 'Found'
            })
        return displayable

    def _populate_results_list(self):
        self.results_list_ctrl.DeleteAllItems()
        for idx, res_item in enumerate(self.displayable_results):
            self.results_list_ctrl.InsertItem(idx, str(res_item['matched_text']))
            self.results_list_ctrl.SetItem(idx, self.COL_REPLACEMENT, str(res_item['replacement_text'] or ""))
            self.results_list_ctrl.SetItem(idx, self.COL_STATUS, res_item['status'])
            self.results_list_ctrl.SetItem(idx, self.COL_SOURCE, res_item['source_display_name'])
            self.results_list_ctrl.SetItem(idx, self.COL_LINE_NUM, str(res_item['line_number']))
            self.results_list_ctrl.SetItem(idx, self.COL_ORIGINAL_LINE, res_item['original_line_content'].strip())
            self.results_list_ctrl.SetItemData(idx, idx)

    def _update_list_item(self, list_ctrl_idx, displayable_result_item):
        self.results_list_ctrl.SetItem(list_ctrl_idx, self.COL_MATCH_TEXT, str(displayable_result_item['matched_text']))
        self.results_list_ctrl.SetItem(list_ctrl_idx, self.COL_REPLACEMENT, str(displayable_result_item['replacement_text'] or ""))
        self.results_list_ctrl.SetItem(list_ctrl_idx, self.COL_STATUS, displayable_result_item['status'])

    def OnReplaceSelected(self, event):
        selected_idx = self.results_list_ctrl.GetFirstSelected()
        if selected_idx == -1:
            wx.MessageBox("Please select an item from the list to replace.", "No Selection", wx.ICON_WARNING, self)
            return
        
        item_data_idx = self.results_list_ctrl.GetItemData(selected_idx)
        result_to_modify = self.displayable_results[item_data_idx]

        dlg = ReplacementEntryDialog(self, current_text=result_to_modify['replacement_text'] or result_to_modify['matched_text'])
        if dlg.ShowModal() == wx.ID_OK:
            replacement = dlg.GetValue()
            result_to_modify['replacement_text'] = replacement
            result_to_modify['status'] = "Pending Replace"
            self._update_list_item(selected_idx, result_to_modify)
        dlg.Destroy()

    def OnReplaceAll(self, event):
        if not self.displayable_results:
            wx.MessageBox("No items to replace.", "Empty List", wx.ICON_INFORMATION, self)
            return

        first_match_text = self.displayable_results[0]['matched_text'] if self.displayable_results else ""
        dlg = ReplacementEntryDialog(self, title="Enter Replacement Text for All Found Items", current_text=first_match_text)        
        if dlg.ShowModal() == wx.ID_OK:
            replacement = dlg.GetValue()
            confirm_dlg = wx.MessageDialog(self,
                                           f"Are you sure you want to replace all {len(self.displayable_results)} found occurrences with '{replacement}'?\nThis action will be applied in memory and can be saved later.",
                                           "Confirm Replace All",
                                           wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
            if confirm_dlg.ShowModal() == wx.ID_YES:
                for item in self.displayable_results:
                    item['replacement_text'] = replacement
                    item['status'] = "Pending Replace All"
                self._populate_results_list() # Repopulate to update all
            confirm_dlg.Destroy()
        dlg.Destroy()

    def OnBrowseDestination(self, event):
        dlg = wx.DirDialog(self, "Choose Output Destination Folder", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.output_destination = dlg.GetPath()
            self.dest_text_ctrl.SetValue(self.output_destination)
        dlg.Destroy()

    def OnSave(self, event):
        if not self.output_destination:
            wx.MessageBox("Please select an output destination folder.", "No Destination", wx.ICON_ERROR, self)
            return

        items_to_process = [item for item in self.displayable_results if item['replacement_text'] is not None]
        if not items_to_process:
            wx.MessageBox("No replacements have been specified. Nothing to save.", "No Changes", wx.ICON_INFORMATION, self)
            return

        replacements_by_source = {}
        for item in items_to_process:
            source_id = item['source_id']
            if source_id not in replacements_by_source:
                replacements_by_source[source_id] = []
            replacements_by_source[source_id].append(item)

        # Check for overwrites
        overwrite_confirmed_sources = set()

        processed_files_count = 0
        modified_text_inputs = {} # {'source_display_name': 'full_modified_content'}

        save_progress_dlg = wx.ProgressDialog(
            "Saving Files",
            "Preparing to save...",
            maximum=len(replacements_by_source),
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME
        )
        save_progress_dlg.Show()
        wx.Yield()
        
        current_source_idx = 0
        for source_id, source_replacements in replacements_by_source.items():
            current_source_idx +=1
            source_meta = self.source_items_metadata.get(source_id)
            if not source_meta:
                wx.CallAfter(wx.MessageBox, f"Could not find metadata for source ID {source_id}. Skipping.", "Save Error", wx.ICON_ERROR, self)
                wx.CallAfter(save_progress_dlg.Update, current_source_idx, f"Skipping unknown source {source_id}...")
                continue

            wx.CallAfter(save_progress_dlg.Update, current_source_idx, f"Processing: {source_meta['display_name']}")

            original_lines = []
            is_file_source = source_meta['type'] == 'file'
            
            if is_file_source:
                source_path = source_meta['path']
                try:
                    # For "large files", read line by line. UTF-8 assumed.
                    with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
                        original_lines = f.readlines()
                except Exception as e:
                    wx.CallAfter(wx.MessageBox, f"Error reading source file {source_path}:\n{e}", "Read Error", wx.ICON_ERROR, self)
                    continue
            else:
                original_lines = source_meta['content'].splitlines(True)

            replacements_by_line_num = {} # {line_num_0_based: [list_of_replacements_for_this_line]}
            for rep_item in source_replacements:
                line_num_0_based = rep_item['line_number'] - 1
                if line_num_0_based not in replacements_by_line_num:
                    replacements_by_line_num[line_num_0_based] = []
                replacements_by_line_num[line_num_0_based].append(rep_item)
            
            modified_content_lines = []
            for i, original_line in enumerate(original_lines):
                current_line = original_line
                if i in replacements_by_line_num:
                    # Sort replacements for this line by start_char in REVERSE order
                    # to avoid index shifts within the same line during replacement
                    line_replacements = sorted(replacements_by_line_num[i], key=lambda r: r['match_start_char_in_line'], reverse=True)
                    for rep in line_replacements:
                        start = rep['match_start_char_in_line']
                        end = rep['match_end_char_in_line']
                        current_line = current_line[:start] + rep['replacement_text'] + current_line[end:]
                modified_content_lines.append(current_line)
            
            if is_file_source:
                output_file_path = os.path.join(self.output_destination, source_meta['display_name'])
                
                try:
                    if shutil.disk_usage(os.path.dirname(source_path)) == shutil.disk_usage(self.output_destination) and \
                       os.path.basename(source_path) == os.path.basename(output_file_path) and \
                       source_id not in overwrite_confirmed_sources :
                        
                        confirm_ow = wx.MessageDialog(self,
                                                    f"The output destination for '{source_meta['display_name']}' is the same as the source.\n"
                                                    "This will overwrite the original file. Continue?",
                                                    "Confirm Overwrite",
                                                    wx.YES_NO | wx.ICON_WARNING | wx.NO_DEFAULT)
                        if confirm_ow.ShowModal() == wx.ID_NO:
                            confirm_ow.Destroy()
                            continue
                        confirm_ow.Destroy()
                        overwrite_confirmed_sources.add(source_id)
                except Exception as e:
                    print(f"Warning: Could not reliably perform overwrite check for {source_path} due to {e}. Proceeding with caution.")

                try:
                    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
                    with open(output_file_path, 'w', encoding='utf-8') as f_out:
                        f_out.writelines(modified_content_lines)
                    processed_files_count += 1
                except Exception as e:
                    wx.CallAfter(wx.MessageBox, f"Error writing to file {output_file_path}:\n{e}", "Write Error", wx.ICON_ERROR, self)
            else:
                modified_text_inputs[source_meta['display_name']] = "".join(modified_content_lines)
                processed_files_count += 1

        wx.CallAfter(save_progress_dlg.Destroy)

        summary_message = f"Save process completed.\n{processed_files_count} files/text inputs processed and saved to '{self.output_destination}'."
        if modified_text_inputs:
            summary_message += "\n\nSome modified text inputs are ready to be viewed/copied."        
        wx.MessageBox(summary_message, "Save Complete", wx.ICON_INFORMATION, self)

        if modified_text_inputs:
            viewer_dlg = ModifiedTextsViewerDialog(self, modified_texts_map=modified_text_inputs)
            viewer_dlg.ShowModal()
            viewer_dlg.Destroy()
        
        for item in self.displayable_results:
            if item['replacement_text'] is not None: # If it was a candidate for saving
                item['status'] = "Saved" 
        self._populate_results_list()

    def OnShowStatistics(self, event):
        """Calculates and displays search statistics."""
        total_occurrences = len(self.displayable_results)
       
        unique_source_ids_with_matches = set()
        if self.displayable_results: # or self.raw_found_results
            unique_source_ids_with_matches = set(item['source_id'] for item in self.displayable_results)        
        num_unique_sources_with_matches = len(unique_source_ids_with_matches)
        total_sources_searched = len(self.raw_source_items_metadata)

        items_pending_replace = len([
            item for item in self.displayable_results 
            if item['status'] == "Pending Replace" or item['status'] == "Pending Replace All"
        ])
        items_saved = len([item for item in self.displayable_results if item['status'] == "Saved"])
        
        # Determine how many of the originally searched sources were files vs text inputs
        num_files_searched = 0
        num_texts_searched = 0
        for item_meta in self.raw_source_items_metadata:
            if item_meta['type'] == 'file':
                num_files_searched += 1
            elif item_meta['type'] == 'text':
                num_texts_searched += 1
        
        stats_message = (
            f"Search Statistics:\n\n"
            f"Total Occurrences Found: {total_occurrences},\n"
            f"Unique Sources with Matches: {num_unique_sources_with_matches},\n\n"
            f"Total Sources Searched: {total_sources_searched},\n"
            f"  - Files Searched: {num_files_searched},\n"
            f"  - Text Inputs Searched: {num_texts_searched}\n,\n"
            f"Replacements Pending: {items_pending_replace},\n"
            f"Replacements Saved (in this session): {items_saved}.\n"
        )        
        wx.MessageBox(stats_message, "Search Statistics", wx.OK | wx.ICON_INFORMATION, self)


class AdvancedFinder(wx.Frame):
    def __init__(self, parent, title="Advanced Finder"):
        super(AdvancedFinder, self).__init__(parent, title=title, size=(700, 600))
        self.source_items = [] # List of dicts: {'id': unique, 'type': 'file'/'text', 'path_or_content': ..., 'display_name': ...}
        self.text_input_counter = 0
        self.search_thread = None

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        source_box = wx.StaticBox(panel, label="Sources")
        source_sizer = wx.StaticBoxSizer(source_box, wx.VERTICAL)

        self.source_list_box = wx.ListBox(panel, style=wx.LB_SINGLE)
        source_sizer.Add(self.source_list_box, 1, wx.EXPAND | wx.ALL, 5)

        source_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_files_btn = wx.Button(panel, label="Add Files...")
        add_files_btn.Bind(wx.EVT_BUTTON, self.OnAddFiles)
        source_buttons_sizer.Add(add_files_btn, 0, wx.RIGHT, 5)

        add_folder_btn = wx.Button(panel, label="Add Folder...")
        add_folder_btn.Bind(wx.EVT_BUTTON, self.OnAddFolder)
        source_buttons_sizer.Add(add_folder_btn, 0, wx.RIGHT, 5)

        add_text_btn = wx.Button(panel, label="Add Text...")
        add_text_btn.Bind(wx.EVT_BUTTON, self.OnAddText)
        source_buttons_sizer.Add(add_text_btn, 0, wx.RIGHT, 5)
        
        remove_selected_btn = wx.Button(panel, label="Remove Selected")
        remove_selected_btn.Bind(wx.EVT_BUTTON, self.OnRemoveSelected)
        source_buttons_sizer.Add(remove_selected_btn, 0, wx.RIGHT, 5)
        source_sizer.Add(source_buttons_sizer, 0, wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        main_sizer.Add(source_sizer, 1, wx.EXPAND | wx.ALL, 5)

        search_params_box = wx.StaticBox(panel, label="Search Parameters")
        search_params_sizer = wx.StaticBoxSizer(search_params_box, wx.VERTICAL)

        find_label = wx.StaticText(panel, label="Find what:")
        search_params_sizer.Add(find_label, 0, wx.LEFT | wx.TOP, 5)
        self.find_text_ctrl = wx.TextCtrl(panel)
        search_params_sizer.Add(self.find_text_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        self.regex_checkbox = wx.CheckBox(panel, label="Use Regular Expressions")
        search_params_sizer.Add(self.regex_checkbox, 0, wx.ALL, 5)
        main_sizer.Add(search_params_sizer, 0, wx.EXPAND | wx.ALL, 5)

        start_button = wx.Button(panel, label="Start Search")
        start_button.Bind(wx.EVT_BUTTON, self.OnStartSearch)
        main_sizer.Add(start_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        self.Layout()
        self.Centre()

    def _update_source_list_box(self):
        self.source_list_box.Clear()
        for item in self.source_items:
            self.source_list_box.Append(item['display_name'])

    def OnAddFiles(self, event):
        with wx.FileDialog(self, "Select Files", wildcard="All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            paths = fileDialog.GetPaths()
            for path in paths:
                if not any(item['type'] == 'file' and item['path'] == path for item in self.source_items):
                    item_id = str(uuid.uuid4())
                    self.source_items.append({'id': item_id, 'type': 'file', 'path': path, 'display_name': os.path.basename(path)})
            self._update_source_list_box()

    def OnAddFolder(self, event):
        with wx.DirDialog(self, "Select Folder to Add Files From", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dirDialog:
            if dirDialog.ShowModal() == wx.ID_CANCEL:
                return
            folder_path = dirDialog.GetPath()
            for root, _, files in os.walk(folder_path):
                for file in files:
                    path = os.path.join(root, file)
                    if not any(item['type'] == 'file' and item['path'] == path for item in self.source_items):
                        item_id = str(uuid.uuid4())
                        self.source_items.append({'id': item_id, 'type': 'file', 'path': path, 'display_name': os.path.basename(path)})
            self._update_source_list_box()

    def OnAddText(self, event):
        dlg = MultilineTextEditDialog(self, title="Add Text Content")
        if dlg.ShowModal() == wx.ID_OK:
            text_content = dlg.GetValue()
            if text_content:
                self.text_input_counter += 1
                item_id = str(uuid.uuid4())
                display_name = f"Text {self.text_input_counter}"
                self.source_items.append({'id': item_id, 'type': 'text', 'content': text_content, 'display_name': display_name})
                self._update_source_list_box()
        dlg.Destroy()
        
    def OnRemoveSelected(self, event):
        selected_idx = self.source_list_box.GetSelection() # Get single selection
        if selected_idx == wx.NOT_FOUND:
            wx.MessageBox("Please select an item to remove.", "No Selection", wx.ICON_WARNING, self)
            return

        del self.source_items[selected_idx]        
        self.source_list_box.Delete(selected_idx)

        # Set selection to the next item, or previous if last was removed
        count = self.source_list_box.GetCount()
        if count > 0:
            new_selection = selected_idx
            if new_selection >= count:
                new_selection = count - 1
            self.source_list_box.SetSelection(new_selection)

    def OnStartSearch(self, event):
        search_term = self.find_text_ctrl.GetValue()
        if not search_term:
            wx.MessageBox("Please enter a search term.", "Missing Input", wx.ICON_WARNING, self)
            return
        if not self.source_items:
            wx.MessageBox("Please add files or text to search in.", "No Sources", wx.ICON_WARNING, self)
            return
        if self.search_thread and self.search_thread.is_alive():
            wx.MessageBox("A search is already in progress.", "Search Active", wx.ICON_INFORMATION, self)
            return

        use_regex = self.regex_checkbox.GetValue()

        self.progress_dialog = wx.ProgressDialog(
            "Searching...",
            "Starting search...",
            maximum=len(self.source_items),
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME | wx.PD_CAN_ABORT
        )
        self.progress_dialog.Show()
        wx.Yield()

        self.search_thread = threading.Thread(target=self._perform_search_thread_task,
                                              args=(search_term, use_regex, list(self.source_items)))
        self.search_thread.daemon = True
        self.search_thread.start()

    def _perform_search_thread_task(self, search_term, use_regex, sources_to_search):
        found_results = []
        total_occurrences = 0
        search_term_lower = search_term.lower()

        for idx, source_item in enumerate(sources_to_search):
            if self.progress_dialog.WasCancelled():
                wx.CallAfter(self.progress_dialog.Destroy)
                wx.CallAfter(wx.MessageBox, "Search cancelled by user.", "Cancelled", wx.ICON_INFORMATION)
                return

            wx.CallAfter(self.progress_dialog.Update, idx,
                          f"Processing: {source_item['display_name']} ({idx+1}/{len(sources_to_search)})\nFound: {total_occurrences} occurrences.")
            
            lines = []
            try:
                if source_item['type'] == 'file':
                    with open(source_item['path'], 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                elif source_item['type'] == 'text':
                    lines = source_item['content'].splitlines(True)
            except Exception as e:
                continue 

            for line_num_1_based, original_line_text in enumerate(lines, 1):
                line_text_for_search = original_line_text
                
                try:
                    if use_regex:
                        try:
                            regex_pattern = re.compile(search_term, re.IGNORECASE) 
                        except re.error as re_compile_err:
                            wx.CallAfter(self.progress_dialog.Destroy)
                            wx.CallAfter(wx.MessageBox, f"Invalid Regular Expression: {re_compile_err}\nSearch term: '{search_term}'\nAborting search.", "Regex Pattern Error", wx.ICON_ERROR, self)
                            return

                        for match in regex_pattern.finditer(line_text_for_search):
                            total_occurrences += 1
                            found_results.append({
                                'source_id': source_item['id'],
                                'source_display_name': source_item['display_name'],
                                'line_num': line_num_1_based,
                                'match_start': match.start(),
                                'match_end': match.end(),
                                'matched_text': match.group(0), # This will be the actual text from the line
                                'line_text': original_line_text 
                            })
                    else:
                        # For non-regex, search on the lowercase version of the line
                        line_text_lower = line_text_for_search.lower()
                        start_index = 0
                        while True:
                            # Find in the lowercased line
                            pos_in_lower = line_text_lower.find(search_term_lower, start_index)
                            if pos_in_lower == -1:
                                break
                            
                            total_occurrences += 1
                            match_end_in_lower = pos_in_lower + len(search_term_lower)                            
                            original_matched_text = line_text_for_search[pos_in_lower:match_end_in_lower]

                            found_results.append({
                                'source_id': source_item['id'],
                                'source_display_name': source_item['display_name'],
                                'line_num': line_num_1_based,
                                'match_start': pos_in_lower, # Position is relative to original line
                                'match_end': match_end_in_lower,
                                'matched_text': original_matched_text, # Store the text with its original casing
                                'line_text': original_line_text
                            })
                            start_index = match_end_in_lower
                except re.error as re_err: 
                    wx.CallAfter(self.progress_dialog.Destroy)
                    wx.CallAfter(wx.MessageBox, f"Regex error during matching: {re_err}\nAborting search.", "Expression Error", wx.ICON_ERROR, self)
                    return
                except Exception as e_match:
                    print(f"Error during matching in '{source_item['display_name']}' line {line_num_1_based}: {e_match}")
                    
        wx.CallAfter(self.progress_dialog.Destroy)

        if not (hasattr(self.progress_dialog, '_cancelled') and self.progress_dialog._cancelled):
            if found_results:
                wx.CallAfter(self._show_results_dialog, found_results, list(self.source_items))
            else:
                wx.CallAfter(wx.MessageBox, "Search term not found.", "No Results", wx.ICON_INFORMATION)
        elif hasattr(self.progress_dialog, 'WasCancelled') and self.progress_dialog.WasCancelled():
             if not hasattr(self.progress_dialog, '_cancelled'):
                 self.progress_dialog._cancelled = True


    def _show_results_dialog(self, found_results, original_source_items_metadata):
        results_dlg = AdvancedFinderResultsDialog(self, found_results=found_results, source_items_metadata=original_source_items_metadata)
        results_dlg.ShowModal()
        results_dlg.Destroy()
