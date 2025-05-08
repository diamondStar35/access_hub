import wx
from .multi_rename import MultipleRename
from .advanced_search import AdvancedSearchDialog

class FileTools(wx.Frame):
    def __init__(self, parent, title):
        super(FileTools, self).__init__(parent, title=title, size=(350, 200))
        self.SetBackgroundColour(wx.Colour(240, 240, 240))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        heading = wx.StaticText(panel, label="Select a File Tool")
        font = heading.GetFont()
        font.PointSize += 2
        font = font.Bold()
        heading.SetFont(font)
        vbox.Add(heading, 0, wx.ALL | wx.CENTER, 15)

        rename_button = wx.Button(panel, label="Multiple File Rename")
        rename_button.Bind(wx.EVT_BUTTON, self.on_multiple_rename)
        vbox.Add(rename_button, 0, wx.ALL | wx.EXPAND, 10)

        search_button = wx.Button(panel, label="Advanced File Search")
        search_button.Bind(wx.EVT_BUTTON, self.on_advanced_search)
        vbox.Add(search_button, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(vbox)
        self.Layout()
        self.Centre()

    def on_multiple_rename(self, event):
        """Opens the Multiple File Rename tool."""
        rename_frame = MultipleRename(self, title="Multiple File Rename")
        rename_frame.Show()
        self.Hide()

    def on_advanced_search(self, event):
        """Opens the Advanced File Search dialog."""
        search_dialog = AdvancedSearchDialog(self)
        self.Hide()
        search_dialog.ShowModal()
        search_dialog.Destroy()
        self.Show()

    def on_child_tool_close(self, child_frame_being_closed):
        self.Show()
        self.Raise()
