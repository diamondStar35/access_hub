import wx
from .json_viewer import JsonViewer
from .text_cleaner import TextCleaner
from .advanced_finder import AdvancedFinder
from .xml_viewer import XMLViewer


class TextSplitterFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super(TextSplitterFrame, self).__init__(*args, **kw)
        self.SetBackgroundColour(wx.Colour(240, 240, 240)) # Light gray background

        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)

        vbox = wx.BoxSizer(wx.VERTICAL)

        text_label = wx.StaticText(panel, label='Input text: ')
        vbox.Add(text_label, flag=wx.LEFT | wx.TOP, border=10)

        self.text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.text_ctrl.SetBackgroundColour(wx.Colour(250, 250, 250)) # Very light gray
        self.text_ctrl.SetForegroundColour(wx.Colour(30, 30, 30))  # Dark gray text
        vbox.Add(self.text_ctrl, 1, flag=wx.EXPAND | wx.ALL, border=10)

        hbox1 = wx.BoxSizer(wx.HORIZONTAL)

        split_label = wx.StaticText(panel, label='Split at:')
        hbox1.Add(split_label, flag=wx.RIGHT, border=5)

        self.split_input = wx.TextCtrl(panel)
        hbox1.Add(self.split_input, flag=wx.RIGHT, border=5)

        split_btn = wx.Button(panel, label='Split Text', size=(100, 30))
        split_btn.SetBackgroundColour(wx.Colour(100, 150, 200))  # Muted blue
        split_btn.SetForegroundColour(wx.Colour(255, 255, 255))  # White text
        split_btn.Bind(wx.EVT_BUTTON, self.OnSplit)
        hbox1.Add(split_btn)

        split_lines_btn = wx.Button(panel, label='Split by Lines', size=(150, 30))
        split_lines_btn.Bind(wx.EVT_BUTTON, self.OnSplitByLines)
        hbox1.Add(split_lines_btn, flag=wx.RIGHT, border=5)

        split_words_btn = wx.Button(panel, label='Split by Words', size=(150, 30))
        split_words_btn.Bind(wx.EVT_BUTTON, self.OnSplitByWords)
        hbox1.Add(split_words_btn)

        vbox.Add(hbox1, flag=wx.EXPAND | wx.RIGHT, border=10)

        include_number_label = wx.StaticText(panel, label='Include element number in result list')
        vbox.Add(include_number_label, flag=wx.LEFT | wx.TOP, border=10)
        self.include_number_checkbox = wx.CheckBox(panel, label='Include element number in result list')
        vbox.Add(self.include_number_checkbox, flag=wx.EXPAND | wx.ALL, border=10)

        ignore_blank_lines_label = wx.StaticText(panel, label='Ignore blank lines when splitting by lines')
        vbox.Add(ignore_blank_lines_label, flag=wx.LEFT | wx.TOP, border=10)
        self.ignore_blank_lines_checkbox = wx.CheckBox(panel, label='Ignore blank lines when splitting by lines')
        vbox.Add(self.ignore_blank_lines_checkbox, flag=wx.EXPAND | wx.ALL, border=10)

        # Listbox for displaying result text parts
        self.result_listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.result_listbox.Hide()  # Hide the listbox initially
        vbox.Add(self.result_listbox, 1, flag=wx.EXPAND | wx.ALL, border=10)

        # "Copy" button to copy the selected element
        self.copy_btn = wx.Button(panel, label='Copy Selected', size=(150, 30))
        self.copy_btn.Hide()
        self.copy_btn.Bind(wx.EVT_BUTTON, self.OnCopySelected)
        vbox.Add(self.copy_btn, flag=wx.EXPAND | wx.ALL, border=10)

        panel.SetSizer(vbox)

        self.SetSize((500, 400))
        self.SetTitle('Text Splitter')
        self.Centre()

    def OnSplit(self, event):
        text = self.text_ctrl.GetValue()
        split_option_str = self.split_input.GetValue()

        try:
            split_option = int(split_option_str)
        except ValueError:
            wx.MessageBox('Please enter a valid integer for splitting.', 'Error', wx.OK | wx.ICON_ERROR)
            return

        # Improved splitting logic
        split_text = [text[i:i + split_option] for i in range(0, len(text), split_option)]
        self.DisplayResult(split_text)

    def OnSplitByLines(self, event):
        text = self.text_ctrl.GetValue()

        if self.ignore_blank_lines_checkbox.GetValue():
            lines = [line for line in text.split('\n') if line.strip()]
        else:
            lines = text.split('\n')

        self.DisplayResult(lines)

    def OnSplitByWords(self, event):
        text = self.text_ctrl.GetValue()
        words = text.split()
        self.DisplayResult(words)

    def OnCopySelected(self, event):
        selected_index = self.result_listbox.GetSelection()
        if selected_index != wx.NOT_FOUND:
            text_to_copy = self.result_listbox.GetString(selected_index)

            data = wx.TextDataObject()
            data.SetText(text_to_copy)

            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(data)
                wx.TheClipboard.Close()

    def DisplayResult(self, result_text_list):
        # Clear existing items in the listbox
        self.result_listbox.Clear()

        # Add each part to the listbox
        for index, result_text in enumerate(result_text_list, start=1):
            if self.include_number_checkbox.GetValue():
                result_text = f'{index}: {result_text}'
            self.result_listbox.Append(result_text)

        # Show the listbox after displaying results
        self.result_listbox.Show()
        self.copy_btn.Show()


class CapitalizeFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super(CapitalizeFrame, self).__init__(*args, **kw)
        self.SetBackgroundColour(wx.Colour(240, 240, 240)) # Light gray background

        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)

        vbox = wx.BoxSizer(wx.VERTICAL)

        input_text_label = wx.StaticText(panel, label='Enter Text:')
        vbox.Add(input_text_label, flag=wx.LEFT | wx.TOP, border=10)

        self.input_text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.input_text_ctrl.SetBackgroundColour(wx.Colour(250, 250, 250)) # Very light gray
        self.input_text_ctrl.SetForegroundColour(wx.Colour(30, 30, 30))  # Dark gray text
        vbox.Add(self.input_text_ctrl, 1, flag=wx.EXPAND | wx.ALL, border=10)

        capitalize_btn_label = wx.StaticText(panel, label='Capitalize Text:')
        vbox.Add(capitalize_btn_label, flag=wx.LEFT | wx.TOP, border=10)
        capitalize_btn = wx.Button(panel, label='Capitalize', size=(150, 30))
        capitalize_btn.Bind(wx.EVT_BUTTON, self.OnCapitalize)
        capitalize_btn.SetBackgroundColour(wx.Colour(100, 150, 200))  # Muted blue
        capitalize_btn.SetForegroundColour(wx.Colour(255, 255, 255))  # White text
        vbox.Add(capitalize_btn, flag=wx.EXPAND | wx.ALL, border=10)

        # Output read-only text box (initially hidden)
        self.output_text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.output_text_ctrl.Hide()
        vbox.Add(self.output_text_ctrl, 1, flag=wx.EXPAND | wx.ALL, border=10)

        panel.SetSizer(vbox)

        self.SetSize((400, 300))
        self.SetTitle('Capitalize Text')
        self.Centre()

    def OnCapitalize(self, event):
        # Get the input text
        input_text = self.input_text_ctrl.GetValue()

        # Capitalize the first letter of each line, handling leading spaces
        capitalized_lines = []
        for line in input_text.split('\n'):
            if line.strip():  # Check if the line is not just spaces
                first_non_space_index = len(line) - len(line.lstrip())
                line = line[:first_non_space_index] + line[first_non_space_index:].capitalize()
            capitalized_lines.append(line)

        capitalized_text = '\n'.join(capitalized_lines)

        # Display the result in the output text box
        self.output_text_ctrl.SetValue(capitalized_text)
        self.output_text_ctrl.Show()


