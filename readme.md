# Introduction

Access Hub is a multifunctional app designed with accessibility in mind that aims to include the most useful tools in one place, Without having to install lots of apps for your daily tasks. This app bundles a collection of powerful tools in one place, While focusing on each function within the app itself to be as better as possible.

Please note the following:

The app may not be ready for public use, It is for beta testing for now. Though the app is mostly very stable enough in most tasks: You might find bugs, Because this is a beta version, and since this is the first version.

Some features are not yet well-designed due to some reasons.

There are, of course, some undiscovered bugs I might not know about them. Please help by testing the app and leave your feedback by contacting me, Find contact info section below.

# What does this have?

Currently: The app has a small number of tools which are as follows.

- Text Utilities: The main "Text Utilities" window provides access to the following tools:
    - **Text Splitter:** Splits text by character count, lines, or words. Options include numbering elements and ignoring blank lines.
    - **Text Info:** Displays statistics about the input text, such as total lines, words, and characters.
    - **Capitalize Text:** Converts the first letter of each line of text to uppercase.
    - **Advanced Finder:** A powerful tool to search for text within multiple files or text inputs. It supports plain text and regular expression searches. Results can be reviewed, and text can be replaced individually or in bulk. Modified files/texts can be saved to a specified location.
    - **Text Cleaner:** Processes and cleans text from multiple files. Cleaning options include removing leading/trailing spaces, normalizing line endings, stripping comments (e.g., `#`, `//`, `/* */`), removing HTML tags, deleting duplicate lines, and removing empty lines. Cleaned files are saved to a chosen destination.
    - **JSON Viewer:** Opens, displays, and allows editing of JSON files. Data is shown in a tree view. Users can modify values, add new elements to objects/arrays, and save changes.
    - **XML Viewer:** Provides a way to view and edit XML files. It displays the XML in a tree structure and as raw text. Features include adding/editing/removing elements and attributes, and saving modifications.
- Task Scheduler: The Task Scheduler allows you to automate various actions and set reminders. Tasks are saved and will persist even if the application is restarted.
- Shutdown control: Allows you to shutdown or restart the device at a spicific time.
- Password doctor: Check your password integrity and password breaches.
- Network player: Play youtube videos, direct links, as well as download youtube videos. More detailed explanation to this tool below.
- Eleven Labs: Provides a comprehensive interface for interacting with various features of the ElevenLabs API, allowing for advanced voice generation and manipulation. An API key is required and can be configured in the application settings.
- Accessible terminal: An accessible SSH terminal with file manager and other features. More detailed explanation below.
- Internet speed test: A simple tool to check your internet speed test.
- Speech to text recognition: More detailed explanation below.

## Task Scheduler Features

**Scheduled Task Types:**

*   **Alarms:**
    *   **Configuration:** Set a specific time (hour, minute, second, AM/PM) and date (day, month) for the alarm.
    *   **Scheduling Options:**
        *   **Once:** Triggers only on the specified date and time.
        *   **Daily:** Repeats every day at the set time.
        *   **Weekly:** Repeats on the same day of the week as the initial date, at the set time.
        *   **Custom Days:** Choose specific days of the week (e.g., Monday, Wednesday, Friday) for the alarm to repeat.
    *   **Sound:** Select from a list of built-in alarm sounds or browse for your own custom sound file (supports MP3, WAV, OGG, FLAC). Sound previews are available.
    *   **Snooze:** Configure how many times you can snooze (0-10 times) and the snooze interval (1-60 minutes).
    *   **Notification:** When an alarm triggers, a notification window appears, playing the selected sound. You can "Stop Alarm" or "Snooze" (if available). If ignored, the alarm may automatically snooze or stop after a set duration. Snoozed alarms are rescheduled as temporary "Once" tasks.
*   **Run a Script:**
    *   Schedule a script (e.g., `.py`, `.bat`, `.exe`) or any executable file to run at a specified time (set by hours and minutes from the current time).
*   **Open a Website:**
    *   Schedule a specific website URL to be opened in your default web browser at a set time (relative hours/minutes).
*   **Play a Media File:**
    *   Schedule a media file (audio or video) to be opened with the system's default player at a chosen time (relative hours/minutes).
*   **Send a Reminder Notification:**
    *   Set up a system notification with a custom title and message to appear at a scheduled time (relative hours/minutes).

