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
| GPX | `.gpx` with waypoints, tracks, or routes | `.gpx` for point-only or line-only data | `/parse/gpx` |
| CSV | `.csv` with latitude/longitude columns | `.csv` for Point data | `/parse/csv` |

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

## Parse GPX

`POST /parse/gpx` accepts GPX 1.0 or 1.1 and reports waypoint, track, and route
counts separately, along with combined geometry metadata.

```bash
curl -X POST "http://127.0.0.1:8000/parse/gpx" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/activity.gpx"
```

Malformed XML, unsupported GPX versions, and files without waypoints, tracks,
or routes produce clear client error responses.

## Parse latitude/longitude CSV

`POST /parse/csv` converts coordinate rows to EPSG:4326 Point geometries.
Common column names such as `lat`/`lon`, `latitude`/`longitude`, and `y`/`x`
are detected automatically.

```bash
curl -X POST "http://127.0.0.1:8000/parse/csv" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/points.csv"
```

For custom column names, provide the optional query parameters:

```bash
curl -X POST \
  "http://127.0.0.1:8000/parse/csv?lat_col=Ycoord&lon_col=Xcoord" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/points.csv"
```

Coordinates must be numeric, with latitude between -90 and 90 and longitude
between -180 and 180.

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

## Batch ZIP processing

`POST /batch/process` accepts a ZIP containing mixed supported spatial files.
Each file is processed independently, so one corrupt input does not prevent
valid files from completing. Every result includes its filename, progress
position, success/failure status, and either a result or error message.

Use `parse`, `validate`, or `convert` as the operation. Batch conversion
defaults to GeoJSON; use `convert:kml`, `convert:gpx`, `convert:csv`, or
another supported target to select the output format.

```bash
curl -X POST "http://127.0.0.1:8000/batch/process" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/mixed-spatial-files.zip" \
  -F "operation=parse"
```

## Spatial Operations

The `/analyze/*` endpoints accept supported spatial uploads, including
Shapefile ZIP archives. Analysis downloads use GeoJSON so results can be opened
directly by GIS software or passed into another GeoFile Toolkit operation.

### Check polygon topology

`POST /analyze/topology` detects polygon overlaps, coverage gaps, and small
sliver features. The JSON report includes issue counts, severity totals, and
feature references.

```bash
curl -X POST "http://127.0.0.1:8000/analyze/topology" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/parcels.geojson"
```

Use topology analysis before publishing administrative boundaries, parcels,
or other polygon coverages where shared edges should not overlap or leave
gaps.

### Clip a layer

`POST /analyze/clip` limits input features to a boundary layer and downloads
the result as `clipped.geojson`.

```bash
curl -X POST "http://127.0.0.1:8000/analyze/clip" \
  -H "Content-Type: multipart/form-data" \
  -F "input_file=@path/to/roads.geojson" \
  -F "clip_file=@path/to/study-area.geojson" \
  -o clipped.geojson
```

Clipping is useful for extracting data inside a project area, municipality,
watershed, or other region of interest.

### Merge layers

`POST /analyze/merge` combines two or more layers. Inputs with different CRS
definitions are reprojected to the first layer's CRS before merging.

```bash
curl -X POST "http://127.0.0.1:8000/analyze/merge" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@path/to/north.geojson" \
  -F "files=@path/to/south.geojson" \
  -o merged.geojson
```

Use merge to combine tiled, regional, or periodically collected datasets into
one layer.

### Spatial join

`POST /analyze/spatial-join` transfers attributes between two layers using
`intersects`, `within`, or `contains`.

```bash
curl -X POST "http://127.0.0.1:8000/analyze/spatial-join" \
  -H "Content-Type: multipart/form-data" \
  -F "left_file=@path/to/points.geojson" \
  -F "right_file=@path/to/districts.geojson" \
  -F "predicate=within" \
  -o spatial_join.geojson
```

Spatial joins can assign points to districts, find intersecting assets, or
associate containing polygons with smaller features.

### Geometry statistics

`POST /analyze/stats` returns per-feature area, perimeter, centroid, and vertex
count plus dataset totals. Measurements use the uploaded layer's CRS units.

```bash
curl -X POST "http://127.0.0.1:8000/analyze/stats" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/features.geojson"
```

Use a projected CRS when metric area or length values are required.

Run the automated tests with:

```bash
python -m pytest
```

## Roadmap

- [x] Shapefile parser
- [x] GeoJSON parser + validation + repair
- [x] KML parser
- [x] Format conversion layer
- [x] GPX parser
- [x] CSV latitude/longitude parser
- [x] Mixed-file batch processing
- [x] Polygon topology validation
- [x] Spatial analysis operations
