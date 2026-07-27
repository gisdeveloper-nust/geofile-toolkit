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

## Supported formats

| Format | Accepted input | Conversion output | Parse endpoint |
| --- | --- | --- | --- |
| Shapefile | `.zip` containing `.shp`, `.shx`, and `.dbf` | `.zip` containing all Shapefile components | `/parse/shapefile` |
| GeoJSON | `.geojson` or `.json` | `.geojson` | `/parse/geojson` |
| KML | `.kml` with Placemark geometries | `.kml` in EPSG:4326 | `/parse/kml` |

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

## Parse GeoJSON

`POST /parse/geojson` accepts a `.geojson` or `.json` FeatureCollection and
returns the same metadata shape as the shapefile parser.

```bash
curl -X POST "http://127.0.0.1:8000/parse/geojson" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/data.geojson"
```

Malformed JSON, missing `type` or `features` keys, and empty FeatureCollections
produce clear client error responses.

## Parse KML

`POST /parse/kml` accepts a `.kml` document containing Placemark geometries
and returns geometry types, feature count, CRS, bounding box, and attribute
fields. Overlay-only KML files are rejected because they do not contain
convertible vector features.

```bash
curl -X POST "http://127.0.0.1:8000/parse/kml" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/places.kml"
```

## Validate GeoJSON

`POST /validate/geojson` checks every feature without changing the uploaded
data. The response reports valid and invalid feature totals and describes each
invalid geometry.

```bash
curl -X POST "http://127.0.0.1:8000/validate/geojson" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/data.geojson"
```

Example response:

```json
{
  "feature_count": 2,
  "valid_count": 1,
  "invalid_count": 1,
  "issues": [
    {
      "feature_index": 1,
      "issue_type": "self_intersection",
      "description": "Self-intersection[1 1]"
    }
  ]
}
```

## Repair GeoJSON

`POST /repair/geojson` repairs fixable geometries and returns the resulting
GeoJSON as a file download. The `X-Repair-Report` response header contains the
`RepairReport` JSON encoded as base64url; `X-Repair-Report-Encoding` identifies
that encoding.

```bash
curl -X POST "http://127.0.0.1:8000/repair/geojson" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/data.geojson" \
  -D repair-headers.txt \
  -o data_repaired.geojson
```

The downloaded file is standard GeoJSON. The repair report lists each invalid
feature with a `fixed` or `unfixable` status and includes aggregate counts.

## Convert formats

`POST /convert` auto-detects Shapefile, GeoJSON, or KML input and converts it
to either of the other supported formats. Upload Shapefiles as ZIP archives.
The optional `target_crs` field accepts values understood by PROJ, such as
`EPSG:3857`. KML output is always reprojected to EPSG:4326.

Convert GeoJSON to KML:

```bash
curl -X POST "http://127.0.0.1:8000/convert" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/data.geojson" \
  -F "target_format=kml" \
  -o data_converted.kml
```

Convert a Shapefile ZIP to reprojected GeoJSON:

```bash
curl -X POST "http://127.0.0.1:8000/convert" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/shapefile.zip" \
  -F "target_format=geojson" \
  -F "target_crs=EPSG:3857" \
  -o data_converted.geojson
```

Shapefile output is returned as a ZIP containing its component files.
Conversion metadata is provided in the base64url-encoded
`X-Conversion-Result` response header.

Run the automated tests with:

```bash
python -m pytest
```

## Roadmap

- [x] Shapefile parser
- [x] GeoJSON parser + validation + repair
- [x] KML parser
- [x] Format conversion layer
