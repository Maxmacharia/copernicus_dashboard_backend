import openeo
import os
import xarray as xr
import base64
from dotenv import load_dotenv

load_dotenv()

def search_sentinel(aoi, start_date, end_date, collection="SENTINEL2_L2A", cloud_cover=100, bands=None):
    print(f"\n--- [BACKEND] Starting Visual Search: {collection} ---")
    
    try:
        # 1. Connection
        print("STEP 1: Connecting to CDSE API...")
        connection = openeo.connect("https://openeo.dataspace.copernicus.eu")
        
        # 2. Authentication
        print("STEP 2: Authenticating...")
        connection.authenticate_oidc_client_credentials(
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET")
        )
        print("SUCCESS: Authenticated.")

        # 3. Load Collection
        search_bands = bands if bands and len(bands) > 0 else ["B04", "B03", "B02"]
        print(f"STEP 3: Loading collection {collection} with bands {search_bands}")
        
        load_params = {
            "collection_id": collection,
            "spatial_extent": aoi,
            "temporal_extent": [start_date, end_date],
            "bands": search_bands
        }
        if "SENTINEL2" in collection:
            load_params["properties"] = {"eo:cloud_cover": lambda c: c.lte(cloud_cover)}

        cube = connection.load_collection(**load_params)

        # 4. Fetch Dates (Metadata)
        print("STEP 4: Fetching available dates...")
        # We execute this separately to get the JSON list of dates
        summary_cube = cube.aggregate_spatial(geometries=aoi, reducer="mean")
        raw_metadata = summary_cube.execute()
        
        dates = []
        if isinstance(raw_metadata, dict):
            dates = list(raw_metadata.keys())
        elif isinstance(raw_metadata, xr.DataArray):
            dates = [str(t.values) for t in raw_metadata.coords["t"]]
        print(f"SUCCESS: Found {len(dates)} scenes.")

        # 5. Visual Processing & Rendering
        if len(dates) > 0:
            print("STEP 5: Processing Median and Scaling for PNG...")
            visual_cube = cube.reduce_dimension(dimension="t", reducer="median")
            visual_cube = visual_cube.linear_scale_range(0, 3000, 0, 255)
            
            # 6. DOWNLOAD PIXELS
            print("STEP 6: Downloading PNG bytes via connection.download()...")
            # Instead of .execute(), we use the connection to download the final result
            img_bytes = connection.download(visual_cube.save_result(format="PNG"))
            
            # 6. Encode for Frontend
            base64_img = base64.b64encode(img_bytes).decode('utf-8')
            print(f"SUCCESS: Image encoded ({len(base64_img)} characters).")
            
            return {
                "results": dates, 
                "image": f"data:image/png;base64,{base64_img}",
                "aoi": aoi
            }
        
        return {"results": [], "image": None}

    except Exception as e:
        print(f"❌ ERROR in search_sentinel: {str(e)}")
        raise e