**Managing Tasks:**
*   The main Task Scheduler window lists all your upcoming scheduled tasks, showing their name, type, scheduled time, and details.
*   You can remove any selected task from the list.

## Eleven Labs Features

**Key Features:**

*   **Text-to-Speech (TTS):**
    *   Convert text into speech using voices from your ElevenLabs account.
    *   Select from available TTS models.
    *   Fine-tune voice characteristics using settings like Stability, Similarity Boost, Style Exaggeration, and Speaker Boost.
    *   View estimated character usage before generation.
    *   Save generated audio as MP3 files.

*   **Speech-to-Speech (STS):**
    *   Transform the voice in an existing audio file into a different voice from your library.
    *   Select the target voice and STS model.
    *   Adjust voice settings for the conversion.
    *   Options include background noise removal.
    *   Save the converted speech as an MP3 file.

*   **Audio Isolation:**
    *   Upload an audio file to isolate speech by removing background noise or music.
    *   Outputs the cleaned audio as an MP3.
    *   Provides character usage estimates based on audio duration.

*   **Sound Effects Generation:**
    *   Generate sound effects from text prompts.
    *   Control the duration of the generated sound (manual or automatic).
    *   Adjust "Prompt Influence" to guide the generation.
    *   Save the generated sound effect as an MP3.

*   **Voice Management (via "Voices" Menu):**
    *   **Your Voices:**
        *   Browse and manage voices in your personal ElevenLabs library.
        *   Edit voice settings (Stability, Similarity, Style, Speed, Speaker Boost).
        *   Preview voice audio samples.
        *   Delete voices from your library.
    *   **Voice Library (Shared Voices):**
        *   Explore a vast library of publicly shared voices.
        *   Search and filter voices.
        *   Preview shared voices.
        *   Add interesting shared voices to your personal library.
    *   **Voice Cloning:**
        *   Create new voice clones by uploading one or more audio samples.
        *   Provide a name and optional description for the cloned voice.
        *   Option to remove background noise from samples during cloning.
    *   **Add Voice from Prompt (Voice Design):**
        *   Design new synthetic voices by providing a text description of the desired voice characteristics.
        *   Adjust generation parameters like Loudness, Quality, and Guidance Scale.
        *   Generate multiple audio previews based on your prompt.
        *   Listen to previews and add your chosen designed voice to your personal library.

## File Utilities

- **Advanced File Search:** Searches for files across specified drives or the entire device. Users can search by filename or pattern, with an option for regular expressions. Results are displayed in a list, allowing users to copy file paths or open the file's location.
- **Multiple File Rename:** Renames multiple files based on user-defined criteria. Files can be added individually or by folder. Renaming options include:
    - Using regular expressions to find and replace parts of filenames.
    - Sequential numbering (e.g., using `#` in the search pattern like `image-#.jpg` to `image-001.jpg`).
    - Changing file extensions.
    Renamed files are saved to a specified output folder.

## Network Player

The Network Player offers a rich multimedia experience, especially tailored for YouTube, but also supporting direct media links.

**Core Features:**

*   **YouTube Search:**
    *   Search YouTube directly within the app.
    *   Results display title, duration, and uploader.
    *   Option to load more results.
*   **YouTube Link Playback:**
    *   Paste YouTube links (video or playlist) to stream directly.
    *   Choose playback mode: "Video" or "Audio-only".
    *   Select video quality when pasting: Low, Medium, or Best.
*   **Direct Link Playback:**
    *   Play media streams from generic URLs (e.g., online radio, direct video/audio links).
*   **Playback Controls:**
    *   Standard controls: Play/Pause, Rewind, Forward.
    *   Adjust volume and playback speed.
    *   Seek to specific percentages or time points.
*   **Subtitle Support (YouTube):**
    *   Lists available manual and automatic subtitles for a video.
    *   Downloads the selected subtitle in SRT format.
    *   Displays subtitles synchronized with the video playback.
*   **Comment Viewing (YouTube):**
    *   Browse comments for a YouTube video.
    *   Comments are displayed in a sortable list showing author and text.
