"""Create ICO with all sizes using proper method"""
from PIL import Image
import struct
import io

input_png = r"F:\project\authen\deloy docker\nhso_right_close_kiosk\logo\Worker ID Card.png"
output_ico = r"F:\project\authen\deloy docker\nhso_right_close_kiosk\logo\nhso_kiosk.ico"

# Open and prepare images
img = Image.open(input_png).convert('RGBA')
sizes = [16, 32, 48, 256]
images = []

for size in sizes:
    resized = img.resize((size, size), Image.Resampling.LANCZOS)
    images.append(resized)

# Create ICO file manually
ico_data = io.BytesIO()

# ICO header (6 bytes)
ico_data.write(struct.pack('<HHH', 0, 1, len(images)))  # Reserved, Type (1=ICO), Count

# Calculate offsets
offset = 6 + (16 * len(images))  # Header + directory entries

# Directory entries and image data
entries = []
image_datas = []

for i, img_resized in enumerate(images):
    # Save image to PNG in memory
    img_buffer = io.BytesIO()
    img_resized.save(img_buffer, format='PNG')
    png_data = img_buffer.getvalue()
    
    width = img_resized.width if img_resized.width < 256 else 0
    height = img_resized.height if img_resized.height < 256 else 0
    
    # Directory entry (16 bytes)
    entry = struct.pack('<BBBBHHII',
        width,           # Width (0 = 256)
        height,          # Height (0 = 256)
        0,               # Color palette
        0,               # Reserved
        1,               # Color planes
        32,              # Bits per pixel
        len(png_data),   # Size of image data
        offset           # Offset to image data
    )
    entries.append(entry)
    image_datas.append(png_data)
    offset += len(png_data)

# Write directory entries
for entry in entries:
    ico_data.write(entry)

# Write image data
for data in image_datas:
    ico_data.write(data)

# Save to file
with open(output_ico, 'wb') as f:
    f.write(ico_data.getvalue())

print(f"Created: {output_ico}")
print(f"File size: {len(ico_data.getvalue())} bytes")
print(f"Contains {len(images)} sizes: {[f'{s}x{s}' for s in sizes]}")

# Verify
verify_img = Image.open(output_ico)
print(f"Verification - Sizes: {verify_img.info.get('sizes', 'None')}")
