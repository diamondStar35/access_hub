import wx

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
        self.split_frame = None
        self.capitalize_frame = None
        self.text_info_frame = None
        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)

        vbox = wx.BoxSizer(wx.VERTICAL)

        hbox = wx.BoxSizer(wx.HORIZONTAL)

        split_btn = wx.Button(panel, label='Split Text', size=(150, 30))
        split_btn.Bind(wx.EVT_BUTTON, self.OnSplit)
        hbox.Add(split_btn, flag=wx.RIGHT, border=5)

        text_info_btn = wx.Button(panel, label='Text Info', size=(150, 30))
        text_info_btn.Bind(wx.EVT_BUTTON, self.OnTextInfo)
        hbox.Add(text_info_btn)

        capitalize_btn = wx.Button(panel, label='Capitalize Text', size=(150, 30))
        capitalize_btn.Bind(wx.EVT_BUTTON, self.OnCapitalizeText)
        hbox.Add(capitalize_btn)

        vbox.Add(hbox, flag=wx.EXPAND | wx.RIGHT, border=10)

        panel.SetSizer(vbox)

        self.SetSize((500, 400))
        self.SetTitle('Text Utilities')
        self.Centre()
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, event):
        for frame in self.child_frames:
            frame.Close()
        event.Skip()

    def on_child_close(self, event, frame):
        if frame in self.child_frames:
            self.child_frames.remove(frame)
        event.Skip()


    def OnCapitalizeText(self, event):
        self.capitalize_frame = CapitalizeFrame(None, title='Capitalize Text')
        self.capitalize_frame.Show()
        self.add_child_frame(self.capitalize_frame)

    def OnSplit(self, event):
        self.split_frame = TextSplitterFrame(None, title='Text Splitter')
        self.split_frame.Show()
        self.add_child_frame(self.split_frame)

    def OnTextInfo(self, event):
        self.text_info_frame = TextInfoFrame(None, title='Text Info')
        self.text_info_frame.Show()
        self.add_child_frame(self.text_info_frame)

    def add_child_frame(self, frame):
        self.child_frames.append(frame)
        frame.Bind(wx.EVT_CLOSE, lambda event, f=frame: self.on_child_close(event, f))


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