*   **Download Features (Primarily YouTube):**
    *   **Download Settings Dialog:**
        *   Customize filename before download.
        *   Choose download type: "Video" or "Audio".
        *   For Video: Select quality (e.g., Low, Medium, Best – actual options depend on video).
        *   For Audio: Select format (MP3, WAV, AAC, Opus, FLAC) and audio quality (e.g., 128K, 192K, Best VBR).
        *   Specify a download directory (defaults to organized subfolders in your main Downloads folder, e.g., `Downloads/AccessHub/YouTube/Video`).
    *   **Direct Download:**
        *   Quickly download using pre-configured default settings.
        *   These defaults (type, quality, format) can be set in the application's YouTube settings.
    *   A progress dialog shows download status, including percentage, downloaded size, total size, speed, and ETA.
*   **Favorites Management (YouTube):**
    *   Add YouTube videos to a local favorites list for easy access.
    *   A dedicated "Favorites" window allows browsing, playing, downloading, or removing saved favorite videos.
*   **Save Video Segment (YouTube):**
    *   While playing a YouTube video, mark a start point (`[`) and an end point (`]`).
    *   Save the selected segment as an MP3 audio file (Ctrl+S).
*   **Video Description (YouTube):**
    *   View the full text description of the currently playing YouTube video.
*   **Playlist Navigation (YouTube Search):**
    *   When playing a video from the search results, use Page Up/Page Down to navigate to the previous/next video in the results list.

**Available Keyboard Shortcuts (Player Window):**

*   **Playback Control:**
    *   `Spacebar` or `P`: Play/Pause.
    *   `Left Arrow`: Rewind (default 5 seconds, configurable).
    *   `Right Arrow`: Forward (default 5 seconds, configurable).
    *   `Home`: Go to the beginning of the video.
    *   `End`: Go to the end of the video.
    *   `Control + Up Arrow`: Increase playback speed.
    *   `Control + Down Arrow`: Decrease playback speed.
    *   `S`: Announce current playback speed.
    *   `Page Up`: Previous video (if playing from search results or playlist).
    *   `Page Down`: Next video (if playing from search results or playlist).
*   **Volume Control:**
    *   `Up Arrow`: Increase volume.
    *   `Down Arrow`: Decrease volume.
    *   `V`: Announce current volume.
*   **Information & Display:**
    *   `E`: Announce elapsed time (HH:MM:SS).
    *   `R`: Announce remaining time (HH:MM:SS).
    *   `T`: Announce total time (HH:MM:SS).
    *   `F`: Toggle full-screen mode (for video playback).
    *   `Shift + T`: Announce video title.
    *   `Shift + P`: Announce current playback percentage.
*   **Seeking:**
    *   `0-9`: Jump to 0% to 90% of the video respectively.
    *   `Shift + 0-9`: Jump to 5%, 15%, ..., 95% of the video respectively.
*   **Segment Selection (YouTube):**
    *   `[` or `{`: Mark selection start.
    *   `]` or `}`: Mark selection end.
    *   `Control + S`: Save selected segment as MP3.
*   **General:**
    *   `Alt Key`: Access the player menu (for subtitles, description, comments, etc.).
    *   `Control + C`: Copy video link to clipboard.

**Configuration Note:**

Many aspects of the Network Player, such as default download settings (type, quality, format), rewind/forward intervals, and what happens after a video finishes playing, can be customized in the application's main settings window, under the "YouTube" category.

## Accessible terminal

For users who need to manage remote servers or network devices, Access Hub includes an Accessible SSH Terminal. What makes it different is that there are some users who don't like the default style of windows terminal, Which sometimes is not as good as a normal textbox, This is the main reason behind this tool.

Session Management: Save and manage your SSH connection details for frequent access, securely storing session information with encryption.

File Manager Integration: Seamlessly transition to a file manager view for your SSH session, allowing for graphical file browsing and transfer on the remote server.

## Speech recognition

Access Hub includes a basic speech recognition using "Google", Allowing you to record a phrase and automatically type it anywhere. The reason behind this feature is that windows speech recognition by default is not good. Though access Hub has a basic speech recognition that only supports one service for now: there are plans to develop this in the future.

The shortcut for start recording is control + shift + h. Press once to record, Again to type the result.

Please note that it automatically detects and uses your keyboard language, There is no way of changing the language for now without changing the keyboard language, Though this will be added in the future.

## Online Text-to-Speech (TTS)

The Online TTS tool allows you to convert text into speech using online services.

