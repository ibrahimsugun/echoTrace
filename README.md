
# Sound Source Localization Project

This project simulates the process of determining the location of a sound source based on the Time Difference of Arrival (TDOA) method using four microphones placed in a square formation.

## Overview

In this project, we calculate the sound source's location by analyzing the time differences of sound arrival at different microphones. The microphones are positioned in a 2D plane, and the system estimates the sound's origin point based on the arrival times at each microphone.

### Features:
- **Microphone Setup**: The microphones are positioned at the corners of a square.
- **Sound Speed**: We assume a constant sound speed of 343 m/s (at room temperature).
- **Mouse Interaction**: Click anywhere on the graph to simulate a sound source. The algorithm will estimate the location of the sound source based on the times at which the sound reaches each microphone.
- **Clear Function**: You can clear the graph with the "Clear" button.

## Code Explanation

### Libraries
```python
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from matplotlib.widgets import Button
```

We use `numpy` for numerical calculations, `matplotlib` for plotting, and `scipy.optimize` for optimization.

### Microphone Placement
The microphones are placed at the corners of a square with coordinates as follows:

```python
mic_positions = np.array([
    [0, 0],    # Bottom-left
    [10, 0],   # Bottom-right
    [0, 10],   # Top-left
    [10, 10]   # Top-right
])
```

### Calculating Distance
We calculate the distance between each microphone and the source position using the Euclidean distance formula:

```python
def calculate_distance(mic_pos, source_pos):
    return np.sqrt((mic_pos[0] - source_pos[0]) ** 2 + (mic_pos[1] - source_pos[1]) ** 2)
```

### Time Difference of Arrival (TDOA)
The time difference between the microphones is calculated and converted to a distance difference:

```python
def time_to_distance(time, sound_speed):
    return time * sound_speed
```

### Loss Function
The loss function is used to minimize the error between the calculated and observed time differences, helping us estimate the sound source's location:

```python
def tdoa_loss(source_pos, mic_positions, time_stamps):
    # Calculates the loss between the actual and predicted distances
```

### Optimization
The `scipy.optimize.minimize` function is used to optimize the sound source's position:

```python
def find_sound_source(mic_positions, time_stamps):
    result = minimize(tdoa_loss, initial_guess, args=(mic_positions, time_stamps), method='Nelder-Mead')
    return result.x
```

### Interaction
The program allows you to click on the plot to simulate a sound source. The system then estimates the source position and plots the actual and estimated points.

```python
def on_click(event):
    # Updates the plot with the clicked position and the estimated source
```

### Running the Simulation
The graph is updated dynamically to display the microphone positions, real sound source, and estimated sound source.

```python
fig, ax = plt.subplots()
update_plot()
plt.show()
```

## How to Run

1. Ensure you have Python installed with the required libraries (`numpy`, `matplotlib`, `scipy`).
2. Run the script, and a plot will appear.
3. Click anywhere on the plot to simulate a sound source.
4. The estimated position of the sound source will be displayed in green, and the real position in red.

## Conclusion
This project provides a basic simulation of sound source localization using TDOA and four microphones. It demonstrates the application of optimization techniques to estimate the position of a sound source in a 2D space.
