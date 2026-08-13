"""Convert PNG to ICO with multiple sizes for Windows"""
from PIL import Image
import os

input_png = r"F:\project\authen\deloy docker\nhso_right_close_kiosk\logo\Worker ID Card.png"
output_ico = r"F:\project\authen\deloy docker\nhso_right_close_kiosk\logo\nhso_kiosk.ico"

# Open the PNG
img = Image.open(input_png)

# Convert to RGBA if not already
if img.mode != 'RGBA':
    img = img.convert('RGBA')

# Create multiple sizes for ICO (Windows standard sizes)
sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
imgs = []

for size in sizes:
    resized = img.resize(size, Image.Resampling.LANCZOS)
    imgs.append(resized)

# Save as ICO with all sizes
imgs[0].save(
    output_ico,
    format='ICO',
    sizes=sizes,
    append_images=imgs[1:]
)

print(f"Created: {output_ico}")
print(f"Sizes: {sizes}")