**Main Features:**
*   **Input Text:** Enter text directly into the text area.
*   **Speech Generation:**
    *   **Manual Mode:**
        *   Select the desired language and specific voice from the available options (powered by Microsoft Speech Services).
        *   Adjust speech parameters:
            *   **Rate:** Controls the speed of the speech (-100 to 100).
            *   **Pitch:** Adjusts the pitch of the voice (-100 to 100).
            *   **Volume:** Sets the volume of the generated audio (1 to 100).
    *   **Auto-detect Language Mode:**
        *   When enabled, the tool attempts to automatically detect the language of the input text.
        *   It will try to use a suitable voice from Microsoft Speech Services if available for the detected language.
        *   If a Microsoft voice isn't found for the detected language, it will use Google Text-to-Speech (gTTS) as a fallback.
*   **Output:** Generates an MP3 audio file of the spoken text. You will be prompted to choose a location to save the file.

**Batch Processing:**
*   The tool also includes a batch processing feature to convert multiple text inputs to speech in one go.
*   **Input Sources for Batch:**
    *   **Add Text:** Manually add individual text snippets to the batch list.
    *   **Select Files:** Add multiple text files; the content of each file will be processed.
*   **Output for Batch:**
    *   You'll be asked to select an output directory for all generated MP3 files.
    *   Files generated from input text files will retain the original filename (e.g., `document.txt` becomes `document.mp3`).
    *   Files generated from manually added text will be named sequentially (e.g., `output_1.mp3`, `output_2.mp3`).
*   The batch process uses the language, voice (if in manual mode), and speech parameter settings currently active in the main Online TTS window.

## Application Updater

Access Hub includes an automatic update checker to help you stay current with the latest features and fixes.

**How it Works:**
*   On startup, the application can check a designated server for a new version.
*   If a newer version is found, you will be notified and asked if you wish to download and install the update.
*   If you choose to update, the new version will be downloaded. A progress dialog will show the download status (file name, size, percentage complete, and a cancel option).
*   Once the download is complete, the application will attempt to launch the installer for the new version. You may need to grant administrative privileges for the installer to run.
*   The main application will typically close after launching the installer.

**Notes:**
*   An active internet connection is required for the update check and download.
*   The update process involves downloading an installer file, which then handles the actual update of the application files.

## Application Settings

Access Hub provides a settings dialog where you can customize various aspects of the application's behavior and the functionality of its tools. These settings are saved in a configuration file (`settings.ini`) located in your user-specific application data directory.

You can typically access the settings through a "Settings" or "Preferences" option in the main application menu (e.g., under "File" or "Edit").

The settings are organized into categories. Here's an overview of what you can configure:

**General Settings:**
*   **Minimize to tray on close:** Choose whether closing the main window minimizes the application to the system tray or exits it.
*   **Hide main window when opening tools:** Decide if the main Access Hub window should automatically hide when you launch one of its tools.
*   **Check for updates at startup:** Enable or disable automatic checking for new versions of Access Hub when it starts.

**Tool-Specific Settings:**
Many individual tools also have their own settings that can be adjusted here. For example:
*   **Network Player (YouTube):**
    *   Configure default playback behaviors like fast forward/rewind intervals and default volume.
    *   Set your preferred default video playback quality.
    *   Define what happens after a video finishes (e.g., close player, replay).
    *   Choose the update channel for `yt-dlp` (the underlying YouTube downloader).
    *   Set default download preferences:
        *   Default type (Video or Audio).
        *   Default video quality for downloads.
        *   Default audio format (e.g., MP3, WAV) and quality for audio downloads.
        *   Specify a default directory for your downloads.
*   **ElevenLabs:**
    *   Securely store your ElevenLabs API key, which is required to use the ElevenLabs integration.

Other tools may also have configurable options available in their respective settings sections. Exploring the Settings dialog is recommended to tailor Access Hub to your preferences.

## Contact me

Please help me by reporting bugs and leaving your feedback thrugh the following ways:

[Telegram: Diamond Star](https://t.me/diamondStar35)

[Official telegram group](https://t.me/access_hub_discussion)

[WhatsApp](https://wa.me/201067573360)

[Email](mailto:ramymaherali55@gmail.com)

You can always get my contact info thrugh the main menu of the app, By pressing alt and choosing contact us. Choose the appropriate method that works well for you.