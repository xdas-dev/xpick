import argparse

import colorcet as cc
import matplotlib.pyplot as plt
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
from matplotlib.colors import SymLogNorm

from xpick.app.pickertool import PickerTool

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


# layout
doc = curdoc()
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

slider = Slider(start=1, end=50, value=3, step=1, title="Marker Size", width=330)
slider_callback = CustomJS(
    args=dict(circle=crc, slider=slider),
    code="""
    circle.glyph.size = slider.value;
""",
)
slider.js_on_change("value", slider_callback)

fig.add_tools(LassoSelectTool())
phase = RadioButtonGroup(labels=phase_labels, active=0, width=330)
fig.add_tools(PickerTool(source=source_picks, phase=phase))


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
mapper = {
    "palette": RadioButtonGroup(labels=["viridis", "seismic"], active=0, width=160),
    "linthresh": TextInput(title="Linear Threshold", value="1e-8", width=160),
    "vlim": TextInput(title="Value Limit", value="1e-5", width=160),
}
fname = TextInput(title="Path", width=330)


# callbacks
def load_signal(db, selection):
    print("Loading signal... ", end="")
    # load
    signal = db.sel(
        time=slice(
            selection["starttime"].value,
            selection["endtime"].value,
        ),
        distance=slice(
            float(selection["startdistance"].value),
            float(selection["enddistance"].value),
        ),
    ).to_xarray()
    print("Done.")
    return signal


def process_signal(signal, processing):
    print("Processing signal... ", end="")
    # distance
    if processing["space"]["integration"].active:
        signal = xp.integrate(signal, dim="distance")
    if q := processing["space"]["decimation"].value:
        signal = xp.decimate(
            signal, int(q), ftype="fir", zero_phase=True, dim="distance"
        )
    if wlen := processing["space"]["highpass"].value:
        signal = xp.sliding_mean_removal(signal, wlen=float(wlen))
    # time
    if processing["time"]["integration"].active:
        signal = xp.integrate(signal, dim="time")
    if q := processing["time"]["decimation"].value:
        signal = xp.decimate(signal, int(q), ftype="iir", zero_phase=False, dim="time")
    if freq := processing["time"]["highpass"].value:
        signal = xp.iirfilter(signal, freq=float(freq), btype="highpass")
    # gain
    signal *= 1.08e-7
    print("Done.")
    return signal


def update_image():
    signal = load_signal(db, selection)
    signal = process_signal(signal, processing)
    print("Updating image... ", end="")
    norm = SymLogNorm(
        linthresh=float(mapper["linthresh"].value),
        vmin=-float(mapper["vlim"].value),
        vmax=float(mapper["vlim"].value),
    )
    image = norm(signal.values).data
    t0 = signal["time"][0].values
    s0 = signal["distance"][0].values
    L = signal["distance"][-1].values - signal["distance"][0].values
    T = signal["time"][-1].values - signal["time"][0].values
    dt = xp.get_sampling_interval(signal, "time")
    dt = np.timedelta64(round(1e9 * dt), "ns")
    ds = xp.get_sampling_interval(signal, "distance")
    x = s0 - ds / 2
    y = t0 - dt / 2
    dw = L + ds
    dh = T + dt
    source_image.data = dict(image=[image], x=[x], y=[y], dw=[dw], dh=[dh])
    print("Done.")


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


def save_picks():
    print("Saving picks... ", end="")
    picks = pd.DataFrame(source_picks.data)
    picks["time"] = pd.to_datetime(picks["time"], unit="ms")
    picks = picks.sort_values("time")
    picks = picks.drop(columns=["status"])
    picks.to_csv(fname.value, index=False)
    print("Done.")


def load_picks():
    print("Loading picks... ", end="")
    picks = pd.read_csv(fname.value, parse_dates=["time"])
    picks["status"] = "inactive"
    source_picks.data = picks.to_dict("list")
    print("Done.")


def reset_picks():
    print("Resetting picks... ", end="")
    source_picks.data = dict(time=[], distance=[], phase=[])
    print("Done.")


def callback():
    update_image()
    update_palette()
    update_range()


# Define a CustomJS callback to handle point deletion
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

b_delete = Button(label="delete", button_type="warning", width=75)
b_delete.js_on_click(delete_selection)
b_apply = Button(label="apply", button_type="success", width=160)
b_apply.on_click(callback)
b_home = Button(label="home", button_type="primary", width=160)
b_home.on_click(update_range)
b_mapper = Button(label="apply", button_type="success", width=160)
b_mapper.on_click(update_image)
b_save = Button(label="save", button_type="success", width=75)
b_save.on_click(save_picks)
b_load = Button(label="load", button_type="primary", width=75)
b_load.on_click(load_picks)
b_reset = Button(label="reset", button_type="danger", width=75)
b_reset.on_click(reset_picks)

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
            fname,
            row(b_save, b_load, b_delete, b_reset),
        ),
    )
)
