import wx

class DescriptionDialog(wx.Dialog):
    """
    A reusable dialog to display read-only, multiline text (like a video description).
    Closes on pressing the Escape key.
    """
    def __init__(self, parent, title, description_text):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetSize(800, 600)
        self.SetMinSize((600, 350))

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.description_text_ctrl = wx.TextCtrl(
            panel, -1, description_text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.VSCROLL
        )
        vbox.Add(self.description_text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        ok_button = wx.Button(panel, wx.ID_OK, "Close")

        button_sizer = wx.StdDialogButtonSizer()
        button_sizer.AddButton(ok_button)
        button_sizer.Realize()
        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        panel.SetSizer(vbox)
        self.Layout()
        self.Centre()
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

    def on_char_hook(self, event):
        """Handles character events, specifically checking for Escape key."""
        if event.GetKeyCode() == wx.WXK_ESCAPE and event.GetModifiers() == wx.MOD_NONE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip() # Process other keys normally (e.g., text navigation)

class MultilineTextEditDialog(wx.Dialog):
    """Dialog for editing multiline text."""
    def __init__(self, parent, title, initial_text=""):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetSize(400, 300)

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.HSCROLL | wx.VSCROLL)
        self.text_ctrl.SetValue(initial_text)
        vbox.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

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

    def GetValue(self):
        """Returns the text from the text control."""
        return self.text_ctrl.GetValue()


