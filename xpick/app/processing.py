import xdas
import xdas.signal as xp
from matplotlib.colors import SymLogNorm


def load_signal(selection):
    db = xdas.open_database(selection["database"].value)
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
    return signal


def process_signal(signal, processing):
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
    return signal


def normalize_signal(signal, mapper):
    norm = SymLogNorm(
        linthresh=float(mapper["linthresh"].value),
        vmin=-float(mapper["vlim"].value),
        vmax=float(mapper["vlim"].value),
    )
    image = signal.copy(data=norm(signal.values).data)
    return image
