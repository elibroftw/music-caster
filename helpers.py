import PySimpleGUI as Sg
import os
import socket
from functools import wraps
from contextlib import suppress
import time  # DO NOT REMOVE
import psutil
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
# FUTURE: C++ JPG TO PNG
# https://stackoverflow.com/questions/13739463/how-do-you-convert-a-jpg-to-png-in-c-on-windows-8
# Styling
fg, bg = '#aaaaaa', '#121212'
font_normal = 'SourceSans', 11
font_link = 'SourceSans', 11, 'underline'
LINK_COLOR, ACCENT_COLOR = '#3ea6ff', '#00bfff'
BUTTON_COLOR = ('#000000', ACCENT_COLOR)
Sg.change_look_and_feel('SystemDefault')
UNFILLED_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACWElEQVRo3u2ZsUsbURzHo2Bc0kkMDoYirRkcpEu7NtAubo7ZPXDo6qaL\nkyUIQtshkE6CkA79C4SqWIiLi5N2iBQ7WgRvUNvGj0OG/n737kLt9d476PuOvx9JPnn3e9/v3b1C\nwcvLy8srSQwR0CHEpi7pEDAUhzPBNq60zYS5Ou5w+kh6lQhwrUADHTgH6mig0DlQqIGErO7spN/1\nQB7IA3kg10DObnk8kAf6b4C44ZxTDmmzSp3JXPkQAF9o8oLh/AD1dcYalTwBAdzQ4lGegAB+sk4p\nT0AA35i3CVRkjClqLPKGI24ToN4x6sSHGGeB3Visw3875PcyRqb5EAN1xoxDp+Ypnwyk7zxzGh3M\n0TWQZhwCFQqMsWtcuEq2uyzkhB22WGE29oMjNI3xHrXlQ1024rB4xS9tAjaNsccmD2OQtObtOvU1\nDYqRL2hG3LtkEwjgM+XILOnxXrefZV95EtlxXRW7j7MBKlGlxhL79Mx3WxGkOdV9n7EPUabBlbFK\n+sJJ9/6RxpH+NFwrfDRmqagCRWbcaytOzXIkWBuq21auPWwlOqgrpGvpS0yr3ktLWcayWqNN1ZPb\nv5lFlh3TMv+pmqWeDBQW5ENTdj60RzUy3nLHbai7SnnRJrMzxgueq05Dxq7qHIlOPUunvpCrRFlZ\npbxob0V99Z7PMDEnZ4OiY0/19kVnRdQXRb2dGqgzOMvEeLMk6luiXpO3a6mBgsFArYQf3hH1KVE/\nTQlkHOBFdSx6VVE/Ubn/W+epgGKOOAecXvEgoV6UryT+EihMPAT28vLy8urrDgm99Mb0O5qlAAAA\nJXRFWHRkYXRlOmNyZWF0ZQAyMDE5LTA3LTE0VDAwOjQ2OjMyKzAwOjAwaWwEjwAAACV0RVh0ZGF0\nZTptb2RpZnkAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMBgxvDMAAAAASUVORK5CYII=\n'
FILLED_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACxUlEQVRo3u2ZT0hUURSHn0bjxtpIYqCElLNwEW1yWYO1yF3L2fvARVs3\nqRtX2SAIJTFgK0HQRdJeaBSDaePGlYaoYUtD8C3ScvpaKHTOfe8NOu/fQPe3PGec+bz3nN+57z7H\nsbKysrIKEy24VPFIU8dUcWkJwulihay0Qpd/dbLDOUfSq4RL1nI10JfMgaoayMscyNNAQql2dtjv\nWiAL9N8AJdHfFigWoMvscXMAnTUb0G3G2GkioIuz0iDLTQR08acDVJoKyHEch2dsptX2pxyyxwaL\nTFKkOxQpx2tqKfsQAF8p84TWQKhH7KcPdK4DXtETgHSTj9kAAZwyx10fUivvsgIC+M007T6oseyA\nAL7z3IfkJgeUo4NeCozwhk3+hHzXLG3RV6kBH+IWw6wGYm2YRX71WmrYGOljKQDqgH71qWtX7bho\nw/Uhn3zf+IMBwwT2Ux0dDLHrQ+o3rLKW6iyjg1XfxqlaYiruLvPYpsICE9wPRLpO2VfebapLN5Pz\noV1mgrB4YZwfZ42TQKLGWGOeOwFIWsoqL3teatypTyiRM5DKhnu3qyNcCqPjM51GLenynlbZ5TRm\n2TceGB23q8buPZEbjA+onTwFRlkPcBTPQBpS2ffqcWAndh+ikxI/faukN0669y/pSLxMZrj28MFX\nSzk1UOSMm1LPcWcJOTXjxmAtqeyicu3W2K9jAj9cVEgn0pfoU7mnqQA5DuNqjeZVTrZ/Of4LK48t\n5vz/qaqlmhwoDMuHpuRu0NbIG+UtO25GnSrlpnUnd6V3xGOVKcmxqzJyvhcTvGPkSK4Sncoq5aa9\nFfHJyNdcx/VGx5rKrYvMhIiPiPhiZKBq/VkmyptREV8Q8YI8rkUGcusDzYX8cEXEe0V8LyKQ7wWe\nqS2Ry4v4tpr7/3QYCSjgFWedt1fcCInn5JVEg0Be6EtgKysrK6tz/QVPmZ3Bw5RmTgAAACV0RVh0\nZGF0ZTpjcmVhdGUAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMGlsBI8AAAAldEVYdGRhdGU6bW9k\naWZ5ADIwMTktMDctMTRUMDA6NDY6MzIrMDA6MDAYMbwzAAAAAElFTkSuQmCC\n'
WINDOW_ICON = b'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'
NEXT_BUTTON_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAAepJREFUSIm1lr9r6lAUxz9ppRpBWrL5BnHRSZ07OUjHbu3gakenIgnuOri4OigiiCAEsZ1cHQqF/gFmUxDhvUFwiYoZ/PGG9xKaPvs0tvlC4J57D+eTc3LuvREkSfoJBHBPcw/ww0UAQMADzPmbSTKZ5OXl5aRIXq+XUChk2dvtltFoBDAXJEnSTchsNqPRaKAoimNIIpGg3+9b9mKxIBwOA8zP3jtut1seHh54e3vj+vraEUQQBNvj9/utNRtkuVwCEIlE6PV6lMvloyG73c5mr1ar/RBBEGyOmUyGwWBAKpU6GrZPZ4ccgsEgnU6HSqWCz+dzB2IqnU6jaRq3t7fuQQCurq5oNpvUajUuLy/dgZi6u7tD0zTu7++tOY/H870QAFEUqVarqKpKNBpF1/V/OuzLEFM3Nzc8Pj5iGAabzcYdSKlUIpvNcnFx8WnJPi/kAb2+vpLL5RgOhwD/bYSTIPl8nnq9bpv7rFSOIf1+H0VRGI/Hjl7qKMh6vUaWZVqtlqPgpg5++F6vRzwePxkAHzJ53+e6riPLMt1u9+TgpmyZBAJ/rnpVVYnFYl8CnJ+fW2NbJpPJhGKxyNPTk+OgH/eIKIr7IYVCgefnZ8cAgOl0SrvdtmzDMKyxIEnS/gPnG+UBfuHyf9dvmm+anYtjY5UAAAAASUVORK5CYII='
PREVIOUS_BUTTON_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAAdhJREFUSIm1lj2vKVEUhp8z0VLIiMRXQSPxUY2oRCGiJUq1QiIRiZbaUWgEvYbePyAamaBAh2bOVUg0EhqJ21xzMzfHdUbMm0wys9Ze69lv9sze82G1Wr8AM8bpZAIcBgIAzCbgBJjtdjsWi0XNXC4XFEV5qavb7cbj8TCZTOCPEwBKpRLZbFYdKMsyuVxON8Dj8dDv91EU5Q5BuCftdjuiKKqXy+XSDSgUCsznc/x+P8fjUY2rTs7ns6bgdDr9uLnP56PVahGNRtXY9XpV74XvivSoUqkwnU41gH9leph5okAgQKfTIRgMPh37kpNarcZoNPoRAHQ6kSSJbreL1+vVNamHEEHQmqzX6+TzeV3Nn0Ku1yuCIJBIJGg2mzgcr28MDyGKohAOhxkMBi83v+vhwrvdbhaLBZlMhu12awzkviaj0YhIJEK73X4/5Ha7aZ5rtRrJZJLlcvk+yHeazWbE43EajYZxkLs+Pz+JxWLIsmwcBGC9XpNKpahWq8ZB7up0OkiSxHg8Ng4CsNvtSKfTlMtl9YUxmf5+girEZrNpCp1Op25Yr9cjFAqxWq0QRVGNq7jhcMjhcFATm81GNwRgv99TLBY1J+uH1Wq9/afmLTIBvzD4v+s3geuMP4PEmxwAAAAASUVORK5CYII='
PLAY_BUTTON_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAAPFJREFUSIm1lrFthTAYBu890b7GuMooMAMWzALjgGABU8EIsEnSuKREIqksISUQg5+vNfrvu46HEOITeBGOJQI+AgoAXk9gCSxZnkcvbdsipXyL5VCilGKaJvI8DycBkFLSNI131anE4lvlJAG/KmeJRSnFPM8URRFOAhDHMXVd03WdU9UtiSXLMqcqLwm4VXlLLGdVb5MAbNvGuq7hJH3fk6YpwzD8eot8jxtjqKrqz+MWrxKt9eH6PbdKjDGUZck4jk7fXy7RWpMkibMALpRcXb/HqeTO+j2nJT7r9xyW+K7f8xBCfHtf+YcI+CLwf9cPX0FmElVF/McAAAAASUVORK5CYII='
PAUSE_BUTTON_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAAGdJREFUSInt1jEKgDAMheG/oWs7pJv3v1cn3bKYCziLgihkEPK2hAdfxhRVXYFGXLwCSyAA0ATwYMTr3dbMTvMY49LpvTPnfOwByNfz3iSRRBJJJJFEfoMUVd0J/lYkGABoFdiCIT8AdVMOh/30v2kAAAAASUVORK5CYII='
VOLUME_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAAlFJREFUSIm1lUFLKlEYhp85qS2ilLMQkwlSqJ8gbmxT0TKoCPoB6q6Va1euWrgXF24MNLKVEYjt+wtBUBHXbaBRDjP23ZXSXK+XGS++MIvD+d7z8H5nDp+htf4FrLI4DQJAfIEAgFUFDPy6TNNkc3PTa/lA+QUAXFxcEA6HPdf7htzd3XFwcMDT09NiIM1mk1QqhW3bLC0tTe2HQqH/gzQaDfb29gAQEQzDcO1fXl7y+Pg4P+Tq6or9/X23UbmtNzc3rK2tUa1W/w2JRCKsr68Ti8WIRqOYpkmz2WR3d3fKaFkWAJ1Oh3q9TqvVot1uc3R0hNbaXay17mutRWst7XZbvMiyLDFNU7TW8vDwICIiyWRS4vG4iIiUy2UZn6m17ruSjEYjL90DYHl5GYDDw0MASqUSw+EQx3GmW/tz4TiOZ8j39zcAtm3z/v5OJpMB4O3tjVgsNhsyr5RSE6hSChGZDRm3wOvBACsrK4TDYTqdDgAbGxv0ej1XbeDn4uvrCxFhNBohIgQCgan3MNZwOASg2+0CUCwWiUQiKKW4vb2dneT8/JxEIjH5kskk19fXf4WM4S8vL9TrdSzLolarAVCpVGYnsSxr8v+Pk+XzeQzD4Pj42GUMhUJ8fn5ydnYGQDabZWdnh1qtxsfHx+wks5TL5aYS/Xm56XSa19dXCoXClN/QWvfxOBkrlQonJyfYts329jb9ft+Lzd88yefz3N/fEwwG/dj8v5PT01MajYafyeivXWNtbW3hOA7Pz89eygdzQXxqoBYMAFgNAL0Fgwa/AcdlA4rMxiUnAAAAAElFTkSuQmCC'
REPEAT_ALL_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAA8BJREFUSIm9Vk1IslsQftTATzGjUxJcDStbmAVRodSmdGEFLiqodqKEuWsTtAiqRdCqTYuili2yv42BiwiKst7KRSJoKWWlRbfCCMSCzMTzLT56b2aZd3HvwMDMnHnmec+c9/xwCCF/A8jHfydPeQD+4nK5SKVS32aVlZWhpaUFSqUSIpEILy8vCAaDYBgGgUDgJ5L8PABPfD4/n8/nIxqNZmSUl5fDaDRCp9NBoVBAKBTi9fUVV1dXqKyshM1mg9frzToTEEJiUqmUDg4O0vX1dUoIoYQQqlAoqMPhoLnI7u4uVavVLPaTxngCgWA4mUzyxWIxRkZGkEgkkEwmwTAMVCrVzx0HIJfL0d/fj3A4jJOTk8/Dibx3631NRkdHM4pcXl5ibW0NXq8XkUgEhYWFqK6uhsFgQG1tLZs3OzsLAFhdXU0vQAiJEUJoR0dHRhseHh7o2NjYd22ghBA6MDCQgfvUuhg3WxsYhsH09HTWVtlsNjQ1NaXFlpeX03yWhMfjZRTo7OzE1NRUVhIAODs7g9FoZP2Kigqo1WrW5wkEgmEAfJlMhu7ubqRSqTStq6uDSCTCzs5OVqJgMAidTgepVAoAKC4uxu3tLW5ubv5Z+P39fZSWloJSmgbmcDiQyWQ/zgYAlpaWoNFoAAANDQ3QarVwuVxgSSileHt7+xIcCoVyIvH5fKwtkUhQX18PAH9IWltboVQqQSkFl8vFysoK7u/vcyr8Uc7OzjA5Ocn6x8fHAAAOISS2uLiY39bWxg5aLBbY7fZ/TfKNPHEBwOl04vz8nI3K5fKc0AKBIKc8LgBsbGzA6XSywd7e3pzAzc3NCIfDODg4AMMwrB4eHkKr1bJ5PIFAMByNRvnn5+ewWq0A/vx+19fXbE+/k4uLC4jFYhgMBkgkElaLioqwvb0Nv98PAAl2M4ZCIbjdbrbAzMwMqqqqfpzN+Pg4JiYmMuLxeJy1044Vk8mUlsgwDHp6erKS6PV6dHV1Zc3J++jc3d3BbDZjfn6ejc3NzcFoNMLhcMDtduPx8REFBQWor69He3s79Hr9l4XTNvX7KfxRrVZrTpfVZ7FYLHRoaIhSSmlfX1/6pQWA//Er/H4/7HY7ampqcjpSfD4fzGYzNjc34fF4oFKpEI/HcXp6ing8nuAQQmLI8lppbGyEyWSCRqNBSUkJfv36hUQigUgkAo/Hg4WFBWxtbWXgxGIxUqkUnp+fn/KyEQCAy+VCKpVCIBCAVCqFUCjEy8sL7u7ucHR0hL29vS9xsVjs3czn/B/vrt90yAsNvOVsywAAAABJRU5ErkJggg=='
REPEAT_ONE_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAA8VJREFUSIm9Vk1IclsUXZlgikWdiiANSwWtBqFiFAbppIKgHBQ0MZ1IgTRp9kE1jWjSoKigZon9QX+DhpXcwEENtMJIUIvKfiZigWjleYPw9l0t8w3e23Dh7H3WXuvufdiHU0AIuQNQjP/OXvgAqnk8HlKp1I+o2tpatLe3Q61WQywWIx6PIxAIgGEY+P3+30SK+QBeBAJBsUAgQDQazULU1dXBYrHAZDJBoVBAJBIhkUjg+voaSqUSTqcTPp8vZyUghMQkEgkdHR2l+/v7lBBCCSFUoVDQvb09mo+53W6q1+vZ3IwvVigUCv+8v78LSkpKMDY2hmQyiff3dzAMg4aGht87DkAmk8FutyMcDuPi4iJzO8lPr9JnMj4+nkUSDAaxvb0Nn8+Hp6cnlJWVobGxEd3d3WhqamJx8/PzAID19XUuASEkRgihvb29WW14fn6mExMTP7WBEkLoyMhIVl5G62K8XG1gGAazs7M5W+V0OtHa2sqJra6ucnxWpLCwMIvAbDZjZmYmpwgAXF1dwWKxsL5cLoder2f9QqFQ+AeAQCqVoq+vD6lUivNpNBqIxWIcHh7mFAoEAjCZTJBIJACAiooK3N/f4/b29uvgj4+PUVNTA0opJ7mgoABSqfTXagDA5XKhubkZAKDT6WA0GuHxeMCKUErx9vb2bXIoFMpL5OzsjF1XVlZCq9UCwKdIR0cH1Go1KKXg8XhYW1vDw8NDXsR/29XVFaanp1n//Pz8S8Rms6Gzs5PdvLm5wdbWVl7Eer0ePT09qK6uxt3dHXZ2dnB6esrB8AHg6OgICoUCSqUSwOcE52PLy8swm82cmMPhwMbGBoaHh7+ChJCYVqulS0tL7DBdXl7mHEBCCD04OGDxXq+XqlQq6vV62djJyQl3GMPhMHslAIBKpcLAwMCPFXR1dcFoNAL4vHImJyeh0Wg4GJ1Oxx4BO4yhUIjTy7m5OdTX138r4nA42LVcLofL5UJFRUUWbnBwkCsCAFarlQNiGAb9/f1ZyQqF4lvxTCsvL88WiUQisNlsHODCwgJ2d3dht9uh1Wohk8mQSCTyEknj+Jkbe3t7GBoawuLiIhszGAwwGAx5Ef9tDMMAyKgkbZubm2hpaYHH4/nXxGn7+PjAysoKAKCAEBJDjtdKS0sLrFYrmpubUVVVhaKiIiSTSUSjUVRWVoLHy/7PRCKB/v5+eL1evL6+vvBzCQCAx+NBKpWC3++HRCKBSCRCPB5HJBJBMBiEyWRCW1sbSktLEY1G4Xa7MTU1hcfHxzRFccH/8e76B4nB4p8UAGKLAAAAAElFTkSuQmCC'
REPEAT_OFF_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAAz5JREFUSIm9lktP8loUhp8CRbkaCkEhShOjaSJ1pEGNjNSBE3/Q+UH+AB07UhNMjCYmJI0geImfRGlR5GI5xnIGHvvRD0Qm57xJk+6137XetfZlZQuSJP0CQvx3aHiApMvlwrKsb1nRaJRkMsnExASCIADQbDZ5eHjg8fHxJ5GQB2h4PJ6Q1+ul2Wz2MWKxGIqikEwmCQaDtki73SYcDuNyuahUKkMrESRJehVFMZROp5Flmb29PQCCwSDZbJZkMvlTplSrVXK5HLquDxRx+3y+vyzLGhsbGyOdTiOKIm63m52dHUKh0bYqEAigKAqmaQ4S+tvz9fe1DKqqoqqqg2WaJqVSiefnZ97e3vB6vUiShCzLhMNhm7e2tgaApmkOfw9D0Ol00DSN8/PzvrlSqcTp6SmqqpLJZBxC1WrVUZFrmEitVhso0It8Ps/+/r7DtrW15RjbIl/L1YtEIsHm5uZQEQBd1zk6OrLHfr+fmZmZfpHvIMsyGxsbA5PoRbFYpFar2ePFxUVSqRTQsye3t7fs7u4ODBAIBH7KBfjcJ0mSgM8LnEgkuLu7+y1iWRadTmeg83f2P9FbiSiKRCIR4N9KZFm2MwC4urqi0WiMFLgXhmFQLBYB6Ha7PD09/RZRVZXJyUmbbJpm31kfBaZpOg7AF1wAlUoF0zRto9/vHymoKIoj8TzwuenhcJjZ2VkA5ufnOTs7+9F5bm6OlZUVWq1W39zFxQXX19e8v79/VmIYBvl83ib4/f6+1jIImqZRLpcJhUJ9n8/ns4+9fU90Xader9sBMpnMSB348PCQy8vLPvvHx4f977iMBwcHDuL29jYLCwtDRWZnZ0kkEkM5jgZZr9c5Pj4mm83attXVVRRFoVwuYxgGrVaL8fFxYrEYsiwTj8cHBu52u4NFAAqFAm63227bAJFIhKWlpaHZAuRyOURRZHl5GUEQ7CUb2Oo1TUPXddbX1x2X9Du8vr5ycnLC/f09AFNTU0QiEUKhEC8vLwiSJL0y5LWSSqVQFIVoNOo4MaZpUqvVKBQKlMvlPr9gMIhlWbTb7YYgSVK3j/EHpqenicfj+P1+x0PCMAxubm6+9RMEgW63i/B/vLv+ATI5LWbZUJVeAAAAAElFTkSuQmCC'
FOLDER_ICON = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x19\x00\x00\x00\x19\x08\x06\x00\x00\x00\xc4\xe9\x85c\x00\x00\x01KiTXtXML:com.adobe.xmp\x00\x00\x00\x00\x00<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.6-c142 79.160924, 2017/07/13-01:06:39        ">\n <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n  <rdf:Description rdf:about=""/>\n </rdf:RDF>\n</x:xmpmeta>\n<?xpacket end="r"?>\x9e\x1c`\xef\x00\x00\x024IDATH\x89\xbd\x951K\xebP\x18\x86\x9f4\xa5\x08*\x94\xd3\xc5\xd6\xa1q(\xd5IJ@JW\xc9 \xd4\x8e\x0e\x1d\xfa\x0f\xc4\x1f\xd0?\xe0\xd0?\xd0\xc5\xeeN"B)\x84B\xa5\x19\x1c:\xd4\xbd\x16\x07\xaf \xa8m:\x94B\x93s\x97k\xef\x8d\xa9\x10+\xb9\xef\x96/\xc9\xfb\x9c\x9c\xf7\xfbr\x14!\xc4\x13\xb0Ix\x9aD\x81T\x88\x00\x80\xcd\x080\t\x192\x89\x84\x0c\x00 \xfa\xef\x85\xae\xeb\x9c\x9d\x9d\x91H$\x00p\x1c\x87\x8b\x8b\x0b\xae\xae\xae~\x04Q\x84\x106\x7f\x82\xbf\xbc\xbc\xe4\xf0\xf0\xd0\xf3\x80\xeb\xba\x1c\x1c\x1c0\x1c\x0eWeL\x10B\xd8B\x08)\x84\x90RJY\xaf\xd7\xa5\xa6irggG\xee\xed\xed\xc9^\xaf\'\xbf\xa3\xbb\xbb;\x99L&\xe5\x87\xa7\x10\xc2\x8e~\xc6\xbe\xbe\xbeb\xdb6\x00\xe3\xf1\x18\xc30(\x16\x8b\xc4\xe3q\x1c\xc7\xf9r\xb9RJR\xa9\x14\xd5j\x95l6\xcb\xfd\xfd\xfd\xe2\x9e\x0f\xb2\xb6\xb6\xe63\xb8\xb9\xb9\t\xbc7\xd5j\x95\xd1h\xe4\xa9\xf9 \x8a\xa2\x00\xa0\xaa*\xbb\xbb\xbb\xa8\xaa\x1a\xc8\xdcu]\xd2\xe94\x00\xf9|\x1eUUy||\xc4u]|\x99\x9c\x9f\x9fK!\x84\x1c\x0e\x87\xdf\xcab\x99\x1a\x8d\xc6\xf2L\x9e\x9f\x9f\xd9\xd8\xd8@\xd34J\xa5\x12\x83\xc1\x80H$\xd88I)q\x1c\x87\xed\xedmL\xd3dkkk\xf9v\xbd\xbf\xbfS.\x97\x01\xb0,+\x90\xf9ge2\x19\x00Z\xad\x16\x00\xbe%\xae\xaf\xafsttD\xb3\xd9\\\t\x00P\xa9T\xb0m\x9b\xeb\xebk?d:\x9d\x92\xcb\xe5\xd8\xdf\xdf\xa7\xd1h\xac\x0c)\x95J\xb4\xdb\xedE\x97y ///\x14\x8bEb\xb1\x18\xddnw%\x80\xa2(\xc4b1:\x9d\xce\xa2\xe6\x81\xcc\xe7s\x92\xc9$\x96e1\x9b\xcdV\x82\x14\n\x05\xc0;[\x1e\xc8G\x17\xfd$\x8f\x93\x93\x13\x00\xde\xde\xde\x165Ow\xc5\xe3q\x00\xfa\xfd>\xf0w0\x83HJ\t\x80a\x18\x8b\xf7\x97B\x1e\x1e\x1e\xd0u\x1d\xd34\x03\x9b/\xd3\xe9\xe9\xe9\xd7\x90Z\xad\xc6\xf1\xf11\x9a\xa6-\xfd\x87\x05Q\xbf\xdf\xe7\xf6\xf6\xd6S\xf3\x9c\'!\xe9\xff\x1c\xbf\x11\xc2\xfd\n\x80\xcd(\xf0+d\xd0\xe47"\x1a9A\xf6\xa9\xdb\x88\x00\x00\x00\x00IEND\xaeB`\x82'
# TODO: add right click menus for list boxes


