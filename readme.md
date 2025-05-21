# Introduction

Access Hub is a multifunctional app designed with accessibility in mind that aims to include the most useful tools in one place, Without having to install lots of apps for your daily tasks. This app bundles a collection of powerful tools in one place, While focusing on each function within the app itself to be as better as possible.

Please note the following:

The app may not be ready for public use, It is for beta testing for now. Though the app is mostly very stable enough in most tasks: You might find bugs, Because this is a beta version, and since this is the first version.

Some features are not yet well-designed due to some reasons.

There are, of course, some undiscovered bugs I might not know about them. Please help by testing the app and leave your feedback by contacting me, Find contact info section below.

# What does this have?

Currently: The app has a small number of tools which are as follows.

- Text Utilities: A collection of tools for manipulating and analyzing text, detailed further below.
- Task Scheduler: The Task Scheduler allows you to automate various actions and set reminders. Tasks are saved and will persist even if the application is restarted.
- Shutdown control: Allows you to shutdown or restart the device at a spicific time.
- Password doctor: Check your password integrity and password breaches.
- Network player: Play youtube videos, direct links, as well as download youtube videos. More detailed explanation to this tool below.
- Eleven Labs: Provides a comprehensive interface for interacting with various features of the ElevenLabs API, allowing for advanced voice generation and manipulation. An API key is required and can be configured in the application settings.
- Accessible terminal: An accessible SSH terminal with file manager and other features. More detailed explanation below.
- Internet speed test: A simple tool to check your internet speed test.
- Speech to text recognition: More detailed explanation below.

## Text Utilities Detailed

