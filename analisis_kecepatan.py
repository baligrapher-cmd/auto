
import os
import sys
import time

print("🔍 ANALISIS PERBANDINGAN: AutoYu vs FotoYu")
print("-"*60)

# Simulasi parameter
ORIGINAL_SIZE = 8.5  # MB (file besar dari kamera)
OPTIMIZED_SIZE = 1.5  # MB (setelah kompres AutoYu)
SPEED_MBPS = 2.5  # Kecepatan upload rata-rata

print(f"\n📦 File: {ORIGINAL_SIZE} MB")

# Simulasi AutoYu
autoyu_compress_time = 1.2  # detik
autoyu_upload_time = OPTIMIZED_SIZE / (SPEED_MBPS / 8)  # konversi Mbps ke MB/dtk
autoyu_total = autoyu_compress_time + autoyu_upload_time

# Simulasi FotoYu
fotoyu_upload_time = ORIGINAL_SIZE / (SPEED_MBPS / 8)
fotoyu_compress_time = 3.5  # detik (kompres di browser)
fotoyu_total = fotoyu_upload_time + fotoyu_compress_time

print("\n✅ AutoYu:")
print(f"   Kompres lokal: {autoyu_compress_time:.1f} detik")
print(f"   Upload: {autoyu_upload_time:.1f} detik ({OPTIMIZED_SIZE} MB)")
print(f"   TOTAL: 🏆 {autoyu_total:.1f} detik")

print("\n❌ FotoYu Langsung:")
print(f"   Upload: {fotoyu_upload_time:.1f} detik ({ORIGINAL_SIZE} MB)")
print(f"   Kompres di browser: {fotoyu_compress_time:.1f} detik")
print(f"   TOTAL: {fotoyu_total:.1f} detik")

print("\n" + "="*60)
selisih = fotoyu_total - autoyu_total
persen = (selisih / fotoyu_total) * 100
print(f"✅ AutoYu {persen:.0f}% LEBIH CEPAT!")
print(f"   Hemat waktu: {selisih:.1f} detik per file")
print("="*60)
