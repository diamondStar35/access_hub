import wx

class CustomButton(wx.Button):
    def __init__(self, *args, **kwargs):
        wx.Button.__init__(self, *args, **kwargs)

    def AcceptsFocusFromKeyboard(self):
        return False

class CustomSlider(wx.Slider):
    """
    A custom slider that provides enhanced keyboard input handling.
    It ensures that slider update events are always fired and offers
    consistent behavior for arrow keys, page up/down, and home/end.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Bind(wx.EVT_CHAR, self.on_char)

    def SetValue(self, value):
        """Overrides SetValue to ensure a slider update event is fired."""
        super().SetValue(value)
        # Create and dispatch the slider updated event.
        evt = wx.CommandEvent(wx.wxEVT_SLIDER, self.GetId())
        evt.SetInt(value)
        evt.SetEventObject(self)
        self.ProcessEvent(evt)

    def on_char(self, evt):
        """Handles character input for the slider."""
        key = evt.GetKeyCode()
        new_value = self.Value  # Start with the current value.

        if key == wx.WXK_UP:
            new_value = min(self.Value + self.LineSize, self.Max)
        elif key == wx.WXK_DOWN:
            new_value = max(self.Value - self.LineSize, self.Min)
        elif key == wx.WXK_PAGEUP:
            new_value = min(self.Value + self.PageSize, self.Max)
        elif key == wx.WXK_PAGEDOWN:
            new_value = max(self.Value - self.PageSize, self.Min)
        elif key == wx.WXK_HOME:
            new_value = self.Max
        elif key == wx.WXK_END:
            new_value = self.Min
        else:
            evt.Skip()  # Let other key events be handled normally.
            return

        self.SetValue(new_value)


class CustomTextCtrl(wx.TextCtrl):
    """
    A custom text control that supports history navigation using Up/Down arrows
    and optionally saves history lines.
    """
    def __init__(self, parent, id=wx.ID_ANY, value="", pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0, validator=wx.DefaultValidator,
                 name=wx.TextCtrlNameStr, history=None):
        super().__init__(parent, id, value, pos, size, style, validator, name)
        self._history = list(history) if history is not None else []
        self._history_index = -1 # -1 means current input is not from history
        self._current_input_before_history = "" # Store current input when browsing history

        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_TEXT_ENTER, self.on_text_enter_for_history)

    def on_key_down(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_UP:
            if self._history:
                # If we were typing, save current input before navigating history
                if self._history_index == -1:
                    self._current_input_before_history = self.GetValue()
                self._history_index += 1
                if self._history_index >= len(self._history):
                    self._history_index = len(self._history) - 1

                self.SetValue(self._history[self._history_index])
                self.SetInsertionPointEnd()
            return

        elif keycode == wx.WXK_DOWN:
            if self._history:
                if self._history_index != -1:
                    self._history_index -= 1

                    if self._history_index >= 0:
                         # Move down in history (towards newer items)
                         self.SetValue(self._history[self._history_index])
                         self.SetInsertionPointEnd()
                    else:
                         # Back to current input state
                         self.SetValue(self._current_input_before_history)
                         self.SetInsertionPointEnd()
                         self._history_index = -1

                if self._history_index != -1 or self._current_input_before_history == "":
                     return
                else:
                     event.Skip()

        else:
            # Any other key press resets history navigation state
            if self._history_index != -1:
                 self._current_input_before_history = self.GetValue()
                 self._history_index = -1
            event.Skip()

    def on_text_enter_for_history(self, event):
        """Saves the current line to history if TE_MULTILINE is enabled."""
        line = self.GetValue().strip()
        if line and (not self._history or self._history[0] != line):
            self._history.insert(0, line)
        # Reset history navigation state
        self._history_index = -1
        self._current_input_before_history = ""
        event.Skip()

    def AddHistory(self, line):
        """Manually adds a line to the history."""
        line = line.strip()
        if line and (not self._history or self._history[0] != line):
             self._history.insert(0, line)
        # Reset history navigation state
        self._history_index = -1
        self._current_input_before_history = ""

    def GetHistory(self):
        """Returns the current history list."""
        return self._history


class CustomVirtualList(wx.ListCtrl):
    """
    A wx.ListCtrl in virtual mode to efficiently display large datasets.
    It expects a data_source (e.g., a list of tuples) and a function
    to retrieve text for a given row and column from that data_source.
    """
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.DefaultSize, 
                 style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES | wx.LC_VIRTUAL, 
                 validator=wx.DefaultValidator, name=wx.ListCtrlNameStr):
        super(CustomVirtualList, self).__init__(parent, id, pos, size, style, validator, name)
        self.data = []
        self._item_text_retriever = None

    def SetDataSource(self, data, item_text_retriever):
        """
        Sets the data source and the function to retrieve text for items.
        :param data: The list of data items.
        :param item_text_retriever: A function f(data_item, col_index) -> str
                                    or f(data_list, row_index, col_index) -> str
        """
        self.data = data
        self._item_text_retriever = item_text_retriever
        self.SetItemCount(len(self.data))
        if len(self.data) > 0: # Refresh if data is set
            self.RefreshItems(0, len(self.data) - 1)

    def OnGetItemText(self, item_idx, col_idx):
        """
        Called by wx.ListCtrl to get the text for a specific cell.
        """
        if self._item_text_retriever:
            # The retriever function is expected to handle accessing self.data[item_idx]
            # and returning the correct string for the column.
            return self._item_text_retriever(item_idx, col_idx)
        return ""
