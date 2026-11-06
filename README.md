# Camera intrinsic matrix: crop and resize without losing calibration

A camera projects the same physical point to different pixel coordinates after cropping and resizing. Run a short Python exercise to update the camera matrix and measure the error from using the old one.

[Read the full WIFA Robotics lesson](https://wifarobotics.com/learn/camera-intrinsic-matrix/) for the derivation, annotated examples, and steps for checking the method on recorded images.

## Start from zero

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/). Check `python3 --version` on macOS or Linux, or `py -3 --version` in Windows PowerShell.
2. On the project page, choose **Code → Download ZIP**, extract the folder, and open a terminal in the folder containing `intrinsics.py`. If Git is already installed, use `git clone https://github.com/williamfarokhzad/wifa-camera-intrinsic-matrix.git` and open the cloned folder instead.
3. Run the commands below. On Windows use `py -3` in place of `python3`. No package installation, camera, or network connection is needed for the exercise.

```sh
python3 intrinsics.py examples/identity.json
python3 intrinsics.py examples/crop-half.json
python3 intrinsics.py examples/anisotropic.json
python3 intrinsics.py examples/offscreen.json
python3 -m unittest discover -s tests -v
```

| Case | Expected output pixel | Inside output | Stale matrix error |
| --- | --- | --- | --- |
| Identity | (395.000, 197.000) | true | 0.000 px |
| Crop and half size | (147.250, 68.250) | true | 279.207 px |
| Different scales by axis | (292.500, 38.500) | true | 188.755 px |
| Point outside crop | (−12.750, 191.250) | false | 266.605 px |

For the second case the program prints `K': fx=400.000 fy=410.000 cx=107.250 cy=88.750`. The tests compare the updated projection to 54 independent inverse sampling and ray reconstruction checks across two conventions, nine output sizes, and three positions per size.

## Make one change

Copy `examples/crop-half.json` and change the copy's `mode` to `asymmetric`. The same point becomes (147.500, 68.500). The two focal lengths remain 400 and 410 pixels. Compare this with the original example and check the diagonal shift of 0.25 px on each axis. Do not round the projected point before measuring its error.

## Troubleshooting

* **The file cannot be opened:** run the command from the extracted project root. Use the included JSON files first.
* **Crop extends past the original image:** check that `left + width` and `top + height` do not exceed the calibrated input dimensions.
* **Z must be positive:** the input is a camera frame point. Convert from the world or robot frame before calling the projector and discard points on or behind the camera plane.
* **Your implementation differs by a small fixed shift:** check the resize coordinate mode. `half_pixel` and `asymmetric` are not interchangeable.
* **Errors change near the image edges:** check distortion and rectification. This lab does not undistort images or resample pixel values.

All input is synthetic. The program checks a zero skew pinhole projection and two explicitly defined coordinate transforms. It does not estimate calibration, verify an actual camera, recover depth, account for padding, or connect to robot hardware. The editable SVGs in `diagrams/` accompany the WebP figures used in the lesson.
