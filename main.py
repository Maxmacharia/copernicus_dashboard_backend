from fastapi import FastAPI, HTTPException, Response
from search import search_sentinel
from fastapi.middleware.cors import CORSMiddleware
from metadata_handler import get_raster_metadata
from raster_calculator import run_math_index

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/search")
def search(data: dict):
    return search_sentinel(**data)

@app.post("/calculate")
def calculate_index(data: dict):
    return run_math_index(data.get("aoi"), data.get("dates"), data.get("collection"), data.get("expression"))

@app.post("/metadata")
def metadata_endpoint(data: dict):
    try:
        return get_raster_metadata(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/visualize")
def visualize_endpoint(data: dict):
    # This uses logic similar to search but with specific band/range parameters
    from metadata_handler import apply_styling
    try:
        return apply_styling(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export")
async def export_layer(data: dict):
    from geotiff_handler import generate_geotiff
    gtiff_bytes = generate_geotiff(data)
    safe_name = data.get('name', 'raster').replace(" ", "_")
    return Response(
        content=gtiff_bytes, 
        media_type="image/tiff",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.tif"}
    )
