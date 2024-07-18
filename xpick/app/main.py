import argparse

import colorcet as cc
import netCDF4  # fix bug for some reason
import numpy as np
import pandas as pd
import xdas
import xdas.signal as xp
from bokeh.layouts import column, row
from bokeh.models import (
    Button,
    CategoricalColorMapper,
    ColorPicker,
    ColumnDataSource,
    CustomJS,
    Div,
    LassoSelectTool,
    LinearColorMapper,
    PreText,
    RadioButtonGroup,
    Range1d,
    Select,
    Slider,
    TextInput,
    Toggle,
    Widget,
)
from bokeh.plotting import curdoc, figure
from bokeh.transform import factor_cmap

from xpick.app.pickertool import PickerTool
from xpick.app.processing import load_signal, normalize_signal, process_signal
from xpick.app.utils import check_paths, get_codes

# parse arguments

parser = argparse.ArgumentParser()
parser.add_argument("--paths", nargs="+")
parser.add_argument("--width", type=int)
parser.add_argument("--height", type=int)
parser.add_argument("--phases", type=str)
parser.add_argument("--colors", type=str)
args = parser.parse_args()


# global constants

palette_mapping = ["Viridis256", cc.CET_D1A]
phase_labels = args.phases.split(",")  # ["Pp", "Ps", "Ss"]
phase_colors = args.colors.split(",")  # ["#7F0DFF", "#BF0DFF", "#FF00FF"]
if len(phase_labels) != len(phase_colors):
    if not phase_colors == [""]:
        print(
            "Phase labels number do no match phase colors. Using default value instead."
        )
    phase_colors = ["#FF0000"] * len(phase_labels)
phase_cmap = factor_cmap(field_name="phase", palette=phase_colors, factors=phase_labels)


# global variables

paths = args.paths
is_datacollection = check_paths(paths)
if is_datacollection:
    codes = get_codes(xdas.open_datacollection(paths[0]))
x_range = Range1d()
y_range = Range1d()
source_image = ColumnDataSource(data=dict(image=[], x=[], y=[], dw=[], dh=[]))
source_picks = ColumnDataSource(data=dict(time=[], distance=[], phase=[], status=[]))
phase = RadioButtonGroup(labels=phase_labels, active=0, width=330)
raw_signal = xdas.DataArray()
pro_signal = xdas.DataArray()
image = xdas.DataArray()


# figure

fig = figure(
    width=args.width,
    height=args.height,
    y_axis_type="datetime",
    x_range=x_range,
    y_range=y_range,
)
img = fig.image(
    source=source_image,
    image="image",
    x="x",
    y="y",
    dw="dw",
    dh="dh",
    color_mapper=palette_mapping[0],
)
crc = fig.scatter(
    source=source_picks,
    x="distance",
    y="time",
    size=3,
    color=phase_cmap,
)
fig.add_tools(LassoSelectTool())
fig.add_tools(PickerTool(source=source_picks, phase=phase))


# widgets

selection = {
    "dataarray": Select(
        title="Data Array",
        value=codes[0] if is_datacollection else paths[0],
        options=codes if is_datacollection else paths,
        width=330,
    ),
    "starttime": TextInput(title="Start", value="", width=160),
    "endtime": TextInput(title="End", value="", width=160),
    "startdistance": TextInput(title="Start", value="", width=160),
    "enddistance": TextInput(title="End", value="", width=160),
    "datacollection": paths[0] if is_datacollection else None,
}
processing = {
    "space": {
        "integration": Toggle(label="Integrate", width=160),
        "decimation": TextInput(title="Decimate", value="16", width=75),
        "highpass": TextInput(title="Highpass", value="", width=75),
    },
    "time": {
        "integration": Toggle(label="Integrate", width=160),
        "decimation": TextInput(title="Decimate", value="4", width=75),
        "highpass": TextInput(title="Highpass", value="", width=75),
    },
}
mapper = {
    "palette": RadioButtonGroup(labels=["viridis", "seismic"], active=0, width=330),
    "linthresh": TextInput(title="Linear Threshold", value="", width=160),
    "vlim": TextInput(title="Value Limit", value="", width=160),
}
b_apply = Button(label="apply", button_type="success", width=160)
b_home = Button(label="home", button_type="primary", width=160)
color_pickers = {
    phase: ColorPicker(title=phase, color=color, width=60)
    for phase, color in zip(phase_labels, phase_colors)
}
slider = Slider(start=1, end=10, value=3, step=1, title="Marker Size", width=330)
path = TextInput(title="Path", width=330)
b_delete = Button(label="delete", button_type="warning", width=75)
b_save = Button(label="save", button_type="success", width=75)
b_load = Button(label="load", button_type="primary", width=75)
b_reset = Button(label="reset", button_type="danger", width=75)
console = PreText(text="", width=330, height=30)


# changes

changes = {
    "load_signal": True,
    "process_signal": True,
    "normalize_signal": True,
    "update_image": True,
    "update_palette": True,
    "update_range": True,
}

for widget in selection.values():
    if isinstance(widget, Widget):
        widget.on_change(
            "value",
            lambda attr, old, new: changes.update(
                {
                    "load_signal": True,
                    "process_signal": True,
                    "normalize_signal": True,
                    "update_image": True,
                    "update_range": True,
                }
            ),
        )
for dim in processing:
    for widget in processing[dim].values():
        if hasattr(widget, "active"):
            attr = "active"
        else:
            attr = "value"
        widget.on_change(
            attr,
            lambda attr, old, new: changes.update(
                {
                    "process_signal": True,
                    "normalize_signal": True,
                    "update_image": True,
                }
            ),
        )
for widget in mapper.values():
    if hasattr(widget, "active"):
        attr = "active"
    else:
        attr = "value"
    widget.on_change(
        attr,
        lambda attr, old, new: changes.update(
            {
                "normalize_signal": True,
                "update_image": True,
            }
        ),
    )

# callbacks

content = ""


def print_console(text, end="\n"):
    global content
    content += text + end
    content = "\n".join(content.split("\n")[-4:])
    console.text = "".join(content)


print_console("Welcome to xpick!")


def console_message(message):
    def decorator(function):
        def wrapper(*args, **kwargs):
            print_console(message, end="")
            out = function(*args, **kwargs)
            print_console(" Done.")
            return out

        return wrapper

    return decorator


def callback():
    global raw_signal, pro_signal, image
    if changes["load_signal"]:
        raw_signal = console_message("Loading signal...")(load_signal)(selection)
        if raw_signal.size == 0:
            print_console("ERROR: No data found for that selection.")
            return
        changes["load_signal"] = False
    if changes["process_signal"]:
        pro_signal = console_message("Processing signal...")(process_signal)(
            raw_signal, processing
        )
        changes["process_signal"] = False
    if changes["normalize_signal"]:
        image = console_message("Normalizing image...")(normalize_signal)(
            pro_signal, mapper
        )
        changes["normalize_signal"] = False
    if changes["update_image"]:
        update_image(image)
        changes["update_image"] = False
    if changes["update_palette"]:
        update_palette()
        changes["update_palette"] = False
    if changes["update_range"]:
        update_range()
        changes["update_range"] = False


b_apply.on_click(callback)


@console_message("Updating image...")
def update_image(image):
    t0 = image["time"][0].values
    s0 = image["distance"][0].values
    L = image["distance"][-1].values - image["distance"][0].values
    T = image["time"][-1].values - image["time"][0].values
    dt = xp.get_sampling_interval(image, "time")
    dt = np.timedelta64(round(1e9 * dt), "ns")
    ds = xp.get_sampling_interval(image, "distance")
    x = s0 - ds / 2
    y = t0 - dt / 2
    dw = L + ds
    dh = T + dt
    source_image.data = dict(image=[image.data], x=[x], y=[y], dw=[dw], dh=[dh])


@console_message("Updating palette...")
def update_palette():
    palette = palette_mapping[mapper["palette"].active]
    image_mapper = LinearColorMapper(palette=palette, low=0, high=1)
    img.glyph.color_mapper = image_mapper


mapper["palette"].on_change("active", lambda attr, old, new: update_palette())


@console_message("Updating range...")
def update_range():
    x, y, dw, dh = [source_image.data[key][0] for key in ["x", "y", "dw", "dh"]]
    x_range.start = x
    x_range.end = x + dw
    y_range.start = y + dh
    y_range.end = y


b_home.on_click(lambda: update_range())


@console_message("Updating picks colors...")
def update_colors():
    for idx, color_picker in enumerate(color_pickers.values()):
        phase_colors[idx] = color_picker.color
    transform = CategoricalColorMapper(factors=phase_labels, palette=phase_colors)
    crc.glyph.line_color = dict(field="phase", transform=transform)
    crc.glyph.fill_color = dict(field="phase", transform=transform)


for color_picker in color_pickers.values():
    color_picker.on_change("color", lambda attr, old, new: update_colors())


slider_callback = CustomJS(
    args=dict(circle=crc, slider=slider),
    code="""
    circle.glyph.size = slider.value;
""",
)
slider.js_on_change("value", slider_callback)


@console_message("Saving picks...")
def save_picks():
    picks = pd.DataFrame(source_picks.data)
    picks["time"] = pd.to_datetime(picks["time"], unit="ms")
    picks = picks.sort_values("time")
    picks = picks.drop(columns=["status"])
    picks.to_csv(path.value, index=False)


b_save.on_click(lambda: save_picks())


@console_message("Loading picks...")
def load_picks():
    picks = pd.read_csv(path.value, parse_dates=["time"])
    picks["time"] = (picks["time"] - np.datetime64(0, "ms")) / np.timedelta64(1, "ms")
    picks["status"] = "inactive"
    source_picks.data = picks.to_dict("list")


b_load.on_click(lambda: load_picks())


delete_selection = CustomJS(
    args=dict(source=source_picks),
    code="""
    // Get the selected indices
    const selected_indices = source.selected.indices;

    // Remove the selected points from the data source
    source.data["distance"] = source.data["distance"].filter((_, index) => !selected_indices.includes(index));
    source.data["time"] = source.data["time"].filter((_, index) => !selected_indices.includes(index));
    source.data["phase"] = source.data["phase"].filter((_, index) => !selected_indices.includes(index));
    source.data["status"] = source.data["status"].filter((_, index) => !selected_indices.includes(index));

    // Update the plot
    source.change.emit();

    // Clear the selection
    source.selected.indices = [];

    // Trigger a change event to update the plot
    source.change.emit();
""",
)

b_delete.js_on_click(delete_selection)


@console_message("Resetting picks...")
def reset_picks():
    source_picks.data = dict(time=[], distance=[], phase=[])


b_reset.on_click(lambda: reset_picks())


# layout

doc = curdoc()
doc.title = "xpick"
doc.add_root(
    row(
        fig,
        column(
            Div(text="<h2 style='margin: 0'>Selection & Processing</h2>"),
            selection["dataarray"],
            row(
                column(
                    Div(text="<h3 style='margin: 0'>Time</h3>"),
                    selection["starttime"],
                    selection["endtime"],
                    processing["time"]["integration"],
                    row(
                        processing["time"]["decimation"], processing["time"]["highpass"]
                    ),
                ),
                column(
                    Div(text="<h3 style='margin: 0'>Space</h3>"),
                    selection["startdistance"],
                    selection["enddistance"],
                    processing["space"]["integration"],
                    row(
                        processing["space"]["decimation"],
                        processing["space"]["highpass"],
                    ),
                ),
            ),
            Div(text="<h3 style='margin: 0'>Colormap</h3>"),
            mapper["palette"],
            row(mapper["linthresh"], mapper["vlim"]),
            row(b_apply, b_home),
            Div(text="<h2 style='margin: 0'>Picks</h2>"),
            phase,
            row(*color_pickers.values()),
            slider,
            path,
            row(b_save, b_load, b_delete, b_reset),
            console,
        ),
    )
)