The Text Utilities suite offers a range of tools for text manipulation and analysis. The Text Splitter allows you to break down large blocks of text based on various criteria, such as by a specific number of characters, by lines, or by words. It offers options to include element numbers in the output and to ignore blank lines when splitting. For analyzing your text, the Text Info tool provides quick statistics, including the total count of lines, words, and characters. You can easily capitalize the first letter of each line using the Capitalize Text feature. For more advanced needs, the Advanced Finder helps locate and replace text across multiple files or text inputs, supporting both plain text and regular expression searches; it also allows for reviewing matches and saving modified content. The Text Cleaner tool is designed to tidy up text from various files by removing redundant elements like leading/trailing spaces, normalizing line endings, stripping out comments (supporting common styles like Python's #, C-style // and /* */), removing HTML tags, and deleting duplicate or empty lines, with the cleaned output saved to a specified destination. Furthermore, specialized viewers are available: the JSON Viewer can open, display (in a tree structure), and edit JSON files, allowing modification of values and the addition of new elements to objects or arrays, with changes savable to the original or a new file. Similarly, the XML Viewer offers capabilities to view XML in both tree and raw text formats, and supports adding, editing, or removing elements and attributes, as well as saving any modifications.

## Task Scheduler Features

The Task Scheduler is a versatile tool designed to help you automate various actions and manage reminders effectively. It supports several types of scheduled events, ensuring your tasks are executed even if the application is restarted.

One of the primary features is the ability to set comprehensive Alarms. You can configure an alarm with a precise time (hour, minute, second, AM/PM) and a specific date (day, month). Alarms offer flexible scheduling: set them to trigger "Once" for a singular event, "Daily" to repeat at the same time each day, "Weekly" to recur on the same day of the week as initially set, or on "Custom Days" where you can select specific days of the week (like Mondays, Wednesdays, and Fridays) for repetition. Sound customization is also robust; you can choose from a list of built-in alarm sounds or browse your system for a custom audio file (MP3, WAV, OGG, FLAC formats are supported), and even preview sounds before selection. For those who need a few extra minutes, the snooze functionality can be configured, allowing between 0 to 10 snoozes with an interval ranging from 1 to 60 minutes. When an alarm triggers, a notification window appears, playing the selected sound and providing "Stop Alarm" and "Snooze" (if configured) buttons. If an alarm notification is ignored, it may automatically snooze based on your settings or stop after a predetermined duration; snoozed alarms are then rescheduled as temporary "Once" tasks for their next alert.

Beyond alarms, the Task Scheduler can automate other system actions. You can "Run a Script" by scheduling any script (such as a `.py`, `.bat` file) or executable program (`.exe`) to execute at a specified future time, which is conveniently set by defining hours and minutes from the current time. Similarly, you can schedule your computer to "Open a Website" by providing its URL, or "Play a Media File" by selecting an audio or video file from your system; both of these tasks will launch in your system's default application at the relative future time you set. Lastly, the "Send a Reminder Notification" task allows you to create a custom system notification with your own title and message that will appear at the scheduled time, also set relatively in hours and minutes.

Managing your scheduled tasks is straightforward. The main Task Scheduler window provides a clear list of all your upcoming events. This list displays the name of each task, its type (e.g., Alarm, Run Script), its scheduled execution time, and other relevant details. If your plans change or a task is no longer needed, you can easily select and remove any task directly from this list.

## Eleven Labs Features

Access Hub offers a powerful suite of tools for leveraging the ElevenLabs API, enabling advanced voice generation and management. Before using these features, ensure your ElevenLabs API key is configured in the application settings.

The Text-to-Speech (TTS) functionality allows you to convert written text into high-quality spoken audio. You can select from your personal ElevenLabs voices and choose an appropriate TTS model for the conversion. To further refine the output, you can adjust voice characteristics such as Stability, Similarity Boost, Style Exaggeration, and enable Speaker Boost. The tool also provides an estimate of character usage before you commit to generation, helping you manage your API quota. All generated audio can be conveniently saved as MP3 files.

For transforming existing audio, the Speech-to-Speech (STS) feature comes into play. This allows you to upload an audio file and convert the speech within it to sound as if spoken by a different voice from your ElevenLabs library. You'll select both the target voice and an STS model, with options to adjust voice settings and remove background noise, before saving the final converted speech as an MP3.

If you need to clean up audio by separating speech from unwanted noise, the Audio Isolation tool can process an uploaded audio file to remove background music or noise, outputting the isolated speech as an MP3. This feature also provides character usage estimates based on the duration of the audio.

Beyond voice, you can also generate Sound Effects directly from text prompts. Describe the sound you need, and the tool will create it. You have control over the duration of the generated sound, which can be set manually or determined automatically by the API, and you can adjust the "Prompt Influence" to better guide the generation process. Generated sound effects are saved as MP3 files.

Extensive Voice Management capabilities are available through the "Voices" menu. Within "Your Voices," you can browse and manage all voices in your personal ElevenLabs account. This includes editing detailed voice settings like Stability, Similarity, Style, Speed, and Speaker Boost, previewing audio samples of each voice, and deleting voices you no longer need. The "Voice Library (Shared Voices)" option opens up a vast collection of publicly shared voices from the ElevenLabs community. You can search and filter this library, preview any shared voice, and add those you like to your personal voice collection. Furthermore, Access Hub provides two powerful methods for creating new voices. "Voice Cloning" allows you to create a digital replica of a voice by uploading one or more audio samples. You'll provide a name and an optional description for the clone, and there's an option to remove background noise from the uploaded samples during the cloning process. Alternatively, "Add Voice from Prompt" (Voice Design) lets you craft entirely new synthetic voices by describing the desired characteristics in text. You can adjust generation parameters such as Loudness, Quality, and Guidance Scale. The system will then generate multiple audio previews based on your description, allowing you to listen to them and select your preferred one to add to your personal voice library.

## File Utilities

Access Hub also includes a suite of File Utilities to help manage your files. The Advanced File Search tool enables you to locate files across your entire device or specific drives using filenames or more complex patterns, including regular expressions. Search results are conveniently displayed in a list, from which you can copy file paths or directly open a file's containing folder. For batch operations, the Multiple File Rename tool offers powerful ways to rename many files at once. You can add files individually or select entire folders. This tool allows for renaming based on regular expression search and replace within filenames, sequential numbering (for instance, transforming a set of images into a numbered sequence like `image-001.jpg`, `image-002.jpg`, etc., by using a '#' placeholder in the pattern), or simply changing file extensions. All renamed files are then saved to a designated output folder.

## Network Player

The Network Player offers a rich multimedia experience, especially tailored for YouTube, but also supporting direct media links.

Interaction with YouTube content is a core strength of the Network Player. You can search YouTube directly from within the application; search results conveniently display the video title, duration, and uploader, with an option to load more results for extensive searches. When you have a specific YouTube link (for either a single video or a playlist), you can paste it directly into the player to begin streaming. Upon pasting, you have the choice to play it as a full "Video" or as "Audio-only," and you can also select your preferred initial video quality (Low, Medium, or Best). Beyond just watching, the player allows you to delve deeper into YouTube content. You can view the full text description of any playing YouTube video, browse through its comments (which are displayed in a sortable list showing the author and comment text), and manage subtitles. The subtitle feature lists all available manual and automatic subtitles for a video, allows you to download your chosen one in SRT format, and then displays these subtitles synchronized with the video playback.

For general media consumption, the Network Player supports Direct Link Playback, enabling you to stream media from various generic URLs, such as online radio stations or direct links to video and audio files. Regardless of the source, comprehensive Playback Controls are at your fingertips. These include standard functions like Play/Pause, Rewind, and Forward, as well as options to adjust the volume, change the playback speed, and seek to specific percentages or time points within the media.

The player also provides robust Download Features, primarily focused on YouTube content. You can initiate downloads through the detailed Download Settings Dialog. This dialog lets you customize the filename before saving, choose the download type ("Video" or "Audio"), and select specific quality settings. For video downloads, quality options like Low, Medium, or Best are available (depending on the source video). For audio, you can pick your desired format (MP3, WAV, AAC, Opus, or FLAC) and audio quality (e.g., 128K, 192K, or Best VBR). You can also specify a custom download directory, which defaults to an organized structure within your main Downloads folder (e.g., `Downloads/AccessHub/YouTube/Video`). For quicker access, a Direct Download option uses your pre-configured default settings (these defaults for type, quality, and format can be pre-set in the application's YouTube settings). During any download, a progress dialog keeps you informed of the status, showing the percentage complete, downloaded size, total size, current speed, and estimated time remaining (ETA).

Further enhancing your YouTube experience, the Network Player includes Favorites Management. You can add any YouTube video to a local favorites list for quick and easy access later. A dedicated "Favorites" window allows you to browse, play, download, or remove videos you've saved. For capturing specific parts of a video, the Save Video Segment feature lets you mark a start point (using `[`) and an end point (using `]`) while playing a YouTube video, and then save just that selected portion as an MP3 audio file (using Ctrl+S). When playing videos found via the YouTube search, Playlist Navigation is enabled, allowing you to use Page Up and Page Down keys to move to the previous or next video in the search results list, creating a seamless viewing sequence.

**Available Keyboard Shortcuts (Player Window):**

    *   `Spacebar`: Play/Pause.
    *   `Left Arrow`: Rewind (default 5 seconds, configurable).
    *   `Right Arrow`: Forward (default 5 seconds, configurable).
    *   `Up Arrow`: Increase volume.
    *   `Down Arrow`: Decrease volume.
    *   `Home`: Go to the beginning of the video.
    *   `End`: Go to the end of the video.
    *   `Control + Up Arrow`: Increase playback speed.
    *   `Control + Down Arrow`: Decrease playback speed.
    *   `S`: Announce current playback speed.
    *   `Page Up`: Previous video (if playing from search results or playlist).
    *   `Page Down`: Next video (if playing from search results or playlist).
    *   `V`: Announce current volume.
*   **Information & Display:**
    *   `E`: Announce elapsed time (HH:MM:SS).
    *   `R`: Announce remaining time (HH:MM:SS).
    *   `T`: Announce total time (HH:MM:SS).
    *   `F`: Toggle full-screen mode. Takes effect for videos only.
    *   `p`: Announce current playback percentage.
    *   `0-9`: Jump to 0% to 90% of the video respectively.
    *   `Shift + 0-9`: Jump to 5%, 15%, ..., 95% of the video respectively.
    *   `left bracket: [` or `left brace: {`: Mark selection start.
    *   `right bracket: ]` or `right brace: }`: Mark selection end.
    *   `Control + S`: Save selected segment as MP3.
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

The Online Text-to-Speech tool enables you to convert written text into spoken audio using Microsoft online text to speech nateural voices. You can input text directly into the provided area for conversion. For speech generation, you have flexible options. In Manual Mode, you can specifically choose your desired language and voice from a list primarily powered by Microsoft Speech Services. This mode also allows for fine-tuning of the audio output by adjusting speech parameters such as Rate (controlling speed from -100 to 100), Pitch (adjusting voice pitch similarly from -100 to 100), and Volume (setting audio loudness from 1 to 100). Alternatively, you can opt for the Auto-detect Language Mode. When this is active, the tool intelligently attempts to identify the language of your input text. It will then try to use an appropriate voice from Microsoft Speech Services if one is available for the detected language. Should a Microsoft voice not be found, the tool seamlessly falls back to Google Text-to-Speech (gTTS) to perform the conversion. Regardless of the mode, the final output is an MP3 audio file of the spoken text, and you will be prompted to select a location to save this file.

For handling multiple conversions efficiently, the Online TTS tool includes a robust Batch Processing feature. This allows you to convert several text inputs to speech in a single operation. You can add content to the batch queue either by manually typing or pasting text snippets or by selecting multiple text files from your computer, where the content of each file will be processed. When the batch process runs, you will be asked to choose an output directory where all the generated MP3 files will be saved. Files created from input text files will conveniently retain their original filenames (e.g., an input file named 'document.txt' will result in 'document.mp3'). For texts added manually, the output files will be named sequentially (like 'output_1.mp3', 'output_2.mp3', and so on). It's important to note that the batch process utilizes the language, voice (if in manual mode), and speech parameter settings that are currently active in the main Online TTS window at the time of processing.

## Application Updater

To ensure you always have the latest features and improvements, Access Hub incorporates an automatic update checker. Upon startup, the application can connect to a designated server to see if a new version is available. If an update is found, you will be informed and given the option to download and install it. Should you choose to proceed, the new version will begin downloading, and a progress dialog will keep you updated on its status, showing the file name, total size, percentage complete, and providing an option to cancel the download. After the download finishes successfully, Access Hub will attempt to launch the installer for the new version. Please note that you might need to grant administrative privileges for the installer to run properly. The main application will usually close once the installer has been initiated.

An active internet connection is necessary for both checking for updates and downloading the update files. The update itself is performed by an installer program that is downloaded, which then takes care of updating the application files on your system.

## Application Settings

Access Hub allows for extensive customization through its dedicated settings dialog. These preferences control various aspects of the application's general behavior as well as the specific functionalities of its integrated tools. All configurations are conveniently saved in a settings file, located within your user-specific application data directory, ensuring your preferences persist across sessions. To access these options: Press the alt key in the main interface to access the main app menu, Then down arrow to settings, Usually the first option in the menu.

The settings are organized into logical categories for ease of use. Under "General Settings," you can tailor core application behaviors. For instance, you can decide whether closing the main window should minimize Access Hub to the system tray or exit the application entirely. You also have the option to automatically hide the main Access Hub window when you launch one of its individual tools, and you can enable or disable the automatic check for new application versions upon startup.

Tool-Specific Settings provide fine-grained control over individual components. For example, the Network Player's YouTube functionalities can be extensively customized: you can set default playback behaviors like fast forward/rewind intervals, preferred default volume, and your desired video playback quality. You can also define what action the player should take after a video finishes (e.g., close the player or replay the video), choose the update channel for the `yt-dlp` downloading engine, and configure comprehensive default download preferences, including the default type (Video or Audio), video quality for downloads, audio format (like MP3 or WAV) and quality for audio extractions, and a specific default directory for all your downloaded media. Similarly, for the ElevenLabs integration, this is where you would securely store your API key, which is essential for using its voice synthesis and management features. Many other tools within Access Hub may also offer configurable options in their respective settings categories, so exploring the Settings dialog is encouraged to fully tailor the application to your workflow and preferences.

## Contact me

Please help me by reporting bugs and leaving your feedback thrugh the following ways:

[Telegram: Diamond Star](https://t.me/diamondStar35)

[Official telegram group](https://t.me/access_hub_discussion)

[WhatsApp](https://wa.me/201067573360)

[Email](mailto:ramymaherali55@gmail.com)

You can always get my contact info thrugh the main menu of the app, By pressing alt and choosing contact us. Choose the appropriate method that works well for you.