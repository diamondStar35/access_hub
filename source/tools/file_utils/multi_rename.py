import wx
import shutil
import os
import re

class MultipleRename(wx.Frame):
    def __init__(self, parent, title):
        super(MultipleRename, self).__init__(parent, title=title, size=(700, 600))
        self.panel = wx.Panel(self)
        self.files_to_rename = []

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        list_label = wx.StaticText(self.panel, label="Files to Rename:")
        main_sizer.Add(list_label, 0, wx.LEFT | wx.TOP | wx.RIGHT, 5)
        self.file_list_box = wx.ListBox(self.panel, style=wx.LB_SINGLE)
        main_sizer.Add(self.file_list_box, 1, wx.EXPAND | wx.ALL, 5)

        list_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_files_btn = wx.Button(self.panel, label="Add Files")
        self.add_folder_btn = wx.Button(self.panel, label="Add Folder")
        self.remove_item_btn = wx.Button(self.panel, label="Remove Selected")
        list_btn_sizer.Add(self.add_files_btn, 0, wx.ALL, 5)
        list_btn_sizer.Add(self.add_folder_btn, 0, wx.ALL, 5)
        list_btn_sizer.Add(self.remove_item_btn, 0, wx.ALL, 5)
        main_sizer.Add(list_btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)

        self.add_files_btn.Bind(wx.EVT_BUTTON, self.on_add_files)
        self.add_folder_btn.Bind(wx.EVT_BUTTON, self.on_add_folder)
        self.remove_item_btn.Bind(wx.EVT_BUTTON, self.on_remove_item)

        options_fgs = wx.FlexGridSizer(4, 3, 5, 5)
        options_fgs.AddGrowableCol(1, 1)

        options_fgs.Add(wx.StaticText(self.panel, label="Search Regex (for filename part):"),
                        0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.search_regex_text = wx.TextCtrl(self.panel)
        options_fgs.Add(self.search_regex_text, 1, wx.EXPAND)
        options_fgs.AddSpacer(0)

        options_fgs.Add(wx.StaticText(self.panel, label="Replace With (can use \\1, \\2 etc.):"),
                        0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.replace_pattern_text = wx.TextCtrl(self.panel)
        options_fgs.Add(self.replace_pattern_text, 1, wx.EXPAND)
        options_fgs.AddSpacer(0)

        options_fgs.Add(wx.StaticText(self.panel, label="New Extension:"),
                        0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.new_ext_text = wx.TextCtrl(self.panel)
        options_fgs.Add(self.new_ext_text, 1, wx.EXPAND)
        options_fgs.AddSpacer(0)

        options_fgs.Add(wx.StaticText(self.panel, label="Output Folder:"),
                        0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.output_path_text = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        options_fgs.Add(self.output_path_text, 1, wx.EXPAND)
        self.browse_output_btn = wx.Button(self.panel, label="Browse...")
        options_fgs.Add(self.browse_output_btn, 0)
        self.browse_output_btn.Bind(wx.EVT_BUTTON, self.on_browse_output)

        main_sizer.Add(options_fgs, 0, wx.EXPAND | wx.ALL, 10)

        action_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_btn = wx.Button(self.panel, label="Start Renaming")
        self.close_btn = wx.Button(self.panel, label="Close")
        action_btn_sizer.Add(self.start_btn, 0, wx.ALL, 10)
        action_btn_sizer.Add(self.close_btn, 0, wx.ALL, 10)
        main_sizer.Add(action_btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.start_btn.Bind(wx.EVT_BUTTON, self.on_start_renaming)
        self.close_btn.Bind(wx.EVT_BUTTON, self.on_close_button)

        self.panel.SetSizer(main_sizer)
        self.Layout()
        self.Centre()
        self.Bind(wx.EVT_CLOSE, self.on_frame_close)

    def on_close_button(self, event):
        self.Close(True)

    def on_frame_close(self, event):
        """Handles the frame's EVT_CLOSE event."""
        parent = self.GetParent()
        if parent:
             parent.on_child_tool_close(self)
        self.Destroy()


    def _update_extension_field(self):
        if not self.files_to_rename:
            self.new_ext_text.SetValue("")
            return

        first_ext = self.files_to_rename[0][2]
        all_same_ext = all(ext.lower() == first_ext.lower() for _, _, ext in self.files_to_rename)
        
        if all_same_ext:
            self.new_ext_text.SetValue(first_ext if first_ext.startswith('.') else ('.' + first_ext if first_ext else ""))
        else:
            self.new_ext_text.SetValue("")

    def _add_file_to_list(self, filepath):
        if not any(f[0] == filepath for f in self.files_to_rename):
            basename = os.path.basename(filepath)
            name, ext = os.path.splitext(basename)
            self.files_to_rename.append((filepath, name, ext))
            self.file_list_box.Append(filepath)
            if not self.output_path_text.GetValue():
                self.output_path_text.SetValue(os.path.dirname(filepath))
            self._update_extension_field()

    def on_add_files(self, event):
        with wx.FileDialog(self, "Select files", wildcard="All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            for path in file_dialog.GetPaths():
                self._add_file_to_list(path)

    def on_add_folder(self, event):
        with wx.DirDialog(self, "Choose a folder", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dir_dialog:
            if dir_dialog.ShowModal() == wx.ID_CANCEL:
                return
            folder_path = dir_dialog.GetPath()
            if not self.output_path_text.GetValue(): # Only set if not already set or if user wants to override
                self.output_path_text.SetValue(folder_path)
            for root, _, files in os.walk(folder_path):
                for f_name in files:
                    self._add_file_to_list(os.path.join(root, f_name))

    def on_remove_item(self, event):
        selected_index = self.file_list_box.GetSelection()
        if selected_index != wx.NOT_FOUND:
            self.file_list_box.Delete(selected_index)
            del self.files_to_rename[selected_index]
            if not self.files_to_rename and self.file_list_box.IsEmpty():
                self.output_path_text.SetValue("")

    def on_browse_output(self, event):
        with wx.DirDialog(self, "Choose an output folder", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dir_dialog:
            if dir_dialog.ShowModal() == wx.ID_OK:
                self.output_path_text.SetValue(dir_dialog.GetPath())

    def on_start_renaming(self, event):
        output_folder = self.output_path_text.GetValue()
        if not output_folder or not os.path.isdir(output_folder):
            wx.MessageBox("Please select a valid output folder.", "Error", wx.OK | wx.ICON_ERROR)
            return
        if not self.files_to_rename:
            wx.MessageBox("No files to rename.", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        search_regex_str = self.search_regex_text.GetValue()
        replace_pattern_str = self.replace_pattern_text.GetValue()
        new_ext_str = self.new_ext_text.GetValue().strip()
        
        compiled_regex = None
        if search_regex_str:
            try:
                compiled_regex = re.compile(search_regex_str)
            except re.error as e:
                wx.MessageBox(f"Invalid Search Regular Expression: {e}", "Regex Error", wx.OK | wx.ICON_ERROR)
                return

        renamed_count = 0
        errors = []

        for i, (original_full_path, original_name, original_ext) in enumerate(self.files_to_rename):
            current_name_part = original_name
            current_ext_part = original_ext

            if compiled_regex and replace_pattern_str: # Regex search and replace
                current_name_part = compiled_regex.sub(replace_pattern_str, original_name)
            elif search_regex_str and not replace_pattern_str: # Only search regex (no replace pattern): name based on counter
                if '#' in search_regex_str:
                     current_name_part = search_regex_str.replace('#', f'{i + 1:03d}')
                # else: if no '#' and no replace pattern, name remains original unless ext changes
            
            if new_ext_str:
                current_ext_part = new_ext_str if new_ext_str.startswith('.') else ('.' + new_ext_str if new_ext_str else "")
            
            new_basename = current_name_part + current_ext_part
            new_full_path = os.path.join(output_folder, new_basename)
            if os.path.exists(new_full_path) and new_full_path.lower() != original_full_path.lower():
                errors.append(f"Skipped '{os.path.basename(original_full_path)}': Target '{new_basename}' already exists.")
                continue
            
            try:
                if original_full_path.lower() == new_full_path.lower():
                    if os.path.basename(original_full_path) != new_basename : # Case change only
                        temp_path = original_full_path + ".renaming_temp_case"
                        shutil.move(original_full_path, temp_path)
                        shutil.move(temp_path, new_full_path)
                        renamed_count += 1
                else:
                    shutil.move(original_full_path, new_full_path)
                    renamed_count += 1
            except Exception as e:
                errors.append(f"Error renaming '{os.path.basename(original_full_path)}' to '{new_basename}': {e}")
        
        msg = f"Successfully renamed {renamed_count} file(s)."
        if errors:
            msg += "\n\nEncountered errors/skipped files:\n" + "\n".join(errors)
       
        wx.MessageBox(msg, "Rename Complete", wx.OK | wx.ICON_INFORMATION)
        
        if renamed_count > 0 and not errors:
             self.Close(True)