class TextUtilitiesApp(wx.Frame):
    def __init__(self, *args, **kw):
        super(TextUtilitiesApp, self).__init__(*args, **kw)
        self.child_frames = []
        self.text_tools_list = [
            ("Split Text", "Split text by character count, lines, or words.", self.OnSplit),
            ("Text Info", "Get information like line, word, and character count.", self.OnTextInfo),
            ("Advanced Finder", "Find and replace text with advanced options.", self.OnAdvancedFinder),
            ("Text Cleaner", "Clean text by removing extra spaces, empty lines, etc.", self.OnTextCleaner),
            ("Capitalize Text", "Capitalize the first letter of each line.", self.OnCapitalizeText),
            ("JSON Viewer", "View and format JSON data.", self.OnJsonViewer),
            ("XML Viewer", "View and navigate XML data.", self.OnXMLViewer)
        ]
        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)
        self.SetBackgroundColour(wx.Colour(240, 240, 240))
        panel.SetBackgroundColour(wx.Colour(230, 230, 230))

        vbox = wx.BoxSizer(wx.VERTICAL)
        title_text = wx.StaticText(panel, label="Text Utilities", style=wx.ALIGN_CENTER)
        title_font = title_text.GetFont()
        title_font.PointSize += 4
        title_font = title_font.Bold()
        title_text.SetFont(title_font)
        vbox.Add(title_text, 0, wx.ALL | wx.EXPAND, 15)

        self.tool_list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES | wx.LC_HRULES)
        self.tool_list_ctrl.SetFont(wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.tool_list_ctrl.SetBackgroundColour(wx.Colour(250, 250, 250))

        self.tool_list_ctrl.InsertColumn(0, "Tool Name", width=180)
        self.tool_list_ctrl.InsertColumn(1, "Description", width=320)

        for index, (name, description, _) in enumerate(self.text_tools_list):
            list_index = self.tool_list_ctrl.InsertItem(index, name)
            self.tool_list_ctrl.SetItem(list_index, 1, description)
            self.tool_list_ctrl.SetItemData(list_index, index)

        self.tool_list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_run_selected_tool)
        vbox.Add(self.tool_list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        run_button = wx.Button(panel, label="Run Tool")
        run_button.Bind(wx.EVT_BUTTON, self.on_run_selected_tool)
        btn_sizer.Add(run_button, 0, wx.ALL, 5)

        back_button = wx.Button(panel, label="Go Back (Close)")
        back_button.Bind(wx.EVT_BUTTON, lambda event: self.Close())
        btn_sizer.Add(back_button, 0, wx.ALL, 5)
        vbox.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
        
        panel.SetSizer(vbox)
        self.SetSize((550, 400))
        self.SetTitle('Text Utilities')
        self.Centre()
        self.Bind(wx.EVT_CLOSE, self.on_main_close)


    def on_run_selected_tool(self, event):
        """Handles running the tool selected in the list control."""
        selected_idx = self.tool_list_ctrl.GetFirstSelected()
        if selected_idx != -1:
            tool_data_index = self.tool_list_ctrl.GetItemData(selected_idx)
            _, _, handler_method = self.text_tools_list[tool_data_index]
            if callable(handler_method):
                handler_method(event)
            else:
                wx.MessageBox("Error: No valid action found for selected tool.", "Error", wx.OK | wx.ICON_ERROR, self)

    def on_main_close(self, event):
        """Handles closing the main TextUtilitiesApp window."""
        for frame in list(self.child_frames):
            if frame:
                try:
                    frame.Close()
                except (wx.PyDeadObjectError, RuntimeError):
                    pass # Frame might have been closed already
        self.child_frames.clear()
        event.Skip()

    def _launch_sub_tool(self, frame_class, title):
        """Helper to launch a sub-tool, manage visibility, and track child frame."""
        sub_tool_frame = frame_class(self, title=title)
        self.add_child_frame(sub_tool_frame)
        self.Hide()
        sub_tool_frame.Show()
        return sub_tool_frame


    def OnCapitalizeText(self, event):
        self._launch_sub_tool(CapitalizeFrame, 'Capitalize Text')

    def OnSplit(self, event):
        self._launch_sub_tool(TextSplitterFrame, 'Text Splitter')

    def OnTextInfo(self, event):
        self._launch_sub_tool(TextInfoFrame, 'Text Info')

    def OnAdvancedFinder(self, event):
        self.advanced_finder_frame = self._launch_sub_tool(lambda parent, title: AdvancedFinder(parent, title), 'Advanced Finder')
        self.advanced_finder_frame.Raise()

    def OnJsonViewer(self, event):
        self._launch_sub_tool(JsonViewer, 'JSON Viewer')

    def OnTextCleaner(self, event):
        self.text_cleaner_frame = self._launch_sub_tool(lambda parent, title: TextCleaner(parent, title), 'Text Cleaner')

    def OnXMLViewer(self, event):
        self.xml_viewer_frame = self._launch_sub_tool(lambda parent, title: XMLViewer(parent, title), 'XML Viewer')
        self.xml_viewer_frame.Raise()

    def add_child_frame(self, frame):
        self.child_frames.append(frame)
        frame.Bind(wx.EVT_CLOSE, lambda event, f=frame: self.on_child_tool_close(event, f))

    def on_child_tool_close(self, event, frame_being_closed):
        """Called when a sub-tool (child frame) is closed."""
        if frame_being_closed in self.child_frames:
            self.child_frames.remove(frame_being_closed)
        
        if self.IsShown():
            pass
        elif not self.child_frames:
             self.Show()
             self.Raise()
        
        if event.GetEventObject() == frame_being_closed:
            frame_being_closed.Destroy()


class TextInfoFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super(TextInfoFrame, self).__init__(*args, **kw)
        self.SetBackgroundColour(wx.Colour(240, 240, 240)) # Light gray background

        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)

        vbox = wx.BoxSizer(wx.VERTICAL)

        text_label = wx.StaticText(panel, label='Input text: ')
        vbox.Add(text_label, flag=wx.LEFT | wx.TOP, border=10)

        self.text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.text_ctrl.SetBackgroundColour(wx.Colour(250, 250, 250)) # Very light gray
        self.text_ctrl.SetForegroundColour(wx.Colour(30, 30, 30))  # Dark gray text
        vbox.Add(self.text_ctrl, 1, flag=wx.EXPAND | wx.ALL, border=10)

        info_btn = wx.Button(panel, label='Show Text Info', size=(150, 30))
        info_btn.Bind(wx.EVT_BUTTON, self.OnShowInfo)
        info_btn.SetBackgroundColour(wx.Colour(100, 150, 200))  # Muted blue
        info_btn.SetForegroundColour(wx.Colour(255, 255, 255))  # White text
        vbox.Add(info_btn, flag=wx.EXPAND | wx.ALL, border=10)

        panel.SetSizer(vbox)

        self.SetSize((500, 400))
        self.SetTitle('Text Info')
        self.Centre()

    def OnShowInfo(self, event):
        text = self.text_ctrl.GetValue()

        line_count = len(text.split('\n'))
        word_count = len(text.split())
        char_count = len(text)
        info_str = f'Total lines: {line_count}, Total Words: {word_count}, Total Characters: {char_count}'
        wx.MessageBox(info_str, 'Text Information', wx.OK | wx.ICON_INFORMATION)