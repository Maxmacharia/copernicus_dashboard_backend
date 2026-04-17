#!/usr/bin/env python3

from fastapi import FastAPI, HTTPException, Response  # Added Response here
from search import search_sentinel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", 
                   "http://127.0.0.1:5173", 
                   "https://data-explorer-dashboard-nine.vercel.app"
                   ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/search")
def search(data: dict):
    print("\n>>> Incoming Dashboard Request")
    try:
        aoi = data.get("aoi")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        collection = data.get("collection", "SENTINEL2_L2A")
        cloud_cover = data.get("cloud_cover", 100)
        bands = data.get("bands", [])

        if not aoi:
            print("!!! Validation Error: No AOI provided")
            return {"error": "Please draw an area on the map first."}

        # Call search function
        data_response = search_sentinel(
            aoi=aoi, 
            start_date=start_date, 
            end_date=end_date, 
            collection=collection,
            cloud_cover=cloud_cover,
            bands=bands
        )

        print(f"<<< Success: Returning {len(data_response['results'])} dates\n")
        return data_response
    
    except Exception as e:
        print(f"!!! FastAPI Endpoint Error: {str(e)}")
        return {"error": str(e)}

@app.post("/calculate")
def calculate_index(data: dict):
    try:
        # Extract expression and parameters
        expression = data.get("expression")
        collection = data.get("collection")
        aoi = data.get("aoi")
        dates = data.get("dates")
        
        # Call processing function in raster_calculator.py
        from raster_calculator import run_math_index
        result = run_math_index(aoi, dates, collection, expression)
        return result
    except Exception as e:
        return {"error": str(e)}

@app.post("/export")
async def export_layer(data: dict):
    try:
        from geotiff_handler import generate_geotiff
        # Generate the actual file bytes
        gtiff_bytes = generate_geotiff(data)
        
        # Sanitize filename
        safe_name = data.get('name', 'raster').replace(" ", "_").replace("(", "").replace(")", "")
        
        # Explicitly return the binary response
        return Response(
            content=gtiff_bytes, 
            media_type="image/tiff",
            headers={
                "Content-Disposition": f"attachment; filename={safe_name}.tif",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        print(f"Export Route Failure: {e}")
        raise HTTPException(status_code=500, detail=str(e))
