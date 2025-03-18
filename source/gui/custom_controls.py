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

