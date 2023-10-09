
<p align="center"><img src="https://user-images.githubusercontent.com/21298211/171323258-5818355a-2c55-444b-8d0d-b0e3feee36e4.png" /> </>

[![GitHub Releases](https://img.shields.io/github/downloads/elibroftw/music-caster/latest/total?color=blue&label=github%20downloads%40latest&style=for-the-badge)](https://github.com/elibroftw/music-caster/releases/latest)
[![Source Forge](https://img.shields.io/sourceforge/dt/music-caster?color=orange&label=SourceForge%20downloads&style=for-the-badge)](https://sourceforge.net/projects/music-caster/)

Music Caster is a modern music player with the ability to cast audio files, system audio, and URLs to Google Chromecasts, Google Home/Nest Minis, etc.

Display languages: English, German, Spanish, French, Italian, Dutch, Russian\*, and Ukrainian\*

Unique users as of April 23rd 2023: 3,800

[Screenshots](https://elijahlopez.ca/music-caster/)

### Donate or Translate

- monero:84PR6SkYd5zaFLKDjAFrQfbaAg2c7SV3q3XDZ15QCpEZUggrN4YzY7n8m9XC3deXjo41yWHTm1LrsUpPTYGnRQbD9Cwp8En
- [PayPal](https://www.paypal.me/elibroftw)
- [Translate](https://github.com/elibroftw/music-caster/issues/12#issuecomment-808658776) Music Caster to other languages

## Install

### [Windows Download Music.Caster.Setup.exe](https://github.com/elibroftw/music-caster/releases/latest)

- **IMPORTANT INFORMATION:** The tray icon will be in the tray, so you will need to move it to your taskbar
- Command line installation: `winget install "Music Caster"`
- [VirusTotal scan](https://www.virustotal.com/gui/file/40a1c61e5cb2c5eed714eb70bb84f138e9fd9742076ea665b4ac85fc8f372abf)
  - If Music Caster is auto-removed, open "Virus & threat protection", then "protection history," and restore all files related to Music Caster

### Linux

Not maintained, but I did get it to work on Ubuntu once. Music Caster is not straight forward to package, so you can invoke a sudo-free [install script](linux_install.sh).

```bash
mkdir -p ~/bin && git clone --depth 1 https://github.com/elibroftw/music-caster.git ~/bin/music-caster
~/bin/music-caster/linux_install.sh
```

## Demo

<a href="https://www.youtube.com/watch?v=5xwHkLPgvtQ" title="Music Caster Video Demo">
  <p align="center">
    <img width=75% src="https://img.youtube.com/vi/5xwHkLPgvtQ/maxresdefault.jpg" alt="Music Caster Video Demo Thumbnail"/>
  </p>
</a>

## Limitations

- Chromecasts only support the AAC version of WMA files
- Emojis might not work well. There's always settings.json + WEB GUI though
- [Road Map](https://github.com/elibroftw/music-caster/projects/1)

## Power User Features

- Global media hot-keys are supported
- Web GUI (QR code in Settings window)
- [Command Line Arguments](https://github.com/elibroftw/music-caster/wiki/Command-Line-Arguments)

Here are Music Caster specific keyboard shortcuts aside from the global media hot-keys.

| **Shortcut**           | **Window** | **Behaviour**                  |
|------------------------|------------|--------------------------------|
| Ctrl + Shift + Alt + M | Global     | Activate Main Window           |
| Ctrl + (Shift) + }     | Main       | Toggle mini-mode               |
| Esc                    | Main       | Close Window                   |
| Ctrl + Shift + Q       | Main       | Exit Program                   |
| Scroll                 | Main       | Volume and Progress Bar        |
| ⬆ / A                  | Main       | Decrease Volume by 5%          |
| ⬇ / D                  | Main       | Increase Volume by 5%          |
| #                      | Main       | Set Volume to # * 10%          |
| K                      | Main       | Pause / Resume / Start Playing |
| Shift + N              | Main       | Next Track                     |
| Shift + P / Shift + B  | Main       | Previous Track                 |
| J                      | Main       | Rewind 5 seconds               |
| L                      | Main       | Fast-forward 5 seconds         |
| Ctrl + R               | Main       | Cycle Repeat                   |
| Ctrl + M               | Main       | Mute                           |
| Ctrl + 1               | Main       | Go to Tab 1 (Queue)            |
| Ctrl + 2               | Main       | Go to Tab 2 (URL)              |
| Ctrl + 3               | Main       | Go to Tab 3 (Library)          |
| Ctrl + 4               | Main       | Go to Tab 4 (Playlists)        |
| Ctrl + 5               | Main       | Go to Tab 5 (Timer)            |
| Ctrl + 6               | Main       | Go to Tab 6 (Metadata)         |
| Ctrl + 7               | Main       | Go to Tab 7 (Settings)         |

### Editing `settings.json`

- I do not recommend editing unless you know what you are doing
- Music Caster will detect changes within 10 seconds of editing `settings.json`
- Some settings values are hidden from the GUI for good reason

## Data Collection / Privacy Policy

Below is the reasonable data that is collected when errors are encountered. I'm sure other programs collect
way more than necessary.

```python
# in handle_exception,
payload = {'VERSION': VERSION, 'FATAL': restart_program, 'EXCEPTION TYPE': exc_type.__name__,
           'LINE': exc_tb.tb_lineno, 'TRACEBACK': trace_back_msg, 'LOG': log_lines,
           'MQ[0]': playing_uri, 'PLAYING_STATUS': str(playing_status), 'DEVICE': device,
           'CWD': os.getcwd(), 'PORTABLE': not os.path.exists(UNINSTALLER),
           'MAC': hashlib.md5(get_mac().encode()).hexdigest(), 'OS': platform.platform(), 'TIME': current_time}
```

In addition, I collect MD5 hashed MAC addresses and IP addresses in a Google Excel Sheet.
Only I have access to this data, I will NEVER give it to anyone else. Will stop collecting analytics once I stop caring about the number of users.

- Hashed MAC so that I know how many users without knowing the actual MAC addresses
- IP because I can map out the IPs to a visual map to see where my users are located

[Developer Guide](https://github.com/elibroftw/music-caster/wiki/Developer-Guide)

### Virtualenv

```
python -m venv venv
```