class ReplacementEntryDialog(wx.Dialog):
    def __init__(self, parent, title="Enter Replacement Text", current_text=""):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetSize((400, 200))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(panel, label="Replacement text:")
        vbox.Add(lbl, 0, wx.ALL, 5)

        self.replace_text_ctrl = wx.TextCtrl(panel, value=current_text, style=wx.TE_MULTILINE)
        vbox.Add(self.replace_text_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()

        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        panel.SetSizer(vbox)
        self.replace_text_ctrl.SetFocus()

    def GetValue(self):
        return self.replace_text_ctrl.GetValue()


class ElementEditorDialog(wx.Dialog):
    """
    A dialog for creating or editing an XML element's tag name and text content.
    """
    def __init__(self, parent, title, tag_name="", text_content=""):
        """
        Initializes the ElementEditorDialog.

        Args:
            parent: The parent window.
            title (str): The title for the dialog window.
            tag_name (str, optional): The initial tag name. Defaults to "".
            text_content (str, optional): The initial text content. Defaults to "".
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetSize((400, 300))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        tag_hbox = wx.BoxSizer(wx.HORIZONTAL)
        tag_label = wx.StaticText(panel, label="Tag Name:")
        tag_hbox.Add(tag_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.tag_name_ctrl = wx.TextCtrl(panel, value=tag_name)
        tag_hbox.Add(self.tag_name_ctrl, 1, wx.EXPAND)
        vbox.Add(tag_hbox, 0, wx.EXPAND | wx.ALL, 10)

        text_label = wx.StaticText(panel, label="Text Content:")
        vbox.Add(text_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.text_content_ctrl = wx.TextCtrl(panel, value=text_content, style=wx.TE_MULTILINE)
        vbox.Add(self.text_content_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        panel.SetSizer(vbox)
        self.tag_name_ctrl.SetFocus()

    def GetTagName(self):
        return self.tag_name_ctrl.GetValue().strip()

    def GetTextContent(self):
        return self.text_content_ctrl.GetValue()


class SingleAttributeEditDialog(wx.Dialog):
    """
    A dialog for editing the name and value of a single attribute.
    """
    def __init__(self, parent, title="Edit Attribute", attr_name="", attr_value=""):
        """
        Initializes the SingleAttributeEditDialog.

        Args:
            parent: The parent window.
            title (str): The title for the dialog window.
            attr_name (str, optional): The initial attribute name. Defaults to "".
            attr_value (str, optional): The initial attribute value. Defaults to "".
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetSize((350, 200))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        name_label = wx.StaticText(panel, label="Attribute Name:")
        vbox.Add(name_label, 0, wx.ALL, 5)
        self.name_ctrl = wx.TextCtrl(panel, value=attr_name)
        vbox.Add(self.name_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        value_label = wx.StaticText(panel, label="Attribute Value:")
        vbox.Add(value_label, 0, wx.ALL, 5)
        self.value_ctrl = wx.TextCtrl(panel, value=attr_value)
        vbox.Add(self.value_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        vbox.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(vbox)
        self.name_ctrl.SetFocus()

    def GetAttributeName(self):
        """
        Gets the attribute name entered in the dialog.

        Returns:
            str: The stripped attribute name.
        """
        return self.name_ctrl.GetValue().strip()

    def GetAttributeValue(self):
        """
        Gets the attribute value entered in the dialog.

        Returns:
            str: The stripped attribute value.
        """
        return self.value_ctrl.GetValue().strip()


class AttributeEditorDialog(wx.Dialog):
    """
    A dialog for editing the attributes of an XML element using a ListBox.
    """
    def __init__(self, parent, title="Edit Attributes", attributes=None):
        """
        Initializes the AttributeEditorDialog.

        Args:
            parent: The parent window.
            title (str, optional): The title for the dialog window. Defaults to "Edit Attributes".
            attributes (dict, optional): A dictionary of initial attributes. Defaults to None.
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetSize((600, 350))
        self.attributes = dict(attributes) if attributes else {}

        panel = wx.Panel(self)
        main_vbox = wx.BoxSizer(wx.VERTICAL)
        attr_label = wx.StaticText(panel, label="Attributes:")
        main_vbox.Add(attr_label, 0, wx.ALL, 5)

        self.attr_listbox = wx.ListBox(panel)
        main_vbox.Add(self.attr_listbox, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)        
        self.add_btn = wx.Button(panel, label="Add...")
        self.add_btn.Bind(wx.EVT_BUTTON, self.OnAddAttribute)
        btn_sizer.Add(self.add_btn, 0, wx.ALL, 5)

        self.edit_btn = wx.Button(panel, label="Edit...")
        self.edit_btn.Bind(wx.EVT_BUTTON, self.OnEditAttribute)
        btn_sizer.Add(self.edit_btn, 0, wx.ALL, 5)

        self.remove_btn = wx.Button(panel, label="Remove")
        self.remove_btn.Bind(wx.EVT_BUTTON, self.OnRemoveAttribute)
        btn_sizer.Add(self.remove_btn, 0, wx.ALL, 5)        
        main_vbox.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        dialog_button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        dialog_button_sizer.AddButton(ok_button)
        dialog_button_sizer.AddButton(cancel_button)
        dialog_button_sizer.Realize()
        main_vbox.Add(dialog_button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(main_vbox)
        self.attr_listbox.Bind(wx.EVT_LISTBOX, self.OnListBoxSelect)
        self.attr_listbox.Bind(wx.EVT_LISTBOX_DCLICK, self.OnEditAttribute)
        self._populate_listbox()
        self._update_button_states()


    def _populate_listbox(self):
        """Populates the ListBox with the current attributes."""
        self.attr_listbox.Clear()
        for name, value in self.attributes.items():
            self.attr_listbox.Append(f"{name}={value}")
        self._update_button_states()

    def _update_button_states(self):
        """Enables/disables edit and remove buttons based on ListBox selection."""
        selected_index = self.attr_listbox.GetSelection()
        is_item_selected = selected_index != wx.NOT_FOUND
        self.edit_btn.Enable(is_item_selected)
        self.remove_btn.Enable(is_item_selected)

    def OnListBoxSelect(self, event):
        """Handles selection changes in the ListBox."""
        self._update_button_states()
        event.Skip()

    def OnAddAttribute(self, event):
        """Handles the 'Add Attribute' event."""
        dlg = SingleAttributeEditDialog(self, title="Add Attribute")
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.GetAttributeName()
            value = dlg.GetAttributeValue()
            if not name:
                wx.MessageBox("Attribute name cannot be empty.", "Invalid Name", wx.OK | wx.ICON_WARNING, self)
                dlg.Destroy()
                return
            if name in self.attributes:
                wx.MessageBox(f"Attribute '{name}' already exists. Use Edit to change its value.",
                              "Attribute Exists", wx.OK | wx.ICON_WARNING, self)
                dlg.Destroy()
                return
            
            self.attributes[name] = value
            self._populate_listbox()
            for i in range(self.attr_listbox.GetCount()):
                if self.attr_listbox.GetString(i).startswith(name + "="):
                    self.attr_listbox.SetSelection(i)
                    break
            self._update_button_states()
            self.attr_listbox.SetFocus()
        dlg.Destroy()

    def OnEditAttribute(self, event):
        """Handles the 'Edit Attribute' event."""
        selected_index = self.attr_listbox.GetSelection()
        if selected_index == wx.NOT_FOUND:
            return

        selected_string = self.attr_listbox.GetString(selected_index)
        parts = selected_string.split("=", 1)
        old_name = parts[0]
        old_value = parts[1] if len(parts) > 1 else ""

        dlg = SingleAttributeEditDialog(self, title="Edit Attribute", attr_name=old_name, attr_value=old_value)
        if dlg.ShowModal() == wx.ID_OK:
            new_name = dlg.GetAttributeName()
            new_value = dlg.GetAttributeValue()

            if not new_name:
                wx.MessageBox("Attribute name cannot be empty.", "Invalid Name", wx.OK | wx.ICON_WARNING, self)
                dlg.Destroy()
                return

            if new_name != old_name:
                if new_name in self.attributes:
                    wx.MessageBox(f"Another attribute with the name '{new_name}' already exists.",
                                  "Attribute Name Conflict", wx.OK | wx.ICON_WARNING, self)
                    dlg.Destroy()
                    return
                del self.attributes[old_name]

            self.attributes[new_name] = new_value
            self._populate_listbox()
            for i in range(self.attr_listbox.GetCount()):
                if self.attr_listbox.GetString(i).startswith(new_name + "="):
                    self.attr_listbox.SetSelection(i)
                    break
            self._update_button_states()
            self.attr_listbox.SetFocus()
        dlg.Destroy()

    def OnRemoveAttribute(self, event):
        """Handles the 'Remove Attribute' event."""
        selected_index = self.attr_listbox.GetSelection()
        if selected_index == wx.NOT_FOUND:
            return

        selected_string = self.attr_listbox.GetString(selected_index)
        name_to_remove = selected_string.split("=", 1)[0]
        if name_to_remove in self.attributes:
            del self.attributes[name_to_remove]
            self._populate_listbox()

            if self.attr_listbox.GetCount() > 0:
                new_selection = min(selected_index, self.attr_listbox.GetCount() - 1)
                if new_selection >=0:
                    self.attr_listbox.SetSelection(new_selection)
            self._update_button_states()
            self.attr_listbox.SetFocus()

    def GetAttributes(self):
        """
        Gets the attributes edited in the dialog.

        Returns:
            dict: A dictionary of attributes.
        """
        return self.attributes
