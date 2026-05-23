
import os
import shutil

def prepare():
    target_dir = r"C:\Users\PRAMANA VISUAL\Pictures\asli"
    processed_dir = os.path.join(target_dir, "processed")
    tracker_file = os.path.join(target_dir, ".upload_tracker.json")
    
    print(f"--- Menyiapkan folder: {target_dir} ---")
    
    # 1. Hapus tracker agar dianggap file baru
    if os.path.exists(tracker_file):
        os.remove(tracker_file)
        print(f"✔ Tracker dihapus: {tracker_file}")
    
    # 2. Pindahkan file dari processed kembali ke root
    if os.path.exists(processed_dir):
        files = os.listdir(processed_dir)
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                src = os.path.join(processed_dir, f)
                dst = os.path.join(target_dir, f)
                
                # Modifikasi sedikit agar hash berubah (hindari Conflict/Duplicate di server)
                try:
                    with open(src, "ab") as fh:
                        fh.write(b"\0") # Tambah 1 byte kosong
                    
                    shutil.move(src, dst)
                    print(f"✔ File dipindahkan & dimodifikasi: {f}")
                except Exception as e:
                    print(f"✘ Gagal memproses {f}: {e}")
        
        # Hapus folder processed jika kosong
        try:
            if not os.listdir(processed_dir):
                os.rmdir(processed_dir)
                print(f"✔ Folder processed dihapus.")
        except:
            pass
    else:
        # Jika file sudah di root, tetap modifikasi agar unik
        for f in os.listdir(target_dir):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                path = os.path.join(target_dir, f)
                with open(path, "ab") as fh:
                    fh.write(b"\0")
                print(f"✔ File di root dimodifikasi agar unik: {f}")

if __name__ == "__main__":
    prepare()
