import wx.adv
import wx
from wx.lib.embeddedimage import PyEmbeddedImage

TRAY_TOOLTIP = 'Music Caster'
unfilled_logo_data = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACWElEQVRo3u2ZsUsbURzHo2Bc0kkMDoYirRkcpEu7NtAubo7ZPXDo6qaL\nkyUIQtshkE6CkA79C4SqWIiLi5N2iBQ7WgRvUNvGj0OG/n737kLt9d476PuOvx9JPnn3e9/v3b1C\nwcvLy8srSQwR0CHEpi7pEDAUhzPBNq60zYS5Ou5w+kh6lQhwrUADHTgH6mig0DlQqIGErO7spN/1\nQB7IA3kg10DObnk8kAf6b4C44ZxTDmmzSp3JXPkQAF9o8oLh/AD1dcYalTwBAdzQ4lGegAB+sk4p\nT0AA35i3CVRkjClqLPKGI24ToN4x6sSHGGeB3Visw3875PcyRqb5EAN1xoxDp+Ypnwyk7zxzGh3M\n0TWQZhwCFQqMsWtcuEq2uyzkhB22WGE29oMjNI3xHrXlQ1024rB4xS9tAjaNsccmD2OQtObtOvU1\nDYqRL2hG3LtkEwjgM+XILOnxXrefZV95EtlxXRW7j7MBKlGlxhL79Mx3WxGkOdV9n7EPUabBlbFK\n+sJJ9/6RxpH+NFwrfDRmqagCRWbcaytOzXIkWBuq21auPWwlOqgrpGvpS0yr3ktLWcayWqNN1ZPb\nv5lFlh3TMv+pmqWeDBQW5ENTdj60RzUy3nLHbai7SnnRJrMzxgueq05Dxq7qHIlOPUunvpCrRFlZ\npbxob0V99Z7PMDEnZ4OiY0/19kVnRdQXRb2dGqgzOMvEeLMk6luiXpO3a6mBgsFArYQf3hH1KVE/\nTQlkHOBFdSx6VVE/Ubn/W+epgGKOOAecXvEgoV6UryT+EihMPAT28vLy8urrDgm99Mb0O5qlAAAA\nJXRFWHRkYXRlOmNyZWF0ZQAyMDE5LTA3LTE0VDAwOjQ2OjMyKzAwOjAwaWwEjwAAACV0RVh0ZGF0\nZTptb2RpZnkAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMBgxvDMAAAAASUVORK5CYII=\n'
filled_logo_data = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACxUlEQVRo3u2ZT0hUURSHn0bjxtpIYqCElLNwEW1yWYO1yF3L2fvARVs3\nqRtX2SAIJTFgK0HQRdJeaBSDaePGlYaoYUtD8C3ScvpaKHTOfe8NOu/fQPe3PGec+bz3nN+57z7H\nsbKysrIKEy24VPFIU8dUcWkJwulihay0Qpd/dbLDOUfSq4RL1nI10JfMgaoayMscyNNAQql2dtjv\nWiAL9N8AJdHfFigWoMvscXMAnTUb0G3G2GkioIuz0iDLTQR08acDVJoKyHEch2dsptX2pxyyxwaL\nTFKkOxQpx2tqKfsQAF8p84TWQKhH7KcPdK4DXtETgHSTj9kAAZwyx10fUivvsgIC+M007T6oseyA\nAL7z3IfkJgeUo4NeCozwhk3+hHzXLG3RV6kBH+IWw6wGYm2YRX71WmrYGOljKQDqgH71qWtX7bho\nw/Uhn3zf+IMBwwT2Ux0dDLHrQ+o3rLKW6iyjg1XfxqlaYiruLvPYpsICE9wPRLpO2VfebapLN5Pz\noV1mgrB4YZwfZ42TQKLGWGOeOwFIWsoqL3teatypTyiRM5DKhnu3qyNcCqPjM51GLenynlbZ5TRm\n2TceGB23q8buPZEbjA+onTwFRlkPcBTPQBpS2ffqcWAndh+ikxI/faukN0669y/pSLxMZrj28MFX\nSzk1UOSMm1LPcWcJOTXjxmAtqeyicu3W2K9jAj9cVEgn0pfoU7mnqQA5DuNqjeZVTrZ/Of4LK48t\n5vz/qaqlmhwoDMuHpuRu0NbIG+UtO25GnSrlpnUnd6V3xGOVKcmxqzJyvhcTvGPkSK4Sncoq5aa9\nFfHJyNdcx/VGx5rKrYvMhIiPiPhiZKBq/VkmyptREV8Q8YI8rkUGcusDzYX8cEXEe0V8LyKQ7wWe\nqS2Ry4v4tpr7/3QYCSjgFWedt1fcCInn5JVEg0Be6EtgKysrK6tz/QVPmZ3Bw5RmTgAAACV0RVh0\nZGF0ZTpjcmVhdGUAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMGlsBI8AAAAldEVYdGRhdGU6bW9k\naWZ5ADIwMTktMDctMTRUMDA6NDY6MzIrMDA6MDAYMbwzAAAAAElFTkSuQmCC\n'


def create_menu_item(menu, label, func):
    item = wx.MenuItem(menu, -1, label)
    menu.Bind(wx.EVT_MENU, func, id=item.GetId())
    menu.Append(item)
    return item


class TaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame):
        self.frame = frame
        super(TaskBarIcon, self).__init__()
        self.set_icon(PyEmbeddedImage(unfilled_logo_data).GetIcon())
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        create_menu_item(menu, 'Site', self.on_hello)
        menu.AppendSeparator()
        create_menu_item(menu, 'Exit', self.on_exit)
        return menu

    def set_icon(self, path):
        icon = wx.Icon(path)
        self.SetIcon(icon, TRAY_TOOLTIP)

    @staticmethod
    def on_left_down(event):
        print('Tray icon was left-clicked.')

    @staticmethod
    def on_hello(self, event):
        print('Hello, world!')

    def on_exit(self, event):
        wx.CallAfter(self.Destroy)
        self.frame.Close()


class App(wx.App):
    def OnInit(self):
        frame = wx.Frame(None)
        self.SetTopWindow(frame)
        TaskBarIcon(frame)
        return True


def main():
    app = App(False)
    app.MainLoop()


if __name__ == '__main__':
    main()
