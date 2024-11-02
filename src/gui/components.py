import base64
import io
import platform

import pyqrcode
import PySimpleGUI as Sg
from meta import FONT_NORMAL, State
from PIL import Image, ImageDraw


def get_styled_button_font():
    if platform.system() == 'Windows':
        return 'Segoe UI Variable', 12


def StyledButton(button_text, fill, text_color, tooltip=None, key=None, visible=True,
              pad=None, bind_return_key=False, button_width=None, blend_color=None, outline=None):
    if State.using_tcl_theme:
        return Sg.Button(button_text, use_ttk_buttons=True, key=key, visible=visible,
                         bind_return_key=bind_return_key, size=(button_width, 1), pad=pad)
    multi = 4
    btn_w = ((len(button_text) if button_width is None else button_width) * 5 + 20) * multi
    height = 18 * multi
    btn_img = Image.new('RGBA', (btn_w, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(btn_img)
    x0 = y0 = 0
    if outline is None:
        outline = fill
    d.rounded_rectangle((x0, y0, btn_w, height), fill=fill, outline=outline, width=5, radius=10)
    data = io.BytesIO()
    btn_img.thumbnail((btn_w // 3, height // 3), resample=Image.Resampling.LANCZOS)
    btn_img.save(data, format='png', quality=100)
    btn_img = base64.b64encode(data.getvalue())
    btn_color = (text_color, blend_color)
    if blend_color is None:
        blend_color = text_color
        mouseover_colors = (None, None)
        highlight_colors = None
    else:
        mouseover_colors = btn_color if platform.system() == 'Windows' else None
        highlight_colors = btn_color
    return Sg.Button(button_text=button_text, image_data=btn_img, button_color=(text_color, blend_color),
                     tooltip=tooltip, key=key, pad=pad, enable_events=False, size=(button_width, 1),
                     bind_return_key=bind_return_key, font=get_styled_button_font(), visible=visible,
                     mouseover_colors=mouseover_colors, highlight_colors=highlight_colors)


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
