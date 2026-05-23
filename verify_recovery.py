import os
import time
import json
import shutil
from core.worker import AutomationWorker as Worker
from core.state_machine import UploadMode

def test_recovery_logic():
    # 1. Setup Mock Environment
    test_dir = os.path.abspath("test_recovery_env")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    source_dir = os.path.join(test_dir, "source")
    processed_dir = os.path.join(test_dir, "processed")
    failed_dir = os.path.join(test_dir, "failed")
    
    os.makedirs(source_dir)
    os.makedirs(processed_dir)
    os.makedirs(failed_dir)
    
    # Create 10 dummy files
    files = []
    for i in range(10):
        f_path = os.path.join(source_dir, f"test_{i}.jpg")
        with open(f_path, "w") as f:
            f.write("dummy")
        files.append(f_path)
    
    # 2. Mock Config
    config = {
        "current_account": "test_acc",
        "folder": source_dir,
        "tabs": 2,
        "batch_size": 5,
        "type": "foto",
        "auto_calc": False
    }
    
    # 3. Create Worker (Headless for server testing)
    worker = Worker(config)
    worker.mode = UploadMode.SAFE
    
    # 4. Inject dummy data into worker's tracking
    # We will simulate that 2 files are already uploaded (success)
    # and the engine stops while the rest are pending.
    
    print("--- SIMULASI RECOVERY ---")
    print(f"Total file sumber: {len(files)}")
    
    # Mocking the engine_start_time and tabs
    engine_start_time = time.time()
    
    # We create a dummy TabAutomation object to test the cleanup logic directly
    from core.automation import TabAutomation
    
    class MockPage:
        def is_closed(self): return True
        def close(self): pass
        def on(self, event, handler): pass # Added on method
        def set_default_timeout(self, t): pass
        @property
        def url(self): return "https://www.fotoyu.com/upload"

    # Mocking Tab 1
    tab1 = TabAutomation(
        tab_id=1,
        page=MockPage(),
        files=files[:5],
        config=config,
        logger_func=print,
        global_lock={'injector': None}
    )
    # Simulate file 0 and 1 are already success in tracker
    tab1.upload_tracking = {
        "test_0.jpg": {"status": "success", "timestamp": engine_start_time, "tab_id": 1},
        "test_1.jpg": {"status": "success", "timestamp": engine_start_time, "tab_id": 1}
    }
    # Move them to processed physically
    os.rename(os.path.join(source_dir, "test_0.jpg"), os.path.join(processed_dir, "test_0.jpg"))
    os.rename(os.path.join(source_dir, "test_1.jpg"), os.path.join(processed_dir, "test_1.jpg"))
    
    # Tab 1 was processing test_2, test_3, test_4
    tab1.current_batch_files = [
        os.path.join(source_dir, "test_2.jpg"),
        os.path.join(source_dir, "test_3.jpg"),
        os.path.join(source_dir, "test_4.jpg")
    ]
    tab1.file_index = 5 # All files in tab 1 assigned
    
    # Mocking Tab 2 (Not yet started or just created)
    tab2 = TabAutomation(
        tab_id=2,
        page=MockPage(),
        files=files[5:],
        config=config,
        logger_func=print,
        global_lock={'injector': None}
    )
    tab2.file_index = 0 # No files processed yet
    
    tabs = [tab1, tab2]
    file_chunks = [files[:5], files[5:]]
    current_tabs = 2
    
    # 5. EXECUTE CLEANUP LOGIC (Extracted from worker.py)
    print("\n[Mulai Cleanup]")
    
    active_files_found = False
    for tab in tabs:
        remaining_in_tab = []
        if tab.current_batch_files:
            remaining_in_tab.extend(tab.current_batch_files)
        if tab.file_index < len(tab.all_files):
            remaining_in_tab.extend(tab.all_files[tab.file_index:])
        
        remaining_in_tab = list(dict.fromkeys(remaining_in_tab))
        
        actual_failed_to_move = []
        for f_path in remaining_in_tab:
            f_name = os.path.basename(f_path)
            if tab.upload_tracking.get(f_name, {}).get('status') != 'success':
                actual_failed_to_move.append(f_path)
        
        if actual_failed_to_move:
            print(f"Tab {tab.tab_id}: Memindahkan {len(actual_failed_to_move)} file ke failed.")
            tab._mark_batch(actual_failed_to_move, 'failed')
            tab._move_files(actual_failed_to_move, failed_dir)

    # 6. VERIFIKASI HASIL
    processed_count = len(os.listdir(processed_dir))
    failed_count = len(os.listdir(failed_dir))
    source_count = len([f for f in os.listdir(source_dir) if f.endswith(".jpg")])
    
    print("\n--- HASIL VERIFIKASI ---")
    print(f"File di folder PROCESSED: {processed_count} (Harus 2)")
    print(f"File di folder FAILED: {failed_count} (Harus 8)")
    print(f"File tersisa di SOURCE: {source_count} (Harus 0)")
    
    assert processed_count == 2, f"Error: Processed count {processed_count} != 2"
    assert failed_count == 8, f"Error: Failed count {failed_count} != 8"
    assert source_count == 0, f"Error: Source count {source_count} != 0"
    
    print("\n✅ LOGIKA RECOVERY TERVERIFIKASI BERHASIL!")

if __name__ == "__main__":
    test_recovery_logic()
