import wx
import wx.adv
import concurrent.futures
from google import genai
from speech import speak

class GeminiChat(wx.Frame):
    def __init__(self, parent, title="Gemini Chat"):
        super().__init__(parent, title=title, size=(700, 600))
        self.config = parent.config
        self.api_key = self.config.get('Gemini', {}).get('api_key')
        self.chat = None
        self.history = []
        self.models = {}

        if not self.api_key:
            wx.MessageBox("Gemini API key not found. Please set it in the AI Services settings.", "API Key Missing", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Close)
            return

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        try:
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            wx.MessageBox(f"Failed to initialize Gemini client: {e}", "Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Close)
            return

        self.setup_ui()
        self.Centre()
        self.Show()
        self.executor.submit(self.fetch_models).add_done_callback(self.on_models_fetched)

    def setup_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        messages_label = wx.StaticText(panel, label="Messages list:")
        self.messages_list = wx.ListBox(panel)
        sizer.Add(messages_label, 0, wx.LEFT | wx.TOP, 5)
        sizer.Add(self.messages_list, 1, wx.EXPAND | wx.ALL, 5)

        prompt_label = wx.StaticText(panel, label="Your Prompt:")
        self.prompt_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        sizer.Add(prompt_label, 0, wx.LEFT | wx.TOP, 5)
        sizer.Add(self.prompt_text, 0, wx.EXPAND | wx.ALL, 5)

        self.send_button = wx.Button(panel, label="Send")
        sizer.Add(self.send_button, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        model_sizer = wx.BoxSizer(wx.HORIZONTAL)
        model_label = wx.StaticText(panel, label="Model:")
        self.model_combo = wx.ComboBox(panel, style=wx.CB_READONLY | wx.CB_SORT)
        model_sizer.Add(model_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        model_sizer.Add(self.model_combo, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(model_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        self.Layout()

        self.send_button.Bind(wx.EVT_BUTTON, self.on_send)
        self.model_combo.Bind(wx.EVT_COMBOBOX, self.on_model_change)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def fetch_models(self):
        try:
            models_list = self.client.models.list()
            for m in models_list:
                if 'generate_content' in m.supported_actions:
                    if m.description:
                        label = f"{m.display_name}: {m.description}\n\nInternal name: {m.name}"
                    else:
                        label = f"{m.display_name}, {m.name}"
                    self.models[label] = m.name
            return list(self.models.keys())
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Failed to fetch Gemini models: {e}", "Error", wx.OK | wx.ICON_ERROR)
            return []

    def on_models_fetched(self, future):
        models = future.result()
        if models:
            self.model_combo.SetItems(models)
            default_model_name = self.config.get('Gemini', {}).get('default_model')
            if default_model_name:
                for label, name in self.models.items():
                    if name == default_model_name:
                        self.model_combo.SetStringSelection(label)
                        break
            if self.model_combo.GetSelection() == wx.NOT_FOUND:
                self.model_combo.SetSelection(0)
            self.on_model_change(None)

    def on_model_change(self, event):
        selection = self.model_combo.GetStringSelection()
        if not selection:
            return
            
        model_name = self.models.get(selection)
        if not model_name:
            return

        if 'Gemini' not in self.config:
            self.config['Gemini'] = {}
        self.config['Gemini']['default_model'] = model_name
        self.config.write()
        self.chat = self.client.chats.create(model=model_name, history=self.history)

    def on_send(self, event):
        prompt = self.prompt_text.GetValue().strip()
        if not prompt:
            return

        self.messages_list.Append(f"You: {prompt}")
        self.prompt_text.Clear()
        self.send_button.Disable()
        speak("Gemini is typing...")
        self.executor.submit(self.send_message_worker, prompt).add_done_callback(self.on_send_complete)

    def send_message_worker(self, prompt):
        try:
            if not self.chat:
                selected_model_label = self.model_combo.GetStringSelection()
                selected_model_name = self.models.get(selected_model_label)
                if not selected_model_name:
                    wx.CallAfter(wx.MessageBox, "Please select a valid model.", "Error", wx.OK | wx.ICON_ERROR)
                    return None
                self.chat = self.client.chats.create(model=selected_model_name, history=self.history)

            response = self.chat.send_message(prompt)
            return response
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"An error occurred with Gemini: {e}", "Error", wx.OK | wx.ICON_ERROR)
            return None

    def on_send_complete(self, future):
        response = future.result()
        if response and response.text:
            self.messages_list.Append(f"Gemini: {response.text}")
            self.messages_list.SetSelection(self.messages_list.GetCount() - 1)
            self.history = self.chat.get_history(curated=True)
            speak("Gemini replied.")
        else:
            last_item_index = self.messages_list.GetCount() - 1
            if last_item_index >= 0:
                if self.messages_list.GetString(last_item_index).startswith("You:"):
                    self.messages_list.Delete(last_item_index)

        self.send_button.Enable()

    def on_close(self, event):
        self.executor.shutdown(wait=False)
        self.GetParent().on_child_tool_close(self)
        self.Destroy()
