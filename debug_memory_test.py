
import sys
import os
import time
import json
import psutil
import gc

# Simulasi data besar seperti yang ada di worker.py
def simulate_large_process(num_files=20000):
    print(f"--- Memulai simulasi dengan {num_files} file ---")
    
    process = psutil.Process(os.getpid())
    mem_start = process.memory_info().rss / 1024 / 1024
    print(f"RAM Awal: {mem_start:.2f} MB")

    # 1. Simulasi all_files (list string path)
    all_files = [f"C:/Users/USER/Documents/Photos/DSC_{i:05d}.jpg" for i in range(num_files)]
    
    # 2. Simulasi tracking data (dict besar)
    tracking_data = {}
    for i in range(num_files):
        filename = f"DSC_{i:05d}.jpg"
        tracking_data[filename] = {
            'status': 'success',
            'timestamp': time.time(),
            'tab_id': (i % 5) + 1,
            'size': 5000000,
            'id': f"hash_{i}"
        }
    
    # 3. Simulasi Log (list string besar)
    logs = []
    for i in range(num_files // 10): # Anggap 1 log per 10 file
        logs.append(f"[12:00:00] Berhasil mengunggah DSC_{i:05d}.jpg ke server Fotoyu.")

    mem_after_load = process.memory_info().rss / 1024 / 1024
    print(f"RAM Setelah Load Data: {mem_after_load:.2f} MB (Naik {mem_after_load - mem_start:.2f} MB)")

    print("\n--- Simulasi Proses Selesai (Cleanup Dimulai) ---")
    
    # Simulasi menghapus referensi (seperti saat worker selesai tapi app masih buka)
    # Di Python, jika variabel masih ada di lingkup (scope) fungsi/objek, memori tidak dilepas.
    
    print("Menghapus variabel besar secara manual...")
    del all_files
    del tracking_data
    del logs
    
    # Trigger Garbage Collector
    gc.collect()
    
    mem_after_cleanup = process.memory_info().rss / 1024 / 1024
    print(f"RAM Setelah del & gc.collect(): {mem_after_cleanup:.2f} MB")
    print(f"Memori yang tersisa/tidak kembali: {mem_after_cleanup - mem_start:.2f} MB")

if __name__ == "__main__":
    simulate_large_process(20000)
    print("\nKesimpulan: Meskipun variabel dihapus, Python seringkali tidak mengembalikan 100% memori ke OS segera.")
