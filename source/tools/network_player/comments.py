import wx
import wx.lib.mixins.listctrl as listmix
from youtube_comment_downloader.downloader import YoutubeCommentDownloader, SORT_BY_POPULAR
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
            items[index] = (unescaped_comment_text, unescaped_author_name)  # Data for sorting

        # Set up ColumnSorterMixin
        self.itemDataMap = items
        listmix.ColumnSorterMixin.__init__(self, 2)

        close_button = wx.Button(panel, label="Close")
        close_button.Bind(wx.EVT_BUTTON, self.on_close)
        vbox.Add(close_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        panel.SetSizer(vbox)
        self.Centre()

    def on_close(self, event):
        self.Destroy()

    def GetListCtrl(self):
        return self.list_ctrl

    def GetSortImages(self):
        return (self.sm_dn, self.sm_up)