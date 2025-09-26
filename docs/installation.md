# Installation

This guide provides instructions to install ViVa-SAFELAND.

!!! info "System Requirements"
    The code automatically creates a Python 3.12 virtual environment. However, the code has been tested and works with Python versions starting from 3.8.

## 1. Setting `UV`, the Python project manager

To facilitate the creation of virtual environments and manage Python packages and their dependencies we use a state of the art framework [uv](https://docs.astral.sh/uv/), its installation is straightforward and can be done via the following command:

=== "macOS/Linux"
    Using `curl`
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
    Using `wget`
    ```bash
    wget -qO- https://astral.sh/uv/install.sh | sh
    ```
=== "Windows"
    Use `irm` to download the script and execute it with `iex`:
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

## 2. Install ViVa-SAFELAND

Choose one of the following installation methods:

=== "From PyPI"
    !!! abstract "Recommended for most users"
        Install the latest stable release from the Python Package Index (PyPI).

    ```bash
    uv venv --python 3.12
    uv pip install viva-safeland --upgrade
    ```

=== "From Source"
    !!! abstract "Recommended for developers"
        Install the latest development version directly from the GitHub repository.

    ```bash
    git clone https://github.com/viva-safeland/viva_safeland.git
    cd viva_safeland
    uv sync
    ```

## 3. High-definition Aerial Videos
To use ViVa-SAFELAND, **you need to have high-definition aerial videos**. You can use your own videos or download the provided [dataset](installation.md/#download-the-viva-safeland-dataset)

### Using your own videos
To use your own videos, they should follow these specifications:

- **Format:** `.MP4`
- **Resolution:** 4K (3840x2160 pixels)
- **Frame Rate:** 30 FPS by default, if your video has a different frame rate, you can specify it ([see usage](usage.md/#command-line-interface-cli) for more information).
- **Metadata:** You need to provide the initial altitude of the drone, an `.SRT` file with the same name as the video file is regularly created by the drone. The `.SRT` file should contain the text `rel_alt: <initial_altitude>` with the initial altitude of the drone in meters. The file should be in the same directory as the video file.

    Here is an example of a directory containing a video file and its corresponding metadata file:

    ```bash
    /media/user/HDD/Videos_Dron/DJI_20240910181532_0005_D.MP4
    /media/user/HDD/Videos_Dron/DJI_20240910181532_0005_D.SRT
    ```

    The `.SRT` generated automatically by the drone should look like this:

    ```
    1
    00:00:00,000 --> 00:00:00,033
    <font size="28">FrameCnt: 1, DiffTime: 33ms
    2024-09-10 18:15:32.300
    [iso: 110] [shutter: 1/320.0] [fnum: 1.7] [ev: 0] [color_md: default] [focal_len: 24.00] [latitude: 22.764504] [longitude: -102.550488] [rel_alt: 79.900 abs_alt: 2513.263] [ct: 5729] </font>
    ```

    If you don't have the generated `.SRT` file you can specify the initial altitude of the drone ([see usage](usage.md/#command-line-interface-cli) for more information).

### Download the ViVa-SAFELAND Dataset
Alternatively, you can download the provided [ViVa-SAFELAND Dataset](https://zenodo.org/records/13942934) which contains a collection of high-definition aerial videos from unstructured urban environments, including dynamic obstacles like cars, people and other moving objects. 
**This dataset follows the specifications mentioned above and is ready to use with ViVa-SAFELAND.**

1. Create a directory to store the dataset, (it is not necessary to be in the same directory of the project, due the size you maybe want to store it in a different location like an external hard drive).
2. Download the desired videos with its metadata from [Zenodo](https://zenodo.org/records/13942934).
3. Extract the downloaded files into the created directory.
4. Follow the instructions of [usage](usage.md).