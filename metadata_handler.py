import openeo, os, base64, re, traceback, io
import numpy as np
import xarray as xr
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    conn = openeo.connect("https://openeo.dataspace.copernicus.eu/")
    conn.authenticate_oidc_client_credentials(os.getenv("CLIENT_ID"), os.getenv("CLIENT_SECRET"))
    return conn

def get_raster_metadata(data):
    print("\n--- [BACKEND] 📊 Fast Metadata & Histogram ---")
    try:
        conn = get_connection()
        is_calc = data.get('type') == 'calc'
        expression = data.get('expression')
        bands = list(set(re.findall(r'"([^"]*)"', expression))) if is_calc else data.get('bands', ["B04"])

        cube = conn.load_collection(
            collection_id=data['collection'],
            spatial_extent=data['aoi'],
            temporal_extent=data['dates'],
            bands=bands
        )

        # SPEED FIX: Use MEAN and 100m resolution for metadata preview
        cube = cube.reduce_dimension(dimension="t", reducer="mean")
        cube = cube.resample_spatial(resolution=100) 

        if is_calc:
            bands_dict = {b: cube.band(b) for b in bands}
            cube = eval(expression.replace('"', ''), {"__builtins__": None}, bands_dict)
        else:
            cube = cube.band(bands[0])

        print("STEP: Downloading low-res NetCDF for histogram...")
        bytes_data = conn.download(cube.save_result(format="NetCDF"))
        ds = xr.open_dataset(io.BytesIO(bytes_data), engine="h5netcdf")
        
        # Get the first data variable that isn't 'crs'
        var_name = [v for v in ds.data_vars if v.lower() != 'crs'][0]
        values = ds[var_name].values.flatten().astype(np.float32)
        values = values[~np.isnan(values)]

        hist, _ = np.histogram(values, bins=20)
        
        return {
            "bands": bands,
            "crs": "EPSG:4326",
            "resolution": "100m (Preview)",
            "histogram": hist.tolist()
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
