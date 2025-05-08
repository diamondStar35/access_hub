import wx
import wx.adv
import json
import os
from gui.dialogs import MultilineTextEditDialog
from speech import speak


class NewElementDialog(wx.Dialog):
    """Dialog for entering a new key-value pair for a dictionary."""
    def __init__(self, parent, title="Add New Element"):
        super().__init__(parent, title=title, size=(300, 200))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        key_sizer = wx.BoxSizer(wx.HORIZONTAL)
        key_label = wx.StaticText(panel, label="Key:")
        self.key_text = wx.TextCtrl(panel)
        key_sizer.Add(key_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        key_sizer.Add(self.key_text, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(key_sizer, 0, wx.EXPAND | wx.ALL, 5)

        value_sizer = wx.BoxSizer(wx.HORIZONTAL)
        value_label = wx.StaticText(panel, label="Value (JSON/Python literal):")
        self.value_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        value_sizer.Add(value_label, 0, wx.ALIGN_TOP | wx.ALL, 5)
        value_sizer.Add(self.value_text, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(value_sizer, 1, wx.EXPAND | wx.ALL, 5)


        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 10)

        panel.SetSizer(vbox)
        self.Layout()
        self.Centre()

    def GetValues(self):
        """Returns the entered key and value string."""
        return self.key_text.GetValue(), self.value_text.GetValue()


class JsonViewer(wx.Frame):
    def __init__(self, *args, filepath=None, **kw):
        super(JsonViewer, self).__init__(*args, **kw)
        self.json_data = None
        self.original_json_data = None
        self.file_path = ""
        self.SetBackgroundColour(wx.Colour(240, 240, 240))
        self.InitUI()
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        if filepath and os.path.exists(filepath):
            self.LoadJsonFile(filepath)
        elif filepath: # Filepath provided but doesn't exist
            wx.CallAfter(wx.MessageBox, f"File not found: {filepath}", "Error", wx.OK | wx.ICON_ERROR, self)
            self._reset_state()


    @property
    def is_dirty(self):
        if self.json_data is None and self.original_json_data is None:
            return False
        if self.json_data is None or self.original_json_data is None:
            return True # One is None, the other isn't, so they are different

        try:
            return json.dumps(self.json_data, sort_keys=True, ensure_ascii=False) != \
                   json.dumps(self.original_json_data, sort_keys=True, ensure_ascii=False)
        except TypeError:
            return True

    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        file_path_sizer = wx.BoxSizer(wx.HORIZONTAL)
        file_path_label = wx.StaticText(panel, label="File:")
        self.file_path_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_NO_VSCROLL)
        self.file_path_text.SetValue("No file loaded")
        file_path_sizer.Add(file_path_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)
        file_path_sizer.Add(self.file_path_text, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        vbox.Add(file_path_sizer, 0, wx.EXPAND | wx.ALL, 10)

        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.json_tree = wx.TreeCtrl(panel, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT)
        self.json_tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnTreeSelChanged)
        self.json_tree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnModifySelected)
        content_sizer.Add(self.json_tree, 1, wx.EXPAND | wx.ALL, 10)

        self.list_items_listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.list_items_listbox.Bind(wx.EVT_LISTBOX_DCLICK, self.OnListboxDClick)
        content_sizer.Add(self.list_items_listbox, 1, wx.EXPAND | wx.ALL, 10)

        vbox.Add(content_sizer, 1, wx.EXPAND | wx.ALL, 0)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        open_btn = wx.Button(panel, label="Open File...")
        open_btn.Bind(wx.EVT_BUTTON, self.OnOpenFile)
        button_sizer.Add(open_btn, 0, wx.ALL, 5)

        self.copy_selected_btn = wx.Button(panel, label="Copy Element")
        self.copy_selected_btn.Bind(wx.EVT_BUTTON, self.OnCopySelected)
        button_sizer.Add(self.copy_selected_btn, 0, wx.ALL, 5)

        self.copy_value_btn = wx.Button(panel, label="Copy Value")
        self.copy_value_btn.Bind(wx.EVT_BUTTON, self.OnCopyValue)
        button_sizer.Add(self.copy_value_btn, 0, wx.ALL, 5)

        self.modify_btn = wx.Button(panel, label="Modify Value")
        self.modify_btn.Bind(wx.EVT_BUTTON, self.OnModifySelected)
        button_sizer.Add(self.modify_btn, 0, wx.ALL, 5)

        self.new_element_btn = wx.Button(panel, label="New Element")
        self.new_element_btn.Bind(wx.EVT_BUTTON, self.OnNewElement)
        button_sizer.Add(self.new_element_btn, 0, wx.ALL, 5)

        self.save_btn = wx.Button(panel, label="Save")
        self.save_btn.Bind(wx.EVT_BUTTON, self.OnSave)
        button_sizer.Add(self.save_btn, 0, wx.ALL, 5)

        close_btn = wx.Button(panel, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, self.OnClose)
        button_sizer.Add(close_btn, 0, wx.ALL, 5)

        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 10)

        panel.SetSizer(vbox)
        self.SetSize((800, 600))
        self.Centre()

        self._enable_buttons(False)

    def _enable_buttons(self, enable=True):
        self.copy_selected_btn.Enable(enable)
        self.copy_value_btn.Enable(enable)
        self.modify_btn.Enable(enable)
        self.new_element_btn.Enable(enable)
        self.save_btn.Enable(enable and self.json_data is not None and self.is_dirty)

        if not enable:
             self.copy_selected_btn.Enable(False)
             self.copy_value_btn.Enable(False)
             self.modify_btn.Enable(False)
             self.new_element_btn.Enable(False)

    def OnOpenFile(self, event):
        if self.json_data is not None and self.is_dirty:
            confirm_result = wx.MessageBox(
                "You have unsaved changes. Do you want to save before opening a new file?",
                "Unsaved Changes",
                wx.YES_NO | wx.CANCEL | wx.ICON_WARNING,
                parent=self
            )
            if confirm_result == wx.YES:
                if not self.OnSave(None):
                    return
            elif confirm_result == wx.CANCEL:
                return

        with wx.FileDialog(self, "Open JSON File", wildcard="JSON files (*.json)|*.json|All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            path = fileDialog.GetPath()
            self.LoadJsonFile(path)

    def LoadJsonFile(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.json_data = json.load(f)
                self.original_json_data = json.loads(json.dumps(self.json_data))
                self.file_path = path
                self.file_path_text.SetValue(self.file_path)
                self.DisplayJsonInTree()
                self._enable_buttons(True)
                speak(f"Successfully loaded '{os.path.basename(path)}'.")
        except FileNotFoundError:
            wx.MessageBox(f"File not found at '{path}'.", "Error Loading File", wx.OK | wx.ICON_ERROR, parent=self)
            self._reset_state()
        except json.JSONDecodeError as e:
            wx.MessageBox(f"Error decoding JSON in file '{path}':\n{e}", "JSON Error", wx.OK | wx.ICON_ERROR, parent=self)
            self._reset_state()
        except Exception as e:
            wx.MessageBox(f"An unexpected error occurred while loading '{path}':\n{e}", "Error", wx.OK | wx.ICON_ERROR, parent=self)
            self._reset_state()

    def _reset_state(self):
         self.json_data = None
         self.original_json_data = None
         self.file_path = ""
         self.file_path_text.SetValue("No file loaded")
         self.json_tree.DeleteAllItems()
         self.list_items_listbox.Clear()
         self._enable_buttons(False)

    def DisplayJsonInTree(self):
        self.json_tree.DeleteAllItems()
        self.list_items_listbox.Clear()

        if self.json_data is None:
            return

        root = self.json_tree.AddRoot("JSON Data")

        if isinstance(self.json_data, (dict, list)):
             self.json_tree.SetItemData(root, [])
             self._build_tree(root, self.json_data, [])
        else:
             self.json_tree.SetItemData(root, [])
             item = self.json_tree.AppendItem(root, repr(self.json_data))
             self.json_tree.SetItemData(item, [])

        self.json_tree.ExpandAll()
        self._enable_buttons(True)

    def _build_tree(self, parent_item, data, current_path):
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = current_path + [key]
                display_text = f"{key}: {type(value).__name__}"
                item = self.json_tree.AppendItem(parent_item, display_text)
                self.json_tree.SetItemData(item, new_path)

                if isinstance(value, (dict, list)):
                    self._build_tree(item, value, new_path)
                else:
                    value_display = repr(value)
                    value_item = self.json_tree.AppendItem(item, value_display)
                    self.json_tree.SetItemData(value_item, new_path)

        elif isinstance(data, list):
            for index, value in enumerate(data):
                new_path = current_path + [index]
                display_text = f"[{index}]: {type(value).__name__}"
                item = self.json_tree.AppendItem(parent_item, display_text)
                self.json_tree.SetItemData(item, new_path)

                if isinstance(value, (dict, list)):
                     self._build_tree(item, value, new_path)
                else:
                    value_display = repr(value)
                    value_item = self.json_tree.AppendItem(item, value_display)
                    self.json_tree.SetItemData(value_item, new_path)

    def OnTreeSelChanged(self, event):
        item = event.GetItem()
        self.list_items_listbox.Clear()
        self._enable_buttons(True)

        if item is None or not item.IsOk():
            if self.list_items_listbox.GetSelection() == wx.NOT_FOUND and self.json_data is None:
                 self._enable_buttons(False)
            return

        path, current_data, display_text, source = self._get_selected_item_context()

        self.copy_selected_btn.Enable(True)
        self.copy_value_btn.Enable(True)
        self.modify_btn.Enable(False)
        self.new_element_btn.Enable(False)
        self.save_btn.Enable(self.json_data is not None and self.is_dirty)

        if source == 'tree':
             if isinstance(current_data, dict):
                  self.new_element_btn.Enable(True)
             elif isinstance(current_data, list):
                  self.new_element_btn.Enable(True)
                  self.list_items_listbox.Clear()
                  for index, item_value in enumerate(current_data):
                       list_item_text = f"[{index}]: {repr(item_value)}"
                       self.list_items_listbox.Append(list_item_text, clientData=(path, index))
             elif not isinstance(current_data, (dict, list)):
                  self.modify_btn.Enable(True)
        elif source == 'root':
             if isinstance(self.json_data, (dict, list)):
                 self.new_element_btn.Enable(True)
             else:
                 self.modify_btn.Enable(True)

        self.save_btn.Enable(self.json_data is not None and self.is_dirty)

    def _navigate_path(self, data, path):
        try:
            current = data
            for step in path:
                current = current[step]
            return current
        except (KeyError, IndexError, TypeError):
            return None

    def _set_value_at_path(self, data, path, value):
        if not path:
             return False

        try:
            current = data
            for step in path[:-1]:
                 current = current[step]
            last_step = path[-1]
            current[last_step] = value
            return True
        except (KeyError, IndexError, TypeError):
            print(f"Error setting value at path {path}")
            return False

    def _get_selected_item_context(self):
        selected_list_index = self.list_items_listbox.GetSelection()

        if selected_list_index != wx.NOT_FOUND:
            client_data = self.list_items_listbox.GetClientData(selected_list_index)
            if client_data and isinstance(client_data, tuple) and len(client_data) == 2:
                 list_path, item_index = client_data
                 try:
                     list_data = self._navigate_path(self.json_data, list_path)
                     if list_data is not None and isinstance(list_data, list) and 0 <= item_index < len(list_data):
                         item_value = list_data[item_index]
                         full_path = list_path + [item_index]
                         display_text = self.list_items_listbox.GetString(selected_list_index)
                         return full_path, item_value, display_text, 'listbox'
                 except Exception as e:
                      print(f"Error retrieving listbox item data: {e}")
            return None, None, None, None

        else:
            selected_tree_item = self.json_tree.GetSelection()
            if selected_tree_item and selected_tree_item.IsOk():
                 path = self.json_tree.GetItemData(selected_tree_item)

                 if path is None:
                      if self.json_data is not None:
                          # If root data is simple value, the path [] refers to the value itself
                          if not isinstance(self.json_data, (dict, list)):
                                return [], self.json_data, self.json_tree.GetItemText(selected_tree_item), 'tree'
                          # If root data is dict/list, path [] refers to the collection
                          return [], self.json_data, self.json_tree.GetItemText(selected_tree_item), 'root'
                      else:
                           return None, None, None, None

                 try:
                     current_value = self._navigate_path(self.json_data, path)
                     display_text = self.json_tree.GetItemText(selected_tree_item)
                     return path, current_value, display_text, 'tree'

                 except Exception as e:
                      print(f"Error retrieving tree item data: {e}")
                      return None, None, None, None
            else:
                return None, None, None, None

    def OnListboxDClick(self, event):
        self.OnModifySelected(event)

    def OnCopySelected(self, event):
        path, value, display_text, source = self._get_selected_item_context()
        if display_text is not None:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(display_text))
                wx.TheClipboard.Close()
                speak("Element display text copied to clipboard.")
            else:
                 wx.MessageBox("Could not open clipboard.", "Error", wx.OK | wx.ICON_ERROR, parent=self)
        else:
            wx.MessageBox("Please select an element to copy.", "No Selection", wx.OK | wx.ICON_WARNING, parent=self)

    def OnCopyValue(self, event):
        path, value, display_text, source = self._get_selected_item_context()
        if value is not None:
            value_to_copy = repr(value)
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(value_to_copy))
                wx.TheClipboard.Close()
                speak("Value copied to clipboard.")
            else:
                 wx.MessageBox("Could not open clipboard.", "Error", wx.OK | wx.ICON_ERROR, parent=self)
        else:
            wx.MessageBox("Please select an element to copy its value.", "No Selection", wx.OK | wx.ICON_WARNING, parent=self)

    def OnModifySelected(self, event):
        path, current_value, display_text, source = self._get_selected_item_context()

        if path is None and source != 'root':
            wx.MessageBox("Please select an element to modify.", "No Selection", wx.OK | wx.ICON_WARNING, parent=self)
            return

        is_tree_value_leaf = (source == 'tree' and not isinstance(current_value, (dict, list)) and path != []) or (source == 'tree' and path == [] and not isinstance(current_value, (dict, list)))
        is_listbox_item = source == 'listbox'

        if not is_tree_value_leaf and not is_listbox_item:
             wx.MessageBox("Cannot modify this type of element. Select a simple value in the tree or an item in the listbox.", "Modification Error", wx.OK | wx.ICON_WARNING, parent=self)
             return

        with MultilineTextEditDialog(self, f"Modify Value for '{display_text}'", repr(current_value)) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                new_value_str = dlg.GetValue()
                try:
                    new_value = eval(new_value_str)

                    if source == 'listbox':
                         list_path, item_index = self.list_items_listbox.GetClientData(self.list_items_listbox.GetSelection())
                         list_data = self._navigate_path(self.json_data, list_path)
                         if list_data is not None and isinstance(list_data, list) and 0 <= item_index < len(list_data):
                              list_data[item_index] = new_value
                              self.is_dirty = True
                              self.DisplayJsonInTree()
                              speak("Element modified.")
                         else:
                              wx.MessageBox("Could not find the parent list to modify.", "Modification Error", wx.OK | wx.ICON_ERROR, parent=self)

                    elif source == 'tree':
                         if path == []:
                             self.json_data = new_value
                             self.is_dirty = True
                             self.DisplayJsonInTree()
                             speak("Root value modified.")
                         # If it's a nested simple value leaf, path is non-empty
                         elif self._set_value_at_path(self.json_data, path, new_value):
                              self.is_dirty = True
                              self.DisplayJsonInTree()
                              speak("Element modified.")
                         else:
                             wx.MessageBox("Failed to modify element.", "Modification Error", wx.OK | wx.ICON_ERROR, parent=self)
                except (SyntaxError, NameError, ValueError, TypeError) as e:
                    wx.MessageBox(f"Invalid input. Could not interpret as a JSON/Python literal:\n{e}", "Modification Error", wx.OK | wx.ICON_ERROR, parent=self)
                except Exception as e:
                    wx.MessageBox(f"An unexpected error occurred during modification:\n{e}", "Error", wx.OK | wx.ICON_ERROR, parent=self)


    def OnNewElement(self, event):
        path, current_context_data, display_text, source = self._get_selected_item_context()

        target_collection = None
        target_path = None

        if path is None and source == 'root' and isinstance(self.json_data, (dict, list)):
             target_collection = self.json_data
             target_path = []
        elif source == 'tree' and isinstance(current_context_data, (dict, list)):
             target_collection = current_context_data
             target_path = path
        elif self.json_data is None:
             choice = wx.MessageBox("No data loaded. Do you want to create a new JSON Object ({}) or Array ([])?",
                                   "Create New JSON",
                                   wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION | wx.YES_DEFAULT,
                                   parent=self)
             if choice == wx.YES:
                 self.json_data = {}
                 speak("Creating new JSON object.")
             elif choice == wx.NO:
                 self.json_data = []
                 speak("Creating new JSON array.")
             else:
                 return

             self.original_json_data = json.loads(json.dumps(self.json_data))
             self.is_dirty = True
             self._enable_buttons(True)
             target_collection = self.json_data
             target_path = []
        else:
            wx.MessageBox("Select a dictionary or list node (or open a file) to add a new element.", "Action Not Supported", wx.OK | wx.ICON_WARNING, parent=self)
            return

        if isinstance(target_collection, dict):
            with NewElementDialog(self) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    new_key_str, new_value_str = dlg.GetValues()
                    new_key_str = new_key_str.strip()
                    if not new_key_str:
                        wx.MessageBox("Key cannot be empty.", "Input Error", wx.OK | wx.ICON_WARNING, parent=self)
                        return
                    if new_key_str in target_collection:
                        wx.MessageBox(f"Key '{new_key_str}' already exists. Use Modify to change its value.", "Input Error", wx.OK | wx.ICON_WARNING, parent=self)
                        return
                    try:
                        new_value = eval(new_value_str)
                        target_collection[new_key_str] = new_value
                        self.is_dirty = True
                        self.DisplayJsonInTree()
                        speak(f"New element with key '{new_key_str}' added.")
                    except (SyntaxError, NameError, ValueError, TypeError) as e:
                        wx.MessageBox(f"Invalid value input. Could not interpret as a JSON/Python literal:\n{e}", "Input Error", wx.OK | wx.ICON_ERROR, parent=self)
                    except Exception as e:
                        wx.MessageBox(f"An unexpected error occurred adding element:\n{e}", "Error", wx.OK | wx.ICON_ERROR, parent=self)

        elif isinstance(target_collection, list):
            with MultilineTextEditDialog(self, "Enter New Value (JSON/Python literal)") as dlg:
                 if dlg.ShowModal() == wx.ID_OK:
                    new_value_str = dlg.GetValue()
                    try:
                        new_value = eval(new_value_str)
                        target_collection.append(new_value)
                        self.is_dirty = True
                        self.DisplayJsonInTree()
                        speak("New element appended to list.")
                    except (SyntaxError, NameError, ValueError, TypeError) as e:
                        wx.MessageBox(f"Invalid value input. Could not interpret as a JSON/Python literal:\n{e}", "Input Error", wx.OK | wx.ICON_ERROR, parent=self)
                    except Exception as e:
                        wx.MessageBox(f"An unexpected error occurred adding element:\n{e}", "Error", wx.OK | wx.ICON_ERROR, parent=self)

        else:
            wx.MessageBox("Cannot add element to this data type.", "Action Not Supported", wx.OK | wx.ICON_WARNING, parent=self)

    def OnSave(self, event):
        if self.json_data is None:
            wx.MessageBox("No data to save.", "Nothing to Save", wx.OK | wx.ICON_INFORMATION, parent=self)
            return False

        path_to_save = self.file_path

        if not path_to_save:
            with wx.FileDialog(self, "Save JSON File", wildcard="JSON files (*.json)|*.json|All files (*.*)|*.*",
                               style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:

                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return False

                path_to_save = fileDialog.GetPath()
                if not path_to_save.lower().endswith('.json'):
                    path_to_save += '.json'

        try:
            with open(path_to_save, 'w', encoding='utf-8') as f:
                json.dump(self.json_data, f, indent=4)
            self.file_path = path_to_save
            self.original_json_data = json.loads(json.dumps(self.json_data))
            self.file_path_text.SetValue(self.file_path)
            wx.MessageBox(f"Successfully saved '{os.path.basename(path_to_save)}'.", "Save Success", wx.OK | wx.ICON_INFORMATION, parent=self)
            speak("File saved.")
            self._enable_buttons(True)
            return True
        except IOError as e:
            wx.MessageBox(f"Error saving file '{path_to_save}':\n{e}", "Save Error", wx.OK | wx.ICON_ERROR, parent=self)
            return False
        except Exception as e:
            wx.MessageBox(f"An unexpected error occurred during save:\n{e}", "Error", wx.OK | wx.ICON_ERROR, parent=self)
            return False

    def OnClose(self, event):
        if self.json_data is not None and self.is_dirty:
            confirm_result = wx.MessageBox(
                "You have unsaved changes. Do you want to save before closing?",
                "Unsaved Changes",
                wx.YES_NO | wx.CANCEL | wx.ICON_WARNING,
                parent=self
            )
            if confirm_result == wx.YES:
                if self.OnSave(None):
                    event.Skip()
                else:
                    event.Veto()
            elif confirm_result == wx.NO:
                event.Skip()
            else:
                event.Veto()
        else:
            event.Skip()