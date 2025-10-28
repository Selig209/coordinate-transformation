# Coordinate Transformation Web App

A professional web application for transforming coordinates between different Coordinate Reference Systems (CRS), with focus on Ghana's national grid systems.

🌐 **[Live Demo](https://your-app-url.vercel.app)** (Update after deployment)

---

## Features

- **Single Point Transformation**: Real-time coordinate conversion with accuracy information
- **Batch Processing**: Upload CSV files for bulk transformations
- **Interactive Mapping**: Visualize coordinates on Leaflet.js maps
- **5 Coordinate Systems**: WGS84, UTM 30N, UTM 31N, Ghana National Grid, Web Mercator
- **Mobile Responsive**: Works on all devices

---

## Supported Coordinate Systems

| System | EPSG | Coverage | Use Case |
|--------|------|----------|----------|
| WGS84 | 4326 | Global | GPS, international mapping |
| UTM 30N | 32630 | 6°W - 0° | Western Ghana surveys |
| UTM 31N | 32631 | 0° - 6°E | Eastern Ghana surveys |
| Ghana Grid | Custom | Ghana | National surveying |
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
git clone https://github.com/yourusername/coordinate-transformation.git
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

| Transformation | Expected Accuracy |
|---------------|-------------------|
| WGS84 ↔ UTM | < 1 meter |
| WGS84 ↔ Ghana Grid | 1-5 meters |
| UTM ↔ Ghana Grid | 1-5 meters |

---

## Project Structure

```
coordinate-transformation/
├── app.py              # Flask backend
├── requirements.txt    # Python dependencies
├── vercel.json        # Deployment config
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

**Your Name**
- GitHub: [@yourusername](https://github.com/yourusername)
- LinkedIn: [Your Profile](https://linkedin.com/in/yourprofile)
- Email: your.email@example.com

---

## Acknowledgments

- PyProj for coordinate transformation library
- Leaflet.js for mapping capabilities
- Ghana Survey Department for CRS specifications
