# GeoFile Toolkit

Tools for inspecting and converting geospatial files.

## Setup

Create and activate a virtual environment, then install the pinned dependencies:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

Start the API locally:

```bash
uvicorn main:app --reload
```

The interactive API documentation is available at
`http://127.0.0.1:8000/docs`. Check service availability with:

```bash
curl http://127.0.0.1:8000/health
```

## Parse a shapefile

`POST /parse/shapefile` accepts a ZIP archive containing exactly one
shapefile. The archive must include the matching `.shp`, `.shx`, and `.dbf`
files; include a `.prj` file when coordinate reference system metadata is
available.

```bash
curl -X POST "http://127.0.0.1:8000/parse/shapefile" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/shapefile.zip"
```

A successful response contains the geometry type, feature count, coordinate
reference system, bounding box, and attribute field names and types:

```json
{
  "geometry_type": "Point",
  "feature_count": 2,
  "crs": "GEOGCS[... omitted ...]",
  "bounding_box": [10.0, 20.0, 30.0, 40.0],
  "attribute_fields": {
    "name": "str:80",
    "value": "int:18"
  }
}
```

Run the automated tests with:

```bash
python -m pytest
```
