import wx
import re
import os
import platform
import shutil
import threading
import html.parser
import io


class HTMLStripper(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = io.StringIO()

    def handle_data(self, data):
        # Append text content, replacing consecutive whitespace with a single space
        # This prevents smashing words together if tags were between them.
        cleaned_data = re.sub(r'\s+', ' ', data)
        self.text.write(cleaned_data)

    def get_data(self):
        return self.text.getvalue().strip() # Strip leading/trailing whitespace from the whole output


class TextCleaner(wx.Frame):
    def __init__(self, *args, **kw):
        super(TextCleaner, self).__init__(*args, **kw)
        self.file_list = []
        self.SetBackgroundColour(wx.Colour(240, 240, 240))
        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        file_list_vbox = wx.BoxSizer(wx.VERTICAL)
        file_list_label = wx.StaticText(panel, label="Files to Process:")
        file_list_vbox.Add(file_list_label, 0, wx.TOP | wx.LEFT, 10)

        self.file_listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
        file_list_vbox.Add(self.file_listbox, 1, wx.EXPAND | wx.ALL, 10)

        file_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_files_btn = wx.Button(panel, label="Add Files...")
        add_files_btn.Bind(wx.EVT_BUTTON, self.OnAddFiles)
        file_buttons_sizer.Add(add_files_btn, 0, wx.RIGHT, 5)

        add_folders_btn = wx.Button(panel, label="Add Folder...")
        add_folders_btn.Bind(wx.EVT_BUTTON, self.OnAddFolders)
        file_buttons_sizer.Add(add_folders_btn, 0, wx.RIGHT, 5)

        remove_btn = wx.Button(panel, label="Remove Selected")
        remove_btn.Bind(wx.EVT_BUTTON, self.OnRemoveSelected)
        file_buttons_sizer.Add(remove_btn)

        file_list_vbox.Add(file_buttons_sizer, 0, wx.ALIGN_RIGHT | wx.BOTTOM | wx.RIGHT, 10)
        vbox.Add(file_list_vbox, 1, wx.EXPAND | wx.ALL, 0)

        settings_box_sizer = wx.StaticBoxSizer(wx.StaticBox(panel, wx.ID_ANY, "Cleaning Settings"), wx.VERTICAL)
        self.chk_strip_spaces = wx.CheckBox(panel, label="Remove leading/trailing spaces from lines")
        settings_box_sizer.Add(self.chk_strip_spaces, 0, wx.ALL, 5)

        chk_normalize_lines = wx.CheckBox(panel, label="Normalize line endings")
        chk_normalize_lines.Bind(wx.EVT_CHECKBOX, self.OnNormalizeLinesChecked)
        settings_box_sizer.Add(chk_normalize_lines, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)

        self.line_ending_choice = wx.ComboBox(panel, choices=["Unix (\\n)", "Mac (\\r)", "Windows (\\r\\n)"], style=wx.CB_READONLY)
        self.line_ending_choice.SetSelection(2)
        self.line_ending_choice.Disable()
        settings_box_sizer.Add(self.line_ending_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.chk_remove_comments = wx.CheckBox(panel, label="Remove comments (#, //, /* */)")
        settings_box_sizer.Add(self.chk_remove_comments, 0, wx.ALL, 5)

        self.chk_remove_html = wx.CheckBox(panel, label="Remove HTML tags")
        settings_box_sizer.Add(self.chk_remove_html, 0, wx.ALL, 5)

        self.chk_remove_duplicates = wx.CheckBox(panel, label="Remove duplicate lines")
        settings_box_sizer.Add(self.chk_remove_duplicates, 0, wx.ALL, 5)

        self.chk_remove_empty_lines = wx.CheckBox(panel, label="Remove empty lines")
        settings_box_sizer.Add(self.chk_remove_empty_lines, 0, wx.ALL, 5)
        vbox.Add(settings_box_sizer, 0, wx.EXPAND | wx.ALL, 10)

        destination_vbox = wx.BoxSizer(wx.VERTICAL)
        destination_label = wx.StaticText(panel, label="Output Destination Folder:")
        destination_vbox.Add(destination_label, 0, wx.TOP | wx.LEFT, 10)

        destination_hizer = wx.BoxSizer(wx.HORIZONTAL)
        self.destination_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        destination_hizer.Add(self.destination_text, 1, wx.EXPAND | wx.RIGHT, 5)

        browse_btn = wx.Button(panel, label="Browse...")
        browse_btn.Bind(wx.EVT_BUTTON, self.OnBrowseDestination)
        destination_hizer.Add(browse_btn)
        destination_vbox.Add(destination_hizer, 0, wx.EXPAND | wx.ALL, 10)
        vbox.Add(destination_vbox, 0, wx.EXPAND | wx.ALL, 0)

        start_btn = wx.Button(panel, label="Start Cleaning")
        start_btn.Bind(wx.EVT_BUTTON, self.OnStartCleaning)
        vbox.Add(start_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(vbox)
        self.Layout()
        self.SetSize((700, 800))
        self.Centre()


    def OnNormalizeLinesChecked(self, event):
        """Enables/disables the line ending choice based on the checkbox."""
        self.line_ending_choice.Enable(event.IsChecked())

    def OnAddFiles(self, event):
        """Opens a file dialog to add files to the list."""
        with wx.FileDialog(self, "Select Text Files", wildcard="Text files (*.txt)|*.txt|All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            paths = fileDialog.GetPaths()
            for path in paths:
                if path not in self.file_list:
                    self.file_list.append(path)
                    self.file_listbox.Append(path)

    def OnAddFolders(self, event):
        """Opens a directory dialog and adds all files recursively."""
        with wx.DirDialog(self, "Select Folder", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dirDialog:

            if dirDialog.ShowModal() == wx.ID_CANCEL:
                return

            folder_path = dirDialog.GetPath()
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_path not in self.file_list:
                        self.file_list.append(file_path)
                        self.file_listbox.Append(file_path)

    def OnRemoveSelected(self, event):
        """Removes the single selected file from the listbox and internal list."""
        selected_index = self.file_listbox.GetSelection()
        if selected_index == wx.NOT_FOUND:
            wx.MessageBox("Please select a file to remove.", "No Selection", wx.OK | wx.ICON_WARNING, parent=self)
            return

        path_to_remove = self.file_listbox.GetString(selected_index)
        if path_to_remove in self.file_list:
            self.file_list.remove(path_to_remove)
        self.file_listbox.Delete(selected_index)

        if self.file_listbox.GetCount() > 0:
            new_selection_index = min(selected_index, self.file_listbox.GetCount() - 1)
            self.file_listbox.SetSelection(new_selection_index)

    def OnBrowseDestination(self, event):
        """Opens a directory dialog to select the output destination."""
        with wx.DirDialog(self, "Select Output Folder", style=wx.DD_DEFAULT_STYLE) as dirDialog:
            if dirDialog.ShowModal() == wx.ID_CANCEL:
                return
            self.destination_text.SetValue(dirDialog.GetPath())

    def OnStartCleaning(self, event):
        """Initiates the cleaning process."""
        if not self.file_list:
            wx.MessageBox("Please add files or folders to process.", "No Files", wx.OK | wx.ICON_WARNING, parent=self)
            return

        destination_dir = self.destination_text.GetValue()
        if not destination_dir:
            wx.MessageBox("Please select an output destination folder.", "No Destination", wx.OK | wx.ICON_WARNING, parent=self)
            return

        # Check for overwrites
        overwrite_needed = False
        for file_path in self.file_list:
            source_dir = os.path.dirname(file_path)
            if os.path.abspath(source_dir) == os.path.abspath(destination_dir):
                overwrite_needed = True
                break

        if overwrite_needed:
            confirm = wx.MessageBox(
                "The output destination is the same as one or more source folders. "
                "Files will be overwritten. Continue?",
                "Overwrite Confirmation", wx.YES_NO | wx.ICON_WARNING, parent=self
            )
            if confirm == wx.NO:
                return

        # Get cleaning settings
        settings = {
            'strip_spaces': self.chk_strip_spaces.GetValue(),
            'normalize_lines': self.line_ending_choice.IsEnabled(),
            'line_ending': self.line_ending_choice.GetStringSelection() if self.line_ending_choice.IsEnabled() else platform.system(),
            'remove_comments': self.chk_remove_comments.GetValue(),
            'remove_html': self.chk_remove_html.GetValue(),
            'remove_duplicates': self.chk_remove_duplicates.GetValue(),
            'remove_empty_lines': self.chk_remove_empty_lines.GetValue(),
        }

        # Start processing with a progress dialog
        total_files = len(self.file_list)
        progress_dialog = wx.ProgressDialog(
            "Processing Files",
            f"Starting processing... 0/{total_files} files done.",
            maximum=total_files,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME
        )
        progress_dialog.Show()
        wx.Yield()

        self.cleaning_thread = threading.Thread(
            target=self._perform_cleaning_process,
            args=(self.file_list.copy(), destination_dir, settings, progress_dialog)
        )
        self.cleaning_thread.daemon = True # Allow app to exit even if thread is running
        self.cleaning_thread.start()

    def _perform_cleaning_process(self, files_to_process, destination_dir, settings, progress_dialog):
        """Worker thread function to process files."""
        total_files = len(files_to_process)
        processed_count = 0
        total_original_lines_processed = 0
        total_changes = { # Track changes across all files
            'spaces_removed': 0,
            'comments_removed': 0,
            'html_tags_removed': 0,
            'duplicate_lines_removed': 0,
            'empty_lines_removed': 0,
            'lines_removed': 0,
        }

        try:
            for file_index, source_path in enumerate(files_to_process):
                if progress_dialog.WasCancelled():
                    break

                wx.CallAfter(progress_dialog.Update, file_index + 1, f"Processing: {os.path.basename(source_path)} ({file_index + 1}/{total_files})")

                try:
                    with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
                        original_text = f.read()
                    original_file_line_count = len(original_text.splitlines())
                    total_original_lines_processed += original_file_line_count

                except Exception as e:
                    wx.CallAfter(wx.MessageBox, f"Error reading file: {os.path.basename(source_path)}\n\n{e}", "Reading Error", wx.OK | wx.ICON_ERROR, parent=self)
                    continue

                text_to_process = original_text
                current_changes = {k: 0 for k in total_changes}

                if settings['remove_comments']:
                     text_to_process, comments_count = self._remove_comments(text_to_process)
                     current_changes['comments_removed'] += comments_count

                if settings['remove_html']:
                     text_to_process, html_count = self._remove_html_tags(text_to_process)
                     current_changes['html_tags_removed'] += html_count

                lines = text_to_process.splitlines(keepends=True)
                lines_count_after_text_clean = len(lines) # Lines after text-based ops

                if settings['strip_spaces']:
                    lines, spaces_removed = self._clean_spaces(lines)
                    current_changes['spaces_removed'] += spaces_removed

                if settings['remove_empty_lines']:
                    lines, empty_removed = self._remove_empty_lines(lines)
                    current_changes['empty_lines_removed'] += empty_removed

                if settings['remove_duplicates']:
                    lines, duplicates_removed = self._remove_duplicate_lines(lines)
                    current_changes['duplicate_lines_removed'] += duplicates_removed

                # Calculate lines removed purely by line-based operations
                lines_removed_by_line_ops = lines_count_after_text_clean - len(lines)
                if lines_removed_by_line_ops < 0: lines_removed_by_line_ops = 0
                current_changes['lines_removed'] += lines_removed_by_line_ops

                for key in total_changes:
                    if key in current_changes:
                        total_changes[key] += current_changes[key]

                if settings['normalize_lines']:
                     cleaned_lines_for_write, _ = self._normalize_line_endings(lines, settings['line_ending'])
                else:
                     cleaned_lines_for_write = lines

                # Determine output path and write
                try:
                     output_path = os.path.join(destination_dir, os.path.basename(source_path))
                     output_dir = os.path.dirname(output_path)
                     if not os.path.exists(output_dir):
                         os.makedirs(output_dir)
                     with open(output_path, 'w', encoding='utf-8') as f:
                         f.writelines(cleaned_lines_for_write)
                except Exception as e:
                    wx.CallAfter(wx.MessageBox, f"Error writing file: {os.path.basename(source_path)}\n\n{e}", "Writing Error", wx.OK | wx.ICON_ERROR, parent=self)
                    continue # Skip writing this file, but it was processed

                processed_count += 1
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"An unexpected error occurred during processing:\n{e}", "Processing Error", wx.OK | wx.ICON_ERROR, parent=self)
        finally:
            if progress_dialog and progress_dialog.IsShown():
                 wx.CallAfter(progress_dialog.Destroy)

            summary_message = "Cleaning process finished.\n\nSummary of changes across processed files:"
            any_changes = False

            if total_changes['spaces_removed'] > 0:
                 summary_message += f"\n- Removed spaces from {total_changes['spaces_removed']} lines."
                 any_changes = True
            if total_changes['comments_removed'] > 0:
                 summary_message += f"\n- Removed approximately {total_changes['comments_removed']} comments."
                 any_changes = True
            if total_changes['html_tags_removed'] > 0:
                 summary_message += f"\n- Removed approximately {total_changes['html_tags_removed']} HTML tags."
                 any_changes = True
            if total_changes['duplicate_lines_removed'] > 0:
                 summary_message += f"\n- Removed {total_changes['duplicate_lines_removed']} duplicate lines."
                 any_changes = True
            if total_changes['empty_lines_removed'] > 0:
                 summary_message += f"\n- Removed {total_changes['empty_lines_removed']} empty lines."
                 any_changes = True
            if not any_changes:
                 summary_message += "\n- No cleaning options were selected, or no changes were found in the files."

            summary_message += f"\n\nTotal original lines processed: {total_original_lines_processed}"
            summary_message += f"\nTotal files processed successfully: {processed_count}/{total_files}"

            wx.CallAfter(wx.MessageBox, summary_message, "Cleaning Complete", wx.OK | wx.ICON_INFORMATION, parent=self)


    def _clean_spaces(self, lines):
        """Removes leading and trailing spaces from each line."""
        count = 0
        cleaned = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line != line.strip():
                 count += 1
            cleaned.append(stripped_line + self._get_newline_char_from_line(line))
        return cleaned, count

    def _normalize_line_endings(self, lines, target_ending_name):
        """Ensures all lines have the specified line ending."""
        target_ending = self._get_newline_char(target_ending_name)
        cleaned = []
        # count is not relevant here as it changes all lines
        for line in lines:
            line = line.rstrip('\r\n') # Remove \r\n or just \n or just \r
            cleaned.append(line + target_ending)
        return cleaned, 0

    def _get_newline_char(self, ending_name):
        """Maps line ending name to character(s)."""
        if "Unix" in ending_name:
            return '\n'
        elif "Mac" in ending_name:
            return '\r'
        elif "Windows" in ending_name:
            return '\r\n'
        return os.linesep # Default to system's native if unknown

    def _get_newline_char_from_line(self, line):
        """Detects and returns the newline character(s) from a single line."""
        if line.endswith('\r\n'):
            return '\r\n'
        elif line.endswith('\n'):
            return '\n'
        elif line.endswith('\r'):
            return '\r'
        return '' # No newline found


    def _remove_comments(self, text):
        """
        Removes various types of comments (#, //, --, /* */) from text
        with improved heuristics for quoted strings and URLs.
        Still not a full language parser and may have edge cases.
        """
        count = 0
        cleaned_text_buffer = []
        
        i = 0
        n = len(text)
        
        in_block_comment = False
        in_single_quote_string = False
        in_double_quote_string = False
        
        while i < n:
            # Handle escape characters within strings primarily
            if (in_single_quote_string or in_double_quote_string) and text[i] == '\\':
                if i + 1 < n:
                    cleaned_text_buffer.append(text[i:i+2]) # Keep escape and char after
                    i += 2
                    continue
                else: # Dangling escape at end of text
                    cleaned_text_buffer.append(text[i])
                    i += 1
                    continue

            # Toggle string states
            if text[i] == "'":
                if not in_double_quote_string: # Not allowed to toggle single inside double
                    in_single_quote_string = not in_single_quote_string
                cleaned_text_buffer.append(text[i])
                i += 1
                continue
            
            if text[i] == '"':
                if not in_single_quote_string:
                    in_double_quote_string = not in_double_quote_string
                cleaned_text_buffer.append(text[i])
                i += 1
                continue

            # If inside a string, just append characters (unless it's an escape, handled above)
            if in_single_quote_string or in_double_quote_string:
                cleaned_text_buffer.append(text[i])
                i += 1
                continue

            # Handle block comments (/* ... */)
            if not in_block_comment and i + 1 < n and text[i:i+2] == '/*':
                in_block_comment = True
                count += 1 # Count block comment start
                i += 2
                continue
            
            if in_block_comment and i + 1 < n and text[i:i+2] == '*/':
                in_block_comment = False
                i += 2
                continue
            
            if in_block_comment:
                i += 1 # Skip characters inside block comment
                continue

            # Check for '//'
            if i + 1 < n and text[i:i+2] == '//':
                # Check if it's part of a URL like http://, file://
                is_url_protocol = False
                if i > 0 and text[i-1] == ':':
                    if i > 1 and not text[i-2].isspace():
                        is_url_protocol = True
                
                if not is_url_protocol:
                    count += 1
                    # Skip to the end of the line
                    while i < n and text[i] != '\n':
                        i += 1
                    # If loop ended due to '\n', we'll append it in the next step.
                    # If loop ended due to end of text, i will be n.
                    continue
                else: # It's likely part of a URL, treat as normal text
                    cleaned_text_buffer.append(text[i:i+2])
                    i += 2
                    continue

            if text[i] == '#':
                count += 1
                while i < n and text[i] != '\n':
                    i += 1
                continue

            # Check for '--' (common in SQL, Ada, Haskell, Lua)
            if i + 1 < n and text[i:i+2] == '--':
                count += 1
                while i < n and text[i] != '\n':
                    i += 1
                continue

            # If none of the above, it's normal text
            cleaned_text_buffer.append(text[i])
            i += 1
            
        final_cleaned_text = "".join(cleaned_text_buffer)
        return final_cleaned_text, count


    def _remove_html_tags(self, text):
        """Removes HTML/XML tags using html.parser."""
        stripper = HTMLStripper()
        try:
            stripper.feed(text)
            cleaned_text = stripper.get_data()
            approx_tag_count = len(re.findall(r'<[^>]*>', text))

            return cleaned_text, approx_tag_count
        except Exception as e:
             wx.CallAfter(wx.MessageBox, f"Error parsing HTML for cleaning:\n{e}\n\nProceeding without HTML removal for this file.", "HTML Parsing Error", wx.OK | wx.ICON_WARNING, parent=self)
             return text, 0


    def _remove_duplicate_lines(self, lines):
        """Removes identical consecutive or non-consecutive duplicate lines."""
        seen_lines = set()
        cleaned = []
        removed_count = 0
        for line in lines:
             if line not in seen_lines:
                  cleaned.append(line)
                  seen_lines.add(line)
             else:
                  removed_count += 1
        return cleaned, removed_count

    def _remove_empty_lines(self, lines):
        """Removes lines that are empty or contain only whitespace."""
        cleaned = []
        removed_count = 0
        for line in lines:
            if line.strip():
                cleaned.append(line)
            else:
                removed_count += 1
        return cleaned, removed_count


    def _get_relative_path(self, base_path, full_path):
         """Calculates path of full_path relative to base_path."""
         try:
              return os.path.relpath(full_path, base_path)
         except ValueError:
              return os.path.basename(full_path) # Fallback to just filename if relative path fails
