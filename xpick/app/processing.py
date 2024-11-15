import numpy as np
import xdas
import xdas.signal as xp
from matplotlib.colors import SymLogNorm


def load_signal(selection):
    if path := selection["datacollection"]:
        code = selection["dataarray"].value
        db = xdas.open_datacollection(path)
        for key in code.split("."):
            db = db[key]
    else:
        path = selection["dataarray"].value
        db = xdas.open_dataarray(path)
    # load
    signal = db.sel(
        time=slice(
            (
                None
                if (starttime := selection["starttime"].value.strip()) == ""
                else starttime
            ),
            None if (endtime := selection["endtime"].value.strip()) == "" else endtime,
        ),
        distance=slice(
            (
                None
                if (startdistance := selection["startdistance"].value.strip()) == ""
                else float(startdistance)
            ),
            (
                None
                if (enddistance := selection["enddistance"].value.strip()) == ""
                else float(enddistance)
            ),
        ),
    ).load()
    if isinstance(signal, xdas.DataSequence):
        if len(signal) > 1:
            raise ValueError("Data collection must contain only one data array.")
        else:
            signal = signal[0]
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
        signal = xp.filter(signal, freq=float(freq), btype="highpass", dim="time")
    return signal


def normalize_signal(signal, mapper):
    vlim = (
        float(mapper["vlim"].value)
        if mapper["vlim"].value
        else np.max(np.abs(signal.values))
    )
    factor = 10 ** np.floor(np.log10(abs(vlim)))
    vlim = np.ceil(vlim / factor) * factor
    mapper["vlim"].value = str(vlim)
    linthresh = (
        float(mapper["linthresh"].value) if mapper["linthresh"].value else vlim / 10
    )
    mapper["linthresh"].value = str(linthresh)
    norm = SymLogNorm(
        linthresh=linthresh,
        vmin=-vlim,
        vmax=vlim,
    )
    image = signal.copy(data=norm(signal.values).data)
    return image
