import argparse

import colorcet as cc
import numpy as np
import pandas as pd
import xarray as xr
import xdas
import xdas.signal as xp
from bokeh.layouts import column, row
from bokeh.models import (
    Button,
    ColumnDataSource,
    CustomJS,
    Div,
    LassoSelectTool,
    LinearColorMapper,
    RadioButtonGroup,
    Range1d,
    Slider,
    TextInput,
    Toggle,
)
from bokeh.plotting import curdoc, figure
from bokeh.transform import factor_cmap

from xpick.app.processing import load_signal, normalize_signal, process_signal
from xpick.app.pickertool import PickerTool

# parse arguments

parser = argparse.ArgumentParser()
parser.add_argument("--path")
parser.add_argument("--width", type=int)
parser.add_argument("--height", type=int)
args = parser.parse_args()


# global constants

palette_mapping = ["Viridis256", cc.CET_D1A]
phase_labels = ["Pp", "Ps", "Ss"]
phase_cmap = factor_cmap(
    field_name="phase", palette=["#7F0DFF", "#BF0DFF", "#FF00FF"], factors=phase_labels
)


# global variables

db = xdas.open_database(args.path)
x_range = Range1d()
y_range = Range1d()
source_image = ColumnDataSource(data=dict(image=[], x=[], y=[], dw=[], dh=[]))
source_picks = ColumnDataSource(data=dict(time=[], distance=[], phase=[], status=[]))
phase = RadioButtonGroup(labels=phase_labels, active=0, width=330)
signal = xr.DataArray()
image = xr.DataArray()


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
)
crc = fig.circle(
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
    "starttime": TextInput(title="Start", value="2021-11-13T01:41:00", width=160),
    "endtime": TextInput(title="End", value="2021-11-13T01:41:10", width=160),
    "startdistance": TextInput(title="Start", value="20_000.0", width=160),
    "enddistance": TextInput(title="End", value="120_000.0", width=160),
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
b_apply = Button(label="apply", button_type="success", width=160)
b_home = Button(label="home", button_type="primary", width=160)
mapper = {
    "palette": RadioButtonGroup(labels=["viridis", "seismic"], active=0, width=160),
    "linthresh": TextInput(title="Linear Threshold", value="1e-8", width=160),
    "vlim": TextInput(title="Value Limit", value="1e-5", width=160),
}
b_mapper = Button(label="apply", button_type="success", width=160)
slider = Slider(start=1, end=10, value=3, step=1, title="Marker Size", width=330)
path = TextInput(title="Path", width=330)
b_delete = Button(label="delete", button_type="warning", width=75)
b_save = Button(label="save", button_type="success", width=75)
b_load = Button(label="load", button_type="primary", width=75)
b_reset = Button(label="reset", button_type="danger", width=75)


slider_callback = CustomJS(
    args=dict(circle=crc, slider=slider),
    code="""
    circle.glyph.size = slider.value;
""",
)
slider.js_on_change("value", slider_callback)


# callbacks


def callback():
    global signal, image
    signal = load_signal(db, selection)
    signal = process_signal(signal, processing)
    image = normalize_signal(signal, mapper)
    update_image(image)
    update_palette()
    update_range()


b_apply.on_click(callback)


def update_image(image):
    print("Updating image... ", end="")
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
    print("Done.")


b_mapper.on_click(lambda: update_image(normalize_signal(signal, mapper)))


def update_palette():
    print("Updating palette... ", end="")
    palette = palette_mapping[mapper["palette"].active]
    image_mapper = LinearColorMapper(palette=palette, low=0, high=1)
    img.glyph.color_mapper = image_mapper
    print("Done.")


mapper["palette"].on_change("active", lambda attr, old, new: update_palette())


def update_range():
    print("Updating range... ", end="")
    x, y, dw, dh = [source_image.data[key][0] for key in ["x", "y", "dw", "dh"]]
    x_range.start = x
    x_range.end = x + dw
    y_range.start = y + dh
    y_range.end = y
    print("Done.")


b_home.on_click(update_range)


def save_picks():
    print("Saving picks... ", end="")
    picks = pd.DataFrame(source_picks.data)
    picks["time"] = pd.to_datetime(picks["time"], unit="ms")
    picks = picks.sort_values("time")
    picks = picks.drop(columns=["status"])
    picks.to_csv(path.value, index=False)
    print("Done.")


b_save.on_click(save_picks)


def load_picks():
    print("Loading picks... ", end="")
    picks = pd.read_csv(path.value, parse_dates=["time"])
    picks["status"] = "inactive"
    source_picks.data = picks.to_dict("list")
    print("Done.")


b_load.on_click(load_picks)


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


def reset_picks():
    print("Resetting picks... ", end="")
    source_picks.data = dict(time=[], distance=[], phase=[])
    print("Done.")


b_reset.on_click(reset_picks)


# layout

doc = curdoc()
doc.title = "xpick"
doc.add_root(
    row(
        fig,
        column(
            Div(text="<h2 style='margin: 0'>Selection & Processing</h2>"),
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
            row(b_apply, b_home),
            Div(text="<h2 style='margin: 0'>Colormap</h2>"),
            row(mapper["linthresh"], mapper["vlim"]),
            row(b_mapper, mapper["palette"]),
            Div(text="<h2 style='margin: 0'>Picks</h2>"),
            phase,
            slider,
            path,
            row(b_save, b_load, b_delete, b_reset),
        ),
    )
)
