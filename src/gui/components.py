import PySimpleGUI as Sg
import io
from meta import FONT_NORMAL, State
import base64
from PIL import Image, ImageDraw
import pyqrcode


def StyledButton(button_text, fill, text_color, tooltip=None, key=None, visible=True,
              pad=None, bind_return_key=False, button_width=None):
    if State.using_tcl_theme:
        return Sg.Button(button_text, use_ttk_buttons=True, key=key, visible=visible,
                         bind_return_key=bind_return_key, size=(button_width, 1), pad=pad)
    multi = 4
    btn_w = ((len(button_text) if button_width is None else button_width) * 5 + 20) * multi
    height = 18 * multi
    btn_img = Image.new('RGBA', (btn_w, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(btn_img)
    x0 = y0 = 0
    radius = 10 * multi
    d.ellipse((x0, y0, x0 + radius * 2, height), fill=fill)
    d.ellipse((btn_w - radius * 2 - 1, y0, btn_w - 1, height), fill=fill)
    d.rectangle((x0 + radius, y0, btn_w - radius, height), fill=fill)
    data = io.BytesIO()
    btn_img.thumbnail((btn_w // 3, height // 3), resample=Image.LANCZOS)
    btn_img.save(data, format='png', quality=100)
    btn_img = base64.b64encode(data.getvalue())
    return Sg.Button(button_text=button_text, image_data=btn_img, button_color=(text_color, text_color),
                     tooltip=tooltip, key=key, pad=pad, enable_events=False, size=(button_width, 1),
                     bind_return_key=bind_return_key, font=FONT_NORMAL, visible=visible)


def IconButton(image_data, key, tooltip, bg):
    return Sg.Button(image_data=image_data, key=key, tooltip=tooltip, enable_events=True, button_color=(bg, bg))


def Checkbox(name, key, settings, on_right=False, tooltip=None):
    # fix for languages that are too long to fit into the UI
    if tooltip is None:
        tooltip = name
    bg = settings['theme']['background']
    size = (23, 5) if on_right else (23, 5)
    checkbox = {'background_color': bg, 'font': FONT_NORMAL, 'enable_events': True, 'pad': ((0, 5), (5, 5))}
    return Sg.Checkbox(name, default=settings[key], key=key, tooltip=tooltip, size=size, **checkbox)


def QRCode(text_to_encode):
    try:
        qr_code = pyqrcode.create(text_to_encode)
        return qr_code.png_as_base64_str(scale=3, module_color=(255, 255, 255, 255), background=(18, 18, 18, 255))
    except OSError:
        # Failed?
        return None