def timing(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        _start = time.time()
        result = f(*args, **kwargs)
        print(f'{f.__name__} ELAPSED TIME:', time.time() - _start)
        return result
    return wrapper


def is_already_running():
    instances = 0
    for process in psutil.process_iter(['name']):
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            process_name = process.name()
            if process_name == 'Music Caster.exe':
                instances += 1
                if instances > 2: return True
                # 2 because of main thread + Flask thread
    return False
# import re
# _nonbmp = re.compile(r'[\U00010000-\U0010FFFF]')
# def _surrogate_pair(match):
#     char = match.group()
#     assert ord(char) > 0xffff
#     encoded = char.encode('utf-16-le')
#     return chr(int.from_bytes(encoded[:2], 'little')) + chr(int.from_bytes(encoded[2:], 'little'))
# def with_surrogates(text):
#     return _nonbmp.sub(_surrogate_pair, text)


def valid_music_file(file_path): return file_path.endswith('.mp3')  # or file_path.endswith('.flac')


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def create_songs_list(music_queue, done_queue, next_queue):
    # TODO: use metadata and song names or just one artist name
    """:returns the formatted song queue, and the selected value (currently playing)"""
    songs = []
    dq_len = len(done_queue)
    mq_start = len(next_queue) + 1
    selected_value = None
    # format: Index. Artists - Song Name
    for i, path in enumerate(done_queue):
        base = os.path.basename(path)
        base = os.path.splitext(base)[0]
        formatted_item = f'-{dq_len - i}. {base}'
        songs.append(formatted_item)
    if music_queue:
        base = os.path.basename(music_queue[0])
        base = os.path.splitext(base)[0]
        formatted_item = f' {0}. {base}'
        songs.append(formatted_item)
        selected_value = formatted_item
    for i, path in enumerate(next_queue):
        base = os.path.basename(path)
        base = os.path.splitext(base)[0]
        formatted_item = f' {i + 1}. {base}'
        songs.append(formatted_item)
    for i, path in enumerate(music_queue[1:]):
        base = os.path.basename(path)
        base = os.path.splitext(base)[0]
        formatted_item = f' {i + mq_start}. {base}'
        songs.append(formatted_item)
    return songs, selected_value


def create_main_gui(music_queue, done_queue, next_queue, playing_status, volume, repeating_song,
                    all_songs: dict, now_playing_text='Nothing Playing', album_cover_data=None):
    # TODO: Music Library Tab
    # TODO: Play Folder option
    
    pause_resume_img = PAUSE_BUTTON_IMG if playing_status == 'PLAYING' else PLAY_BUTTON_IMG
    # Sg.Button('Shuffle', key='Shuffle'),
    if repeating_song is None: repeat_img = REPEAT_OFF_IMG
    elif repeating_song: repeat_img = REPEAT_ONE_IMG
    else: repeat_img = REPEAT_ALL_IMG
    music_controls = [[Sg.Button(key='Locate File', image_data=FOLDER_ICON, tooltip='show file in explorer'),
                       Sg.Button(key='Prev', image_data=PREVIOUS_BUTTON_IMG),
                       # border_width=0, first add border to images
                       Sg.Button(key='Pause/Resume', image_data=pause_resume_img),
                       Sg.Button(key='Next', image_data=NEXT_BUTTON_IMG),
                       Sg.Button(key='Repeat', image_data=repeat_img,
                                 tooltip='repeat all tracks in music queue' if repeating_song else 'repeat current song'),
                       Sg.Image(data=VOLUME_IMG, tooltip='control volume with mousewheel'),
                       Sg.Slider((0, 100), default_value=volume, orientation='h', key='volume_slider',
                                 disable_number_display=True, enable_events=True, background_color=ACCENT_COLOR,
                                 text_color='#000000', size=(10, 10), tooltip='scroll your mousewheel')]]
    progress_bar_layout = [[Sg.Text('00:00', font=font_normal, text_color=fg, key='time_elapsed'),
                            Sg.Slider(range=(0, 100), orientation='h', size=(30, 10), key='progressbar',
                                      enable_events=True, relief=Sg.RELIEF_FLAT, background_color=ACCENT_COLOR,
                                      disable_number_display=True, disabled=now_playing_text == 'Nothing Playing',
                                      tooltip='scroll your mousewheel'),
                            # Sg.ProgressBar(100, orientation='h', size=(30, 20), key='progressbar', style='clam'),
                            Sg.Text('00:00', font=font_normal, text_color=fg, key='time_left')]]
    
    # Now Playing layout
    tab1_layout = [[Sg.Text(now_playing_text, font=font_normal, text_color=fg, key='now_playing',
                            size=(55, 0))],
                   [Sg.Image(filename=album_cover_data, pad=(0, 0), size=(50, 50),
                             key='album_cover')] if album_cover_data else [],
                   # [Sg.Image(data=album_cover_data, pad=(0, 0), size=(0, 150), key='album_cover'),
                   #  Sg.Slider((range(0, 100)))] if album_cover_data else [Sg.Slider((range(0, 100)))],
                   # Maybe make volume on its own tab or horizontal?
                   [Sg.Column(music_controls, justification='center')],
                   [Sg.Column(progress_bar_layout, justification='center')]]
    # Music Queue layout
    songs, selected_value = create_songs_list(music_queue, done_queue, next_queue)
    mq_controls = [
        [Sg.Button('▲', key='move_up', pad=(2, 5), tooltip='move song up the queue')],
        [Sg.Button('❌', key='remove', pad=(0, 5), tooltip='remove song from the queue')],
        [Sg.Button('▼', key='move_down', pad=(2, 5), tooltip='move song down the queue')]]
    q_controls1 = [
        [Sg.Button('Queue File...', font=font_normal, key='queue_file', pad=(0, 5))],
        [Sg.Button('Queue Folder...', font=font_normal, key='queue_folder', pad=(0, 5))],
        [Sg.Button('Play Next...', font=font_normal, key='play_next', pad=(0, 5))]]
    q_controls2 = [[Sg.Button('Clear Queue', font=font_normal, key='clear_queue', pad=(0, 5))]]
    tab2_layout = [[
        Sg.Listbox(songs, default_values=selected_value, size=(45, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                   key='music_queue', background_color=bg, font=font_normal, enable_events=True),
        Sg.Column(mq_controls, pad=(0, 5)), Sg.Column(q_controls1, pad=(0, 5)), Sg.Column(q_controls2, pad=(0, 5))]]
    # song_lib = sorted(all_songs.keys())
    # tab3_layout = [[
    #     Sg.Listbox(song_lib, size=(80, 30), default_values=song_lib[0] if song_lib else '', text_color=fg,
    #                background_color=bg, font=font_normal, key='library')
    # ]]
    # TODO: double click to play a song
    layout = [[Sg.TabGroup([[Sg.Tab('Now Playing', tab1_layout, background_color=bg, key='tab1'),
                             Sg.Tab('Music Queue', tab2_layout, background_color=bg, key='tab2')]])]]
    # Sg.Tab('Library', tab3_layout, background_color=bg, key='tab3')]])]]
    
    return layout


def create_settings(version, music_directories, settings, qr_code_data):
    LEFT_CHECKMARKS_W = 17
    RIGHT_CHECKMARKS_W = 21
    checkbox_col = Sg.Column([
        [Sg.Checkbox('Auto Update', default=settings['auto_update'], key='auto_update', text_color=fg,
                     background_color=bg, font=font_normal, enable_events=True, size=(17, None),
                     pad=((0, 5), (5, 5))),
         Sg.Checkbox('Discord Presence', default=settings['discord_rpc'], key='discord_rpc',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True, size=(13, None),
                     pad=((0, 5), (5, 5)))],
        [Sg.Checkbox('Notifications', default=settings['notifications'], key='notifications',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True, size=(17, None),
                     pad=((0, 5), (5, 5))),
         Sg.Checkbox('Run on Startup', default=settings['run_on_startup'], key='run_on_startup', text_color=fg,
                     background_color=bg, font=font_normal, enable_events=True, size=(13, None),
                     pad=((0, 5), (5, 5)))],
        [Sg.Checkbox('Save Window Positions', default=settings['save_window_positions'],
                     key='save_window_positions', size=(17, None), text_color=fg, background_color=bg, font=font_normal,
                     enable_events=True, pad=((0, 5), (5, 5))),
         Sg.Checkbox('Shuffle Playlists', default=settings['shuffle_playlists'], key='shuffle_playlists',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True, size=(13, None),
                     pad=((0, 5), (5, 5)))]
        ], pad=((0, 0), (5, 0)))
    qr_code_col = Sg.Column([
        [Sg.Button(image_data=qr_code_data, tooltip='Web GUI QR Code (click or scan)', key='web_gui', border_width=0)]])
    layout = [
        [Sg.Text(f'Music Caster Version {version} by Elijah Lopez', text_color=fg, font=font_normal),
         Sg.Text('elijahllopezz@gmail.com', text_color=LINK_COLOR, font=font_link, click_submits=True, key='email',
                 tooltip='Click to send me an email')],
        [checkbox_col, qr_code_col],
        # [Sg.Slider((0, 100), default_value=settings['volume'], orientation='h', key='volume', tick_interval=5,
        #            enable_events=True, background_color=ACCENT_COLOR, text_color='#000000', size=(49, 15))],
        [Sg.Listbox(music_directories, size=(40, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='music_dirs', background_color=bg, font=font_normal, enable_events=True, no_scrollbar=True),
         Sg.Frame('', [
             [Sg.Button('Remove Folder', key='Remove Folder', enable_events=True, font=font_normal)],
             [Sg.FolderBrowse('Add Folder', font=font_normal, enable_events=True)],
             [Sg.Button('Open settings.json', key='Open Settings', font=font_normal,
                        enable_events=True)]], background_color=bg, border_width=0)]]
    return layout


def create_timer(settings):
    layout = [
        [Sg.Radio('Shut off computer when timer runs out', 'TIMER', default=settings['timer_shut_off_computer'],
                  key='shut_off', text_color=fg, background_color=bg, font=font_normal,
                  enable_events=True)],
        [Sg.Radio('Hibernate computer when timer runs out', 'TIMER', default=settings['timer_hibernate_computer'],
                  key='hibernate', text_color=fg, background_color=bg, font=font_normal,
                  enable_events=True)],
        [Sg.Radio('Sleep computer when timer runs out', 'TIMER', default=settings['timer_sleep_computer'],
                  key='sleep', text_color=fg, background_color=bg, font=font_normal,
                  enable_events=True)],
        [Sg.Text('Enter minutes or HH:MM',  tooltip='press enter once done', text_color=fg, font=font_normal)],
        [Sg.Input(key='minutes'), Sg.Submit(font=font_normal)]]
    return layout


def playlist_selector(playlists):
    playlists = list(playlists.keys())
    layout = [
        [Sg.Combo(values=playlists, size=(41, 5), key='pl_selector', background_color=bg, font=font_normal,
                  enable_events=True, readonly=True, default_value=playlists[0] if playlists else None),
         Sg.Button(button_text='Edit', key='edit_pl', tooltip='Ctrl + E', enable_events=True, font=font_normal),
         Sg.Button(button_text='Delete', key='del_pl', tooltip='Ctrl + Del', enable_events=True, font=font_normal),
         Sg.Button(button_text='New', key='create_pl', tooltip='Ctrl + N', enable_events=True, font=font_normal)]]
    return layout


def playlist_editor(initial_folder, playlists, playlist_name=''):
    paths = playlists.get(playlist_name, [])
    songs = [f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(paths)]
    # TODO: remove .mp3
    layout = [[
        Sg.Text('Playlist name', text_color=fg, font=font_normal),
        Sg.Input(playlist_name, key='playlist_name'),
        Sg.Submit('Save & quit', key='Save', tooltip='Ctrl + S', font=font_normal, pad=(('11px', '11px'), (0, 0))),
        Sg.Button('❌', key='Cancel', tooltip='Cancel (Esc)', font=font_normal, enable_events=True)],
        [Sg.Frame('', [[Sg.FilesBrowse('Add songs', key='Add songs', file_types=(('Audio Files', '*.mp3'),),
                                       pad=(('21px', 0), (5, 5)), initial_folder=initial_folder, font=font_normal,
                                       enable_events=True)],
                       [Sg.Button('Remove song', key='Remove song', tooltip='Ctrl + R', font=font_normal,
                                  enable_events=True)]],
                  background_color=bg, border_width=0),
         Sg.Listbox(songs, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='songs', background_color=bg, font=font_normal, enable_events=True),
         Sg.Frame('', [
             [Sg.Button('Move up', key='move_up', tooltip='Ctrl + U', font=font_normal, enable_events=True)],
             [Sg.Button('Move down ', key='move_down', tooltip='Ctrl + D', font=font_normal, enable_events=True)]
         ], background_color=bg, border_width=0)]]
    return layout

