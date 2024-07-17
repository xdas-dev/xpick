from xdas import (
    DataArray,
    DataMapping,
    DataSequence,
    open_dataarray,
    open_datacollection,
)


def check_paths(paths):
    if len(paths) == 0:
        print("No data array or data collection provided.")
        exit(1)
    elif len(paths) == 1:
        try:
            open_datacollection(paths[0])
            is_datacollection = True
        except:
            try:
                open_dataarray(paths[0])
                is_datacollection = False
            except:
                print("No data array or data collection found.")
                exit(1)
    else:
        is_datacollection = False
        for path in paths:
            try:
                open_dataarray(path)
            except:
                print(f"No data array found for {path}.")
                exit(1)
    return is_datacollection


def uniquifiy(seq):
    seen = set()
    return list(x for x in seq if x not in seen and not seen.add(x))


def get_codes(obj, name=None):
    if isinstance(obj, DataArray):
        codes = ["" if name is None else name]
    elif isinstance(obj, DataSequence):
        codes_list = [get_codes(val, name) for val in obj]
        codes = []
        for val in codes_list:
            codes.extend(val)
    elif isinstance(obj, DataMapping):
        codes_list = [
            get_codes(val, f"{name}.{key}" if name else key) for key, val in obj.items()
        ]
        codes = []
        for val in codes_list:
            codes.extend(val)
    return uniquifiy(codes)
