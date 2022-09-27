import glob
import math
import os
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def rasterize_labels(directory: str) -> None:
    """Rasterize the GeoJSON labels for each of the aerial images."""
    os.chdir(directory)

    for filename in glob.glob("*19.png"):
        filename = filename.replace(".png", "")
        _, x_tile, y_tile, zoom = re.split("-", filename)
        bounding_box = get_bounding_box(int(x_tile), int(y_tile), int(zoom))

        clip_labels = f"""
            ogr2ogr \
                -clipsrc {bounding_box} \
                -f GeoJSON {filename}.geojson labels.geojson
        """
        os.system(clip_labels)

        rasterize_labels = f"""
            gdal_rasterize \
                -burn 255 -burn 255 -burn 255 \
                -ts 256 256 \
                -te {bounding_box} {filename}.geojson {filename}.tif
        """
        os.system(rasterize_labels)

        convert_to_png = f"""
            gdal_translate \
                -ot Byte \
                -of PNG \
                -scale \
                -co worldfile=yes {filename}.tif {filename}-burned.png
        """
        os.system(convert_to_png)
        threshold_and_save_image(f"{filename}-burned.png", directory)

    clean_up()


def get_bounding_box(x_tile: int, y_tile: int, zoom: int) -> str:
    """Get the four corners of the OAM image as coordinates.

    This function gives us the limiting values that we will pass to
    the GDAL commands. We need to make sure that the raster image
    that we're generating have the same dimension as the original image.
    Hence, we'll need to fetch these extrema values.
    """
    bottom_left = num2deg(x_tile, y_tile, zoom)
    top_right = num2deg(x_tile + 1, y_tile + 1, zoom)
    bounding_box = [*bottom_left, *top_right]

    return "".join([f"{x} " for x in bounding_box])


def num2deg(x_tile: int, y_tile: int, zoom: int) -> tuple[float, float]:
    """Convert coordinates from web-mercator to mercator."""
    n = 2.0**zoom
    lon_deg = x_tile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y_tile / n)))
    lat_deg = math.degrees(lat_rad)

    return lon_deg, lat_deg


def threshold_and_save_image(filename: str, directory: str) -> None:
    """Save an image after vertically reflecting and thresholding it.

    After converting the TIF files to PNGs, we get inverted images.
    To fix this mirroring issue, we need to reflect the generated images
    vertically. Since we're interested in getting a mask, the images should
    only have black and white colors. We can ensure this by performing 
    binary thresholding with OpenCV.
    """
    new_filename = filename.replace("burned.png", "label.png")
    base_path = Path(f"../../rasterized_labels/{directory}")
    base_path.mkdir(parents=True, exist_ok=True)
    path = os.path.join(base_path, new_filename)

    image = Image.open(filename)
    image_reflected = np.flip(image, axis=0)
    _, binary_image_arr = cv2.threshold(image_reflected, 127, 255, cv2.THRESH_BINARY)
    binary_image = Image.fromarray(binary_image_arr)
    binary_image.save(path)


def clean_up() -> None:
    """Remove the intermediary files."""
    os.system("rm OAM*.geojson")
    os.system("rm *.tif")
    os.system("rm *burned*")
    os.chdir("..")


if __name__ == "__main__":
    os.chdir("data/from_hot")
    for i in range(1, 6):
        rasterize_labels(str(i))
