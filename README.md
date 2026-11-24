# Schottky Decay Monitor GUI

A Tkinter + Matplotlib interactive GUI tool for inspecting Schottky frequency-domain `.npz` spectrograms (2D waterfall plots + 1D mean PSD spectra) with optional CSV metadata filtering (`ion`, `harmonic`, `peak_pos`), automatic `reconstruct_` filename prefix stripping, and flexible navigation (`Previous`, `Next`, and `Pick Specific Next`).

## Features

- **Dual Mode Operation**:
  - **CSV Mode**: Loads a CSV summary table (such as `*_reconstruct_statics_*.csv`), strips the `reconstruct_` prefix from `filename` to locate actual `.npz` files, filters by `ion` and `harmonic`, and defaults the frequency window to `peak_pos ± 5 kHz` (`Hz` converted to `MHz`).
  - **Folder Mode**: Falls back to scanning a selected directory (or single `.npz` file's parent directory) when no CSV is loaded.
- **Flexible Navigation & Window Management**:
  - Switch across entries/files with **Previous**, **Next**, dropdown selection, or **Pick Specific Next...** dialog.
  - Optional **Auto-plot on switch** (`切换后自动绘图`).
  - **Closes previous Matplotlib figure windows by default** on switching, with a **Keep history figure windows** (`保留历史图像窗口`) checkbox when multi-window comparison is needed.
- **Publication-Style Dual Subplots**:
  - Top panel (3:1 height ratio): Logarithmic-scale waterfall spectrogram (`viridis`, `LogNorm`) with timestamp Y-axis parsed from filename (`YYYY-MM-DDTHH-MM-SS` or `YYYY-MM-DD_HH-MM-SS`) plus `times` offset.
  - Bottom panel: 1D mean PSD (`V²/Hz`) on a log Y-axis, aligned in X width with the top panel via `make_axes_locatable`.
  - Handles frequency bin-edge vs. bin-center length alignment (`len(frequencies) == psd_arrays.shape[1] + 1`).

## Project Structure

```text
schottky-decay-monitor-gui/
├── schottky_gui.py     # Main GUI and plotting script
├── requirements.txt    # Python dependencies
├── .gitignore          # Git ignore rules
└── README.md           # Project documentation
