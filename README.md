# Giant's Cup Uncut 2026 Pace Predictor

A web-based pace calculator for the Ultra Trail Drakensberg Giant's Cup Uncut (GCU) race. Input your split times at checkpoints to get projected finish times and pacing analysis. Predictions are based on prior year race data, adjusted for your marathon time, trail experience, heart rate (if available), and environmental conditions.

## Features

- **Real-time Projections**: Enter elapsed times at aid stations to see estimated arrival times at future checkpoints.
- **Pre-race Estimates**: Get initial predictions based on your marathon time and experience level.
- **Pacing Analysis**: Detects fade (slowing pace) and provides feedback on your performance.
- **Heart Rate Integration**: Optional HR data refines predictions by factoring in effort levels.
- **Environmental Adjustments**: Accounts for temperature and trail conditions (dry, wet, muddy).
- **Elevation Visualization**: Interactive chart showing the race's elevation profile.
- **Cutoff Warnings**: Alerts for potential cutoff misses with time buffers.
- **Mobile-Friendly**: Responsive design optimized for phones and tablets.

## How to Use

1. **Access the App**: Open `index.html` in a web browser (or visit the hosted version at [GitHub Pages URL]).
2. **Set Your Profile**:
   - Enter your marathon time (hours:minutes).
   - Select trail experience level (novice, intermediate, experienced).
   - Optionally add max/resting heart rate.
3. **Adjust Conditions**: Set temperature and trail wetness.
4. **Enter Splits**: As you progress, input elapsed time (and HR) at each checkpoint.
5. **View Projections**: See updated estimates, pacing feedback, and cutoff status in real-time.
6. **Reset**: Use the reset button to clear all inputs and start over.

## Data Sources

- Race details: Official GCU 2026 course data (61.4 km, 2071m elevation gain, start 06:00).
- Reference profiles: Interpolated from 2025 GCU race results and back-runner estimates.
- Elevation profile: Derived from GPX analysis (see `gcu_gpx_analysis.py` and `extract_profile.py` for processing scripts).

## Technical Notes

- Built with vanilla HTML, CSS, and JavaScript—no external dependencies.
- Client-side only; no data is stored or transmitted.
- Tested in modern browsers (Chrome, Firefox, Safari).

## Contributing

Feedback welcome! Open an issue or PR on GitHub for improvements.

## License

MIT License—free to use and modify.