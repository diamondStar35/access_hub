import wx
from gui.dialogs import ElementEditorDialog, AttributeEditorDialog
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError
import os

# Define IDs for context menu items
ID_ADD_SIBLING_OR_TO_ROOT = wx.NewIdRef()
ID_ADD_CHILD = wx.NewIdRef()


class XMLViewer(wx.Frame):
    def __init__(self, parent, title):
        super(XMLViewer, self).__init__(parent, id=wx.ID_ANY, title=title)
        self.current_file_path = None
        self.xml_tree = None
        self.root_element = None
        self.unsaved_changes = False

        self.InitUI()
        self.UpdateTitle()
        self._update_button_states()

    def InitUI(self):
        """Initializes the user interface components of the frame."""
        panel = wx.Panel(self)
        main_vbox = wx.BoxSizer(wx.VERTICAL)

        controls_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.open_btn = wx.Button(panel, label="Open XML File...")
        self.open_btn.Bind(wx.EVT_BUTTON, self.OnOpenFile)
        controls_hbox.Add(self.open_btn, 0, wx.ALL, 5)

        self.save_btn = wx.Button(panel, label="Save")
        self.save_btn.Bind(wx.EVT_BUTTON, self.OnSaveFile)
        controls_hbox.Add(self.save_btn, 0, wx.ALL, 5)

        self.save_as_btn = wx.Button(panel, label="Save As...")
        self.save_as_btn.Bind(wx.EVT_BUTTON, self.OnSaveFileAs)
        controls_hbox.Add(self.save_as_btn, 0, wx.ALL, 5)
        main_vbox.Add(controls_hbox, 0, wx.EXPAND | wx.ALL, 5)

        xml_text_label = wx.StaticText(panel, label="XML Source:")
        main_vbox.Add(xml_text_label, 0, wx.LEFT | wx.TOP, 5)
        self.xml_display_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.VSCROLL)
        self.xml_display_ctrl.SetMinSize((-1, 150)) 
        main_vbox.Add(self.xml_display_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        tree_label = wx.StaticText(panel, label="XML Tree:")
        main_vbox.Add(tree_label, 0, wx.LEFT | wx.TOP, 5)
        self.tree_ctrl = wx.TreeCtrl(panel, style=wx.TR_DEFAULT_STYLE | wx.TR_LINES_AT_ROOT | wx.TR_HIDE_ROOT)
        self.tree_ctrl.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnTreeSelectionChanged)
        main_vbox.Add(self.tree_ctrl, 2, wx.EXPAND | wx.ALL, 5)

        edit_buttons_sizer = wx.GridBagSizer(5, 5)        
        self.add_element_btn = wx.Button(panel, label="Add Element...")
        self.add_element_btn.Bind(wx.EVT_BUTTON, self.OnShowAddElementMenu)
        edit_buttons_sizer.Add(self.add_element_btn, pos=(0,0), flag=wx.EXPAND|wx.ALL, border=2)

        self.edit_element_btn = wx.Button(panel, label="Edit Element...")
        self.edit_element_btn.Bind(wx.EVT_BUTTON, self.OnEditElement)
        edit_buttons_sizer.Add(self.edit_element_btn, pos=(0,1), flag=wx.EXPAND|wx.ALL, border=2)

        self.edit_attr_btn = wx.Button(panel, label="Edit Attributes...")
        self.edit_attr_btn.Bind(wx.EVT_BUTTON, self.OnEditAttributes)
        edit_buttons_sizer.Add(self.edit_attr_btn, pos=(1,0), flag=wx.EXPAND|wx.ALL, border=2)

        self.remove_element_btn = wx.Button(panel, label="Remove Element")
        self.remove_element_btn.Bind(wx.EVT_BUTTON, self.OnRemoveElement)
        edit_buttons_sizer.Add(self.remove_element_btn, pos=(1,1), flag=wx.EXPAND|wx.ALL, border=2)
        
        edit_buttons_sizer.AddGrowableCol(0)
        edit_buttons_sizer.AddGrowableCol(1)
        main_vbox.Add(edit_buttons_sizer, 0, wx.EXPAND | wx.ALL, 5)

        close_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.close_main_btn = wx.Button(panel, label="Close")
        self.close_main_btn.Bind(wx.EVT_BUTTON, lambda event: self.Close())
        close_btn_sizer.AddStretchSpacer(1)
        close_btn_sizer.Add(self.close_main_btn, 0, wx.ALL, 5) 
        close_btn_sizer.AddStretchSpacer(1)
        main_vbox.Add(close_btn_sizer, 0, wx.EXPAND | wx.BOTTOM | wx.TOP, 5)

        panel.SetSizer(main_vbox)
        self.SetSize((800, 700))
        self.Centre()
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Bind(wx.EVT_MENU, self.OnAddElementAsSiblingOrToRoot, id=ID_ADD_SIBLING_OR_TO_ROOT)
        self.Bind(wx.EVT_MENU, self.OnAddElementAsChild, id=ID_ADD_CHILD)


    def UpdateTitle(self):
        """Updates the window title based on the current file and unsaved changes status."""
        title = "XML Viewer"
        if self.current_file_path:
            title += f": {os.path.basename(self.current_file_path)}"
        if self.unsaved_changes:
            title += "*"
        self.SetTitle(title)

    def _update_button_states(self):
        """Updates the enabled/disabled state of various buttons based on the current context."""
        has_file = bool(self.xml_tree)
        self.save_btn.Enable(has_file and self.unsaved_changes)
        self.save_as_btn.Enable(has_file)

        selected_item = self.tree_ctrl.GetSelection()
        has_selection = selected_item.IsOk() and self.tree_ctrl.GetItemData(selected_item) is not None
        
        is_real_root_selected = False
        if has_selection:
            tree_root_item_pseudo = self.tree_ctrl.GetRootItem() # This is the hidden root
            if tree_root_item_pseudo.IsOk() and self.tree_ctrl.GetChildrenCount(tree_root_item_pseudo, recursively=False) > 0:
                actual_xml_root_item, _ = self.tree_ctrl.GetFirstChild(tree_root_item_pseudo)
                if selected_item == actual_xml_root_item:
                    is_real_root_selected = True

        self.add_element_btn.Enable(has_file) 
        self.edit_element_btn.Enable(has_selection)
        self.edit_attr_btn.Enable(has_selection)
        self.remove_element_btn.Enable(has_selection and not is_real_root_selected)


    def OnTreeSelectionChanged(self, event):
        """Handles tree item selection changes to update button states."""
        self._update_button_states()
        event.Skip()

    def OnOpenFile(self, event):
        """Handles the 'Open File' event, prompting to save if there are unsaved changes."""
        if self.unsaved_changes:
            ret = wx.MessageBox("You have unsaved changes. Would you like to Save them before opening a new file?",
                                "Unsaved Changes", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
            if ret == wx.YES:
                if not self.OnSaveFile(event): 
                    return
            elif ret == wx.CANCEL:
                return

        with wx.FileDialog(self, "Open XML file", wildcard="XML files (*.xml)|*.xml|All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            self.current_file_path = fileDialog.GetPath()
            try:
                self.xml_tree = ET.parse(self.current_file_path)
                self.root_element = self.xml_tree.getroot()
                self.PopulateTreeCtrl()
                self._update_xml_display()
                self.unsaved_changes = False
            except ParseError as e:
                wx.MessageBox(f"Error parsing XML file:\n{e}", "Parse Error", wx.OK | wx.ICON_ERROR)
                self.current_file_path = None
                self.xml_tree = None
                self.root_element = None
                self.tree_ctrl.DeleteAllItems()
                self.xml_display_ctrl.Clear()
            except Exception as e:
                wx.MessageBox(f"An unexpected error occurred while opening file:\n{e}", "Error", wx.OK | wx.ICON_ERROR)
                self.current_file_path = None 
            self.UpdateTitle()
            self._update_button_states()

    def _get_element_display_string(self, element):
        """
        Generates a display string for an XML element for use in the TreeCtrl.
        Format: "tag_name [attributes...] : "text content snippet"" (if text exists)
        or      "tag_name [attributes...]" (if no text)
        """
        tag_and_attrs_part = element.tag
        
        if element.attrib:
            attr_list = []
            for k, v in list(element.attrib.items())[:2]: # Show first 2 attributes
                attr_list.append(f'{k}="{v}"')
            if len(element.attrib) > 2:
                attr_list.append("...")
            tag_and_attrs_part += f' [{", ".join(attr_list)}]'
            
        text_content_part = ""
        if element.text and element.text.strip():
            display_text = element.text.strip()
            if len(display_text) > 100:
                display_text = display_text[:100] + "..."
            text_content_part = f' : "{display_text}"'             
        return f"{tag_and_attrs_part}{text_content_part}"

    def PopulateTreeCtrl(self):
        """Populates the TreeCtrl with the loaded XML data."""
        self.tree_ctrl.DeleteAllItems()
        if not self.root_element is None:
            hidden_root = self.tree_ctrl.AddRoot("XML Document") 
            root_item_text = self._get_element_display_string(self.root_element)
            root_item = self.tree_ctrl.AppendItem(hidden_root, root_item_text)
            self.tree_ctrl.SetItemData(root_item, self.root_element)
            self._populate_children(root_item, self.root_element)
            self.tree_ctrl.Expand(root_item)
            self.tree_ctrl.SelectItem(root_item) 
        self._update_button_states()

    def _populate_children(self, parent_item, parent_element):
        """Recursively populates child elements in the TreeCtrl."""
        for child_element in parent_element:
            child_item_text = self._get_element_display_string(child_element)
            child_item = self.tree_ctrl.AppendItem(parent_item, child_item_text)
            self.tree_ctrl.SetItemData(child_item, child_element)
            self._populate_children(child_item, child_element)


    def _update_xml_display(self):
        """Updates the read-only text control with the current XML string."""
        if self.root_element is not None:
            try:
                # Attempt to pretty-print if Python 3.9+
                if hasattr(ET, 'indent'):
                    ET.indent(self.root_element) 
                xml_string = ET.tostring(self.root_element, encoding='unicode', method='xml')
                self.xml_display_ctrl.SetValue(xml_string)
            except Exception as e:
                self.xml_display_ctrl.SetValue(f"Error generating XML string: {e}")
        else:
            self.xml_display_ctrl.Clear()

    def OnSaveFile(self, event):
        """Handles the 'Save' event, saving changes to the current file."""
        if not self.current_file_path:
            return self.OnSaveFileAs(event)
        if self.xml_tree:
            try:
                if hasattr(ET, 'indent'):
                    ET.indent(self.root_element) 
                self.xml_tree.write(self.current_file_path, encoding='utf-8', xml_declaration=True)
                self.unsaved_changes = False
                self.UpdateTitle()
                self._update_xml_display() 
                self._update_button_states()
                wx.MessageBox(f"File saved to\n{self.current_file_path}", "Saved", wx.OK | wx.ICON_INFORMATION)
                return True
            except Exception as e:
                wx.MessageBox(f"Error saving file:\n{e}", "Save Error", wx.OK | wx.ICON_ERROR)
                return False
        return False


    def OnSaveFileAs(self, event):
        """Handles the 'Save As' event, saving to a new file."""
        if not self.xml_tree:
            wx.MessageBox("No XML data to save.", "Nothing to Save", wx.OK | wx.ICON_INFORMATION)
            return False

        with wx.FileDialog(self, "Save XML file as...", wildcard="XML files (*.xml)|*.xml",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return False
            self.current_file_path = fileDialog.GetPath()
            return self.OnSaveFile(event)


    def OnShowAddElementMenu(self, event):
        """Shows a context menu for adding elements."""
        if not self.xml_tree:
            return

        menu = wx.Menu()
        menu.Append(ID_ADD_SIBLING_OR_TO_ROOT, "Add Element (Sibling/To Root)")
        
        selected_item = self.tree_ctrl.GetSelection()
        add_child_item = menu.Append(ID_ADD_CHILD, "Add Child Element")
        add_child_item.Enable(selected_item.IsOk() and self.tree_ctrl.GetItemData(selected_item) is not None)
        
        self.PopupMenu(menu)
        menu.Destroy()

    def _add_element_logic(self, parent_element_in_xml, parent_tree_item_for_append):
        """Shared logic for creating and adding a new element."""
        if parent_element_in_xml is None:
            wx.MessageBox("Cannot determine a valid parent element in the XML structure.", "Error", wx.OK | wx.ICON_ERROR)
            return
        if not parent_tree_item_for_append.IsOk():
             wx.MessageBox("Cannot determine a valid parent item in the tree.", "Error", wx.OK | wx.ICON_ERROR)
             return

        dlg = ElementEditorDialog(self, title="Add New Element", tag_name="NewElement", text_content="")
        if dlg.ShowModal() == wx.ID_OK:
            tag_name = dlg.GetTagName()
            text_content = dlg.GetTextContent()
            if not tag_name:
                wx.MessageBox("Tag name cannot be empty.", "Invalid Tag Name", wx.OK | wx.ICON_WARNING)
                dlg.Destroy()
                return

            new_element = ET.Element(tag_name)
            if text_content:
                new_element.text = text_content            
            parent_element_in_xml.append(new_element) 
            
            new_item_text = self._get_element_display_string(new_element)
            new_item = self.tree_ctrl.AppendItem(parent_tree_item_for_append, new_item_text)
            self.tree_ctrl.SetItemData(new_item, new_element)
            self.tree_ctrl.Expand(parent_tree_item_for_append)
            self.tree_ctrl.EnsureVisible(new_item)
            self.tree_ctrl.SelectItem(new_item)

            self.unsaved_changes = True
            self.UpdateTitle()
            self._update_xml_display()
            self._update_button_states()
        dlg.Destroy()

    def OnAddElementAsChild(self, event):
        """Handles adding an element as a child to the currently selected element."""
        if not self.xml_tree: return

        selected_item = self.tree_ctrl.GetSelection()
        if not selected_item.IsOk() or selected_item == self.tree_ctrl.GetRootItem():
            wx.MessageBox("Please select a valid parent element in the tree to add a child to.", "No Parent Selected", wx.OK | wx.ICON_INFORMATION)
            return
        
        parent_element_in_xml = self.tree_ctrl.GetItemData(selected_item)
        if parent_element_in_xml is None:
            wx.MessageBox("Selected tree item does not correspond to a valid XML element.", "Error", wx.OK | wx.ICON_ERROR)
            return
            
        parent_tree_item_for_append = selected_item
        self._add_element_logic(parent_element_in_xml, parent_tree_item_for_append)

    def OnAddElementAsSiblingOrToRoot(self, event):
        """Handles adding an element as a sibling to the selected element, or to the root if none/root is selected."""
        if not self.xml_tree: return

        selected_item = self.tree_ctrl.GetSelection()
        tree_pseudo_root = self.tree_ctrl.GetRootItem()
        
        actual_xml_root_item = None
        if tree_pseudo_root.IsOk() and self.tree_ctrl.GetChildrenCount(tree_pseudo_root, False) > 0:
            actual_xml_root_item, _ = self.tree_ctrl.GetFirstChild(tree_pseudo_root)

        parent_element_in_xml = None
        parent_tree_item_for_append = None

        if not selected_item.IsOk() or selected_item == tree_pseudo_root or selected_item == actual_xml_root_item:
            parent_element_in_xml = self.root_element
            parent_tree_item_for_append = actual_xml_root_item
            if parent_tree_item_for_append is None or not parent_tree_item_for_append.IsOk():
                parent_tree_item_for_append = tree_pseudo_root # Add to hidden root if XML root item doesn't exist yet
        else:
            parent_of_selected_tree_item = self.tree_ctrl.GetItemParent(selected_item)
            if parent_of_selected_tree_item.IsOk():
                parent_element_in_xml = self.tree_ctrl.GetItemData(parent_of_selected_tree_item)
                parent_tree_item_for_append = parent_of_selected_tree_item
            else:
                wx.MessageBox("Could not determine parent of selected item.", "Error", wx.OK | wx.ICON_ERROR)
                return
        
        if parent_element_in_xml is None and self.root_element is None:
            pass

        if parent_element_in_xml is None:
             parent_element_in_xml = self.root_element
        if parent_tree_item_for_append is None or not parent_tree_item_for_append.IsOk():
             parent_tree_item_for_append = actual_xml_root_item if actual_xml_root_item and actual_xml_root_item.IsOk() else tree_pseudo_root
        self._add_element_logic(parent_element_in_xml, parent_tree_item_for_append)

    def OnEditElement(self, event):
        """Handles editing the selected XML element's tag or text."""
        selected_item = self.tree_ctrl.GetSelection()
        if not selected_item.IsOk() or selected_item == self.tree_ctrl.GetRootItem(): return

        element = self.tree_ctrl.GetItemData(selected_item)
        if not element is None:
            dlg = ElementEditorDialog(self, "Edit Element", element.tag, element.text or "")
            if dlg.ShowModal() == wx.ID_OK:
                new_tag = dlg.GetTagName()
                new_text = dlg.GetTextContent()

                if not new_tag:
                    wx.MessageBox("Tag name cannot be empty.", "Invalid Tag Name", wx.OK | wx.ICON_WARNING)
                    dlg.Destroy()
                    return
                
                element.tag = new_tag
                element.text = new_text if new_text else None 

                updated_item_text = self._get_element_display_string(element)
                self.tree_ctrl.SetItemText(selected_item, updated_item_text)
                self.unsaved_changes = True
                self.UpdateTitle()
                self._update_xml_display()
                self._update_button_states()
            dlg.Destroy()

    def OnEditAttributes(self, event):
        """Handles editing the attributes of the selected XML element."""
        selected_item = self.tree_ctrl.GetSelection()
        if not selected_item.IsOk() or selected_item == self.tree_ctrl.GetRootItem(): return

        element = self.tree_ctrl.GetItemData(selected_item)
        if not element is None:
            dlg = AttributeEditorDialog(self, attributes=element.attrib)
            if dlg.ShowModal() == wx.ID_OK:
                element.attrib = dlg.GetAttributes()
                updated_item_text = self._get_element_display_string(element)
                self.tree_ctrl.SetItemText(selected_item, updated_item_text)
                self.unsaved_changes = True
                self.UpdateTitle()
                self._update_xml_display()
                self._update_button_states()
            dlg.Destroy()
            
    def OnRemoveElement(self, event):
        """Handles removing the selected XML element."""
        selected_item = self.tree_ctrl.GetSelection()
        if not selected_item.IsOk() or selected_item == self.tree_ctrl.GetRootItem(): return

        element_to_remove = self.tree_ctrl.GetItemData(selected_item)
        if element_to_remove is None: return

        if element_to_remove == self.root_element:
            wx.MessageBox("Cannot remove the root element of the XML document.", "Action Denied", wx.OK | wx.ICON_WARNING)
            return
        
        parent_item = self.tree_ctrl.GetItemParent(selected_item)
        parent_element = self.tree_ctrl.GetItemData(parent_item)

        if parent_element is not None: 
            confirm = wx.MessageBox(f"Are you sure you want to remove element '{element_to_remove.tag}' and all its children?",
                                    "Confirm Removal", wx.YES_NO | wx.ICON_QUESTION, self)
            if confirm == wx.YES:
                parent_element.remove(element_to_remove)
                self.tree_ctrl.Delete(selected_item)
                self.unsaved_changes = True
                self.UpdateTitle()
                self._update_xml_display()
                self._update_button_states()
        else: 
             wx.MessageBox("Could not find parent element in tree data.", "Internal Error", wx.OK | wx.ICON_ERROR)


    def OnCloseWindow(self, event):
        """Handles the window close event, prompting to save if there are unsaved changes."""
        if self.unsaved_changes:
            ret = wx.MessageBox("You have unsaved changes. Would you like to save them?",
                                "Unsaved Changes", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
            if ret == wx.YES:
                if not self.OnSaveFile(None): 
                    event.Veto()
                    return
            elif ret == wx.CANCEL:
                event.Veto()
                return
        self.Destroy()
