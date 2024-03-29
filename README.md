# xpick

[![DOI](https://zenodo.org/badge/744528873.svg)](https://zenodo.org/doi/10.5281/zenodo.10678341)

Web app for manual picking of DAS data.

## Instalation

Bokeh apps require nodejs that can be installed with conda:

```
conda install nodejs
```

Then xpick can be installed from github:

```
pip install "git+https://github.com/xdas-dev/xpick.git"
```

## Usage

```
xpick <paths_to_your_database>
```

The paths to your databases must be provided. You can use wildcards.

If you work on a remote machine, you need to forward do port forwarding. VSCode automatically does it for you. You can check in the PORT tab of the bottom pannel that every thing is configure correctly. The same port number should be used on the remote and local machine. If the default port (5006) is already in use you can specify another port with the `--port` option.

For more options look at the help

```
xpick -h
```
