import openeo, os, base64, re, traceback
from dotenv import load_dotenv

load_dotenv()

def run_math_index(aoi, dates, collection, expression):
    print(f"\n---- [BACKEND] ⚡ Fast Raster Math: {expression} ----")
    try:
        connection = openeo.connect("https://openeo.dataspace.copernicus.eu/")
        connection.authenticate_oidc_client_credentials(
            client_id=os.getenv("CLIENT_ID"), 
            client_secret=os.getenv("CLIENT_SECRET")
        )

        required_bands = list(set(re.findall(r'"([^"]*)"', expression)))
        
        cube = connection.load_collection(
            collection_id=collection,
            spatial_extent=aoi,
            temporal_extent=dates,
            bands=required_bands
        )

        # SPEED FIX: Use 'mean' and resample to 60m for instant dashboard display
        print("STEP: Processing math with MEAN and 60m Resampling...")
        processed = cube.reduce_dimension(dimension="t", reducer="mean")
        processed = processed.resample_spatial(resolution=60)
        
        bands_dict = {band: processed.band(band) for band in required_bands}
        clean_expr = expression.replace('"', '')
        index_cube = eval(clean_expr, {"__builtins__": None}, bands_dict)

        # Scale index (-1 to 1) to 0-255 for the frontend PNG
        visual_cube = index_cube.linear_scale_range(-1, 1, 0, 255)
        
        print("STEP: Downloading result...")
        img_bytes = connection.download(visual_cube.save_result(format="PNG"))
        base64_img = base64.b64encode(img_bytes).decode('utf-8')

        print("SUCCESS: Calculation complete.")
        return {
            "image": f"data:image/png;base64,{base64_img}",
            "aoi": aoi,
            "metadata": {"bands": ["Index"], "type": "calc"}
        }

    except Exception as e:
        print(f"❌ ERROR in raster_calculator: {str(e)}")
        traceback.print_exc()
        return {"error": str(e), "image": None}
