import wx.lib.newevent
import threading
import os
import re

SearchProgressEvent, EVT_SEARCH_PROGRESS = wx.lib.newevent.NewEvent()
SearchDoneEvent, EVT_SEARCH_DONE = wx.lib.newevent.NewEvent()

class SearchWorkerThread(threading.Thread):
    """
    Worker thread for performing file searches in the background.
    Communicates progress and results back to the GUI via events.
    """
    def __init__(self, wx_frame, search_term, search_roots, use_regex):
        super().__init__()
        self.wx_frame = wx_frame
        self.search_term = search_term
        self.search_roots = search_roots
        self.use_regex = use_regex
        self._running = True
        self.files_searched = 0
        self.matches_found = 0
        self.results = []
        self.regex = None

        if self.use_regex:
            try:
                self.regex = re.compile(self.search_term, re.IGNORECASE)
            except re.error as e:
                self._running = False
                self.error_message = f"Invalid Regular Expression: {e}"
                return
        else:
            self.search_term_lower = self.search_term.lower()
        self.error_message = None


    def run(self):
        if not self._running:
            wx.PostEvent(self.wx_frame, SearchDoneEvent(results=[], files_searched=0, matches_found=0, error=self.error_message))
            return

        for root_dir in self.search_roots:
            if not self._running:
                break
            try:
                for root, _, files in os.walk(root_dir, topdown=True, onerror=lambda e: None):
                    if not self._running:
                        break
                    for filename in files:
                        if not self._running:
                            break
                        self.files_searched += 1
                        match = False
                        try:
                            if self.use_regex:
                                if self.regex and self.regex.search(filename):
                                    match = True
                            else:
                                if self.search_term_lower in filename.lower():
                                    match = True

                            if match:
                                self.matches_found += 1
                                filepath = os.path.join(root, filename)
                                try:
                                    size = os.path.getsize(filepath)
                                except OSError:
                                    size = -1
                                self.results.append((filename, filepath, size))
                        except Exception:
                            continue # Skip problematic file

                        if self.files_searched % 100 == 0:
                            wx.PostEvent(self.wx_frame, SearchProgressEvent(
                                files_searched=self.files_searched,
                                matches_found=self.matches_found
                            ))
            except Exception:
                 continue

        wx.PostEvent(self.wx_frame, SearchDoneEvent(results=self.results, files_searched=self.files_searched, matches_found=self.matches_found, error=None if self._running else "Cancelled"))

    def stop(self):
        self._running = False
