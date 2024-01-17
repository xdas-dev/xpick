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
    TextInput,
    Toggle,
)
from bokeh.plotting import curdoc, figure
from bokeh.transform import factor_cmap
from matplotlib.colors import SymLogNorm
from pickertool import PickerTool

parser = argparse.ArgumentParser()
parser.add_argument("--path")
args = parser.parse_args()

# global constants
palette_mapping = ["Viridis256", cc.CET_D1A]
phases = ["Pp", "Ps", "Ss"]
phase_cmap = factor_cmap(
    field_name="phase", palette=["#7F0DFF", "#BF0DFF", "#FF00FF"], factors=phases
)

# global variables
db = xdas.open_database(args.path)
range_x = Range1d()
range_y = Range1d()
source_image = ColumnDataSource(data=dict(image=[], x=[], y=[], dw=[], dh=[]))
source_picks = ColumnDataSource(data=dict(time=[], distance=[], phase=[], status=[]))


# layout
doc = curdoc()
fig = figure(
    width=1920,
    height=1080,
    y_axis_type="datetime",
    x_range=range_x,
    y_range=range_y,
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
    size=1,
    color=phase_cmap,
)

fig.add_tools(LassoSelectTool())
for phase in phases:
    fig.add_tools(PickerTool(source=source_picks, phase=phase))


selection = {
    "starttime": TextInput(title="starttime", value="2021-11-13T01:40:55"),
    "endtime": TextInput(title="endtime", value="2021-11-13T01:41:15"),
    "startdistance": TextInput(title="startdistance", value="15_000.0"),
    "enddistance": TextInput(title="enddistance", value="125_000.0"),
}
processing = {
    "space": {
        "integration": Toggle(label="Integrate"),
        "decimation": TextInput(title="Decimate", value=""),
        "mean_removal": TextInput(title="Mean Removal", value=""),
    },
    "time": {
        "integration": Toggle(label="Integrate"),
        "decimation": TextInput(title="Decimate", value=""),
        "highpass": TextInput(title="Highpass", value=""),
    },
}
mapper = {
    "palette": RadioButtonGroup(labels=["viridis", "seismic"], active=0),
    "linthresh": TextInput(title="linthresh", value="1e-8"),
    "vlim": TextInput(title="vlim", value="1e-5"),
}
fname = TextInput(title="fname", value="picks.csv")

signal = xr.DataArray()


# callbacks
def update_signal():
    global signal
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
    # distance
    if processing["space"]["integration"].active:
        signal = xp.integrate(signal, dim="distance")
    if q := processing["space"]["decimation"].value:
        signal = xp.decimate(
            signal, int(q), ftype="fir", zero_phase=True, dim="distance"
        )
    if wlen := processing["space"]["mean_removal"].value:
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


def update_image():
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


def update_palette():
    palette = palette_mapping[mapper["palette"].active]
    image_mapper = LinearColorMapper(palette=palette, low=0, high=1)
    img.glyph.color_mapper = image_mapper


mapper["palette"].on_change("active", lambda attr, old, new: update_palette())


def update_range():
    x, y, dw, dh = [source_image.data[key][0] for key in ["x", "y", "dw", "dh"]]
    range_x.start = x
    range_x.end = x + dw
    range_x.bounds = (x, x + dw)
    range_y.start = y + dh
    range_y.end = y
    range_y.bounds = (y, y + dh)


def save_picks():
    picks = pd.DataFrame(source_picks.data)
    picks["time"] = pd.to_datetime(picks["time"], unit="ms")
    picks = picks.sort_values("time")
    picks = picks.drop(columns=["status"])
    picks.to_csv("data/" + fname.value, index=False)


def load_picks():
    picks = pd.read_csv("data/" + fname.value, parse_dates=["time"])
    picks["status"] = "inactive"
    source_picks.data = picks.to_dict("list")


def reset_picks():
    source_picks.data = dict(time=[], distance=[], phase=[])


def callback():
    update_signal()
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

b_delete = Button(label="delete")
b_delete.js_on_click(delete_selection)

b_apply = Button(label="apply")
b_apply.on_click(callback)
b_home = Button(label="home")
b_home.on_click(update_range)

b_mapper = Button(label="apply")
b_mapper.on_click(update_image)

b_save = Button(label="save")
b_save.on_click(save_picks)
b_load = Button(label="load")
b_load.on_click(load_picks)
b_reset = Button(label="reset")
b_reset.on_click(reset_picks)

doc.add_root(
    row(
        fig,
        column(
            Div(text="<h2>Selection</h2>"),
            b_delete,
            *selection.values(),
            row(b_apply, b_home),
            Div(text="<h2>Processing</h2>"),
            Div(text="<h3>Space</h3>"),
            *processing["space"].values(),
            Div(text="<h3>Time</h3>"),
            *processing["time"].values(),
            Div(text="<h2>Colormap</h2>"),
            *mapper.values(),
            b_mapper,
            Div(text="<h2>File</h2>"),
            fname,
            row(b_save, b_load, b_reset),
        ),
    )
)
