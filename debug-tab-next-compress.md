# Debug Session: tab-next-compress
- **Status**: [OPEN]
- **Issue**: Tab berikutnya tidak langsung mulai kompres (terasa masih menunggu sampai tab sebelumnya klik Unggah / ada delay WAIT_QUEUE).
- **Debug Server**: http://127.0.0.1:<port>/event
- **Log File**: .dbg/trae-debug-log-tab-next-compress.ndjson

## Reproduction Steps
1. Jalankan AutoYu Pro/Lite.
2. Set Tabs >= 2, batch size kecil (mis. 5) agar mudah melihat perpindahan tab.
3. Mulai otomasi dan amati: setelah Tab 1 selesai kompres, Tab 2 terbuka tapi belum langsung masuk kompres (terasa “menunggu”).

## Hypotheses & Verification
| ID | Hypothesis | Likelihood | Effort | Evidence |
|----|------------|------------|--------|----------|
| A | `global_lock['injector']` tidak dilepas di semua jalur (branch `set_input_files`, branch video `expect_file_chooser`, atau exception path), sehingga tab baru stuck di `WAIT_QUEUE`. | High | Low | Pending |
| B | Tab baru memang dibuat cepat, tapi diblok oleh gating “open tab setelah kompres” + lock injector, sehingga tidak ada overlap dan terasa lambat. | Med | Low | Pending |
| C | Tab baru sudah mulai `SELECT_MODE`, tapi deteksi trigger/input file lambat (selector berubah / modal mengganggu), sehingga terlihat seperti “menunggu”. | Med | Med | Pending |
| D | Tab baru tidak benar-benar melakukan `goto /upload` / load state lambat, sehingga `OPEN_UPLOAD_PAGE` lama sebelum masuk `WAIT_QUEUE/SELECT_MODE`. | Low | Med | Pending |

## Log Evidence
- (akan diisi setelah instrumentasi dan reproduksi)

## Verification Conclusion
- (akan diisi setelah pre-fix vs post-fix)
