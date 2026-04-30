import openeo
import os
import base64
from dotenv import load_dotenv

load_dotenv()

def search_sentinel(aoi, start_date, end_date, collection="SENTINEL2_L2A", cloud_cover=20, bands=None):
    print(f"\n--- [BACKEND] 🚀 Optimized Search: {collection} ---")
    try:
        connection = openeo.connect("https://openeo.dataspace.copernicus.eu/")
        connection.authenticate_oidc_client_credentials(
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET")
        )
        print("SUCCESS: Authenticated.")

        search_bands = bands if bands else ["B04", "B03", "B02"]
        
        # We move cloud cover into the load_collection properties to avoid DataCube attribute errors
        load_params = {
            "collection_id": collection,
            "spatial_extent": aoi,
            "temporal_extent": [start_date, end_date],
            "bands": search_bands
        }

        if "SENTINEL2" in collection:
            # Correct way to filter metadata during loading
            load_params["properties"] = {"eo:cloud_cover": lambda c: c <= cloud_cover}

        print(f"STEP: Loading collection with bands {search_bands}...")
        cube = connection.load_collection(**load_params)

        # SPEED FIX: 'mean' is significantly faster than 'median' for large stacks
        print("STEP: Reducing temporal dimension via MEAN...")
        visual_cube = cube.reduce_dimension(dimension="t", reducer="mean")
        
        # SPEED FIX: Downsample to 60m for dashboard preview (10m is too heavy for web)
        print("STEP: Resampling for speed (60m resolution)...")
        visual_cube = visual_cube.resample_spatial(resolution=60)
        
        # Scale to 8-bit for PNG
        visual_cube = visual_cube.linear_scale_range(0, 3000, 0, 255)
        
        print("STEP: Downloading optimized PNG preview...")
        img_bytes = connection.download(visual_cube.save_result(format="PNG"))
        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        
        print(f"SUCCESS: Return payload ready.")
        return {
            "image": f"data:image/png;base64,{base64_img}",
            "aoi": aoi,
            "results": [start_date],
            "bands": search_bands,
            "collection": collection,
            "dates": [start_date, end_date]
        }

    except Exception as e:
        print(f"❌ ERROR in search_sentinel: {str(e)}")
        raise e
