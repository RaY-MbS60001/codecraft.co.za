from supabase import create_client, Client

SUPABASE_URL = "https://inkuwivfhqyplcuwjduu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlua3V3aXZmaHF5cGxjdXdqZHV1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIwMDc5ODEsImV4cCI6MjA2NzU4Mzk4MX0.6GqG_hWI9VMYU_xCEabJkxTNIgsoECeQW_okHrX-ZpM"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def download_from_supabase(file_path, bucket="documents", save_to="downloads"):
    os.makedirs(save_to, exist_ok=True)
    response = supabase.storage.from_(bucket).download(file_path)
    
    if response:
        local_path = os.path.join(save_to, os.path.basename(file_path))
        with open(local_path, "wb") as f:
            f.write(response)
        return local_path
    else:
        raise Exception(f"File {file_path} not found in Supabase bucket '{bucket}'")