from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
import search, raster_calculator, metadata_handler, geotiff_handler

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/search")
async def search_endpoint(data: dict):
    # Offload blocking openEO call to a threadpool
    return await run_in_threadpool(search.search_sentinel, **data)

@app.post("/calculate")
async def calculate_endpoint(data: dict):
    return await run_in_threadpool(raster_calculator.run_math_index, 
        data.get("aoi"), data.get("dates"), data.get("collection"), data.get("expression"))

@app.post("/metadata")
async def metadata_endpoint(data: dict):
    return await run_in_threadpool(metadata_handler.get_raster_metadata, data)

@app.post("/export")
async def export_endpoint(data: dict):
    gtiff_bytes = await run_in_threadpool(geotiff_handler.generate_geotiff, data)
    return Response(content=gtiff_bytes, media_type="image/tiff")
