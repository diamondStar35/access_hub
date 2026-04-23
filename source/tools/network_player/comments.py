import wx
import wx.lib.mixins.listctrl as listmix
import html

class CommentsDialog(wx.Dialog, listmix.ColumnSorterMixin):
    def __init__(self, parent, comments):
        super().__init__(parent, title="Comments", size=(800, 600))
        self.comments = comments

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.list_ctrl.InsertColumn(0, "Comment", width=500)
        self.list_ctrl.InsertColumn(1, "Author", width=200)
        vbox.Add(self.list_ctrl, 1, wx.ALL | wx.EXPAND, 5)

        # Adding data to list
        items = {}
        for index, comment in enumerate(self.comments):
            unescaped_comment_text = html.unescape(comment['text'])
            unescaped_author_name = html.unescape(comment['author'])
            item = self.list_ctrl.InsertItem(index, unescaped_comment_text)
            self.list_ctrl.SetItem(item, 1, unescaped_author_name)
            self.list_ctrl.SetItemData(item, index)
            items[index] = (unescaped_comment_text, unescaped_author_name)  # Data for sorting

        # Set up ColumnSorterMixin
        self.itemDataMap = items
        listmix.ColumnSorterMixin.__init__(self, 2)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        copy_button = wx.Button(panel, label="Copy Comment")
        copy_button.Bind(wx.EVT_BUTTON, self.on_copy)
        button_sizer.Add(copy_button, 0, wx.ALL, 5)

        close_button = wx.Button(panel, label="Close")
        close_button.Bind(wx.EVT_BUTTON, self.on_close)
        button_sizer.Add(close_button, 0, wx.ALL, 5)

        vbox.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        panel.SetSizer(vbox)
        self.Centre()

    def on_copy(self, event):
        selected_item = self.list_ctrl.GetFirstSelected()
        if selected_item != -1:
            comment_text = self.list_ctrl.GetItemText(selected_item, 0)
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(comment_text))
                wx.TheClipboard.Close()
                wx.MessageBox("Comment copied to clipboard!", "Success", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox("Please select a comment to copy.", "error", wx.OK | wx.ICON_WARNING)

    def on_close(self, event):
        self.Destroy()

    def GetListCtrl(self):
        return self.list_ctrl

    def GetSortImages(self):
        return (self.sm_dn, self.sm_up)