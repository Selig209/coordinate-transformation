# Coordinate Transformation Web App

A professional web application for transforming coordinates between different Coordinate Reference Systems (CRS), with focus on Ghana's national grid systems.

🌐 **[Live Demo](https://coordinate-transformation.vercel.app)**

---

## Features

- **Single Point Transformation**: Real-time coordinate conversion with accuracy information
- **Batch Processing**: Upload CSV files for bulk transformations
- **Interactive Mapping**: Visualize coordinates on Leaflet.js maps
- **6 Coordinate Systems**: WGS84, UTM 30N, UTM 31N, Ghana National Grid, Ghana Metre Grid, Web Mercator
- **Honest accuracy reporting**: each result shows the EPSG transformation actually applied and its published accuracy
- **Validated**: automated tests check every grid against its defining parameters
- **Mobile Responsive**: Works on all devices

---

## Supported Coordinate Systems

| System | EPSG | Coverage | Use Case |
|--------|------|----------|----------|
| WGS84 | 4326 | Global | GPS, international mapping |
| UTM 30N | 32630 | 6°W - 0° | Western Ghana surveys |
| UTM 31N | 32631 | 0° - 6°E | Eastern Ghana surveys |
| Ghana National Grid (Accra) | 2136 | Ghana | Legacy national grid, **Gold Coast feet** |
| Ghana Metre Grid (Leigon) | 25000 | Ghana | Metric national grid |
| Web Mercator | 3857 | Global | Web mapping |

---

## Tech Stack

- **Backend**: Python, Flask, PyProj
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Mapping**: Leaflet.js
- **Deployment**: Vercel/Netlify ready

---

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/Selig209/coordinate-transformation.git
cd coordinate-transformation
```

2. **Create virtual environment**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the application**
```bash
python app.py
```

5. **Open in browser**
```
http://localhost:5000
```

---

## Usage

### Single Transformation
1. Select source coordinate system
2. Enter coordinates
3. Select target coordinate system
4. Click Transform

### Batch Processing
1. Prepare CSV with columns: `lon,lat` or `x,y`
2. Upload file
3. Select source and target CRS
4. Download transformed results

---

## API Endpoints

### `GET /api/crs-info`
Get information about supported coordinate systems.

### `POST /api/transform`
Transform single coordinate.

**Request:**
```json
{
  "source_crs": "WGS84",
  "target_crs": "UTM_30N",
  "coordinates": {"lon": -0.1870, "lat": 5.6037}
}
```

### `POST /api/transform-batch`
Transform multiple coordinates from CSV.

---

## Transformation Accuracy

| Transformation | Accuracy | Reason |
|---------------|----------|--------|
| WGS84 ↔ UTM / Web Mercator | Exact (< 1 mm) | Same datum, projection conversion only |
| WGS84 ↔ Ghana National Grid | ~6 m onshore, ~25 m offshore | EPSG "Accra to WGS 84" transformations |
| WGS84 ↔ Ghana Metre Grid | ~5 m | EPSG "Leigon to WGS 84 (1)" |

For datum shifts, PyProj selects the most accurate EPSG operation whose area of use contains the point,
and the API returns that operation's name and published accuracy with every result.
For survey-grade work, use locally determined transformation parameters and control points.

---

## Validation

```bash
pip install pytest
pytest -q
```

The tests check, among other things, that:
- the UTM false origin (central meridian, equator) maps to E 500 000 m, N 0
- the Ghana National Grid natural origin (4°40'N, 1°W, Accra datum) maps to E 900 000 ft, N 0
- the Ghana Metre Grid natural origin (Leigon datum) maps to E 274 319.51 m, N 0
- round trips through the API return to the start point within about 1 mm
- onshore and offshore points use the correct Accra datum transformation

---

## Project Structure

```
coordinate-transformation/
├── app.py              # Flask backend
├── requirements.txt    # Python dependencies
├── vercel.json        # Deployment config
├── tests/             # Geodetic validation tests
└── static/
    ├── index.html     # Main interface
    ├── styles.css     # Styling
    └── app.js         # Frontend logic
```

---

## Deployment

### Vercel
```bash
npm install -g vercel
vercel
```

### Netlify
1. Connect repository to Netlify
2. Build command: `pip install -r requirements.txt`
3. Publish directory: `static`

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## License

MIT License - see LICENSE file for details

---

## Author

**Selig Anyawon Amoak**
- GitHub: [@Selig209](https://github.com/Selig209)
- LinkedIn: [Selig Amoak](https://linkedin.com/in/selig-amoak)
- Email: Seligatambire@gmail.com

---

## Acknowledgments

- PyProj for coordinate transformation library
- Leaflet.js for mapping capabilities
- EPSG Geodetic Parameter Dataset for CRS and transformation definitions
