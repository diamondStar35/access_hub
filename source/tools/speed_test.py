import wx
import concurrent.futures
import speedtest

class SpeedTest(wx.Frame):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(400, 300))
        self.parent = parent
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.SetBackgroundColour(wx.Colour(240, 240, 240))  # Light gray

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.result_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.result_text.SetBackgroundColour(wx.Colour(250, 250, 250))
        self.result_text.SetForegroundColour(wx.Colour(30, 30, 30))
        vbox.Add(self.result_text, 1, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(vbox)
        self.Centre()

        self.run_speedtest()

    def run_speedtest(self):
        """Perform speedtest in the background and update the result."""
        progress_dlg = wx.ProgressDialog("Running Speed Test", "Please wait...", maximum=100, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)

        def perform_test():
            try:
                st = speedtest.Speedtest()
                st.download()
                st.upload()
                st.get_best_server()
                results = {
                    "download": st.results.download / 1000000,  # Convert to Mbps
                    "upload": st.results.upload / 1000000,  # Convert to Mbps
                    "ping": st.results.ping
                }
                return results
            except speedtest.ConfigRetrievalError:
                wx.MessageBox("Failed to retrieve speedtest configuration.", "Error", wx.OK | wx.ICON_ERROR, parent=self)
                return None
            except speedtest.ServersRetrievalError:
                wx.MessageBox("Failed to retrieve speedtest server list.", "Error", wx.OK | wx.ICON_ERROR, parent=self)
                return None
            except speedtest.SpeedtestException as e:
                wx.MessageBox(f"An error occurred during the speed test: {e}", "Error", wx.OK | wx.ICON_ERROR, parent=self)
                return None
            except Exception as e:
                wx.MessageBox(f"An unexpected error occurred: {e}", "Error", wx.OK | wx.ICON_ERROR, parent=self)
                return None
            finally:
                progress_dlg.Update(100)
                progress_dlg.Destroy()

        def update_ui(future):
            """Update the UI with speedtest results."""
            result = future.result()
            if result:
                self.result_text.SetValue(f"Download Speed: {result['download']:.2f} Mbps\nUpload Speed: {result['upload']:.2f} Mbps\nPing: {result['ping']:.2f} ms")
            else:
                self.result_text.SetValue("Speed test failed. Please check your internet connection and try again.")

        future = self.executor.submit(perform_test)
        future.add_done_callback(lambda f: wx.CallAfter(update_ui, f))

    def on_close(self, event):
        self.parent.speed_test_frame = None  # Reset parent's reference
        self.Destroy()