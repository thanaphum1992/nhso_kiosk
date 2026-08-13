"""Create proper ICO file with multiple sizes"""
from PIL import Image
import io

input_png = r"F:\project\authen\deloy docker\nhso_right_close_kiosk\logo\Worker ID Card.png"
output_ico = r"F:\project\authen\deloy docker\nhso_right_close_kiosk\logo\nhso_kiosk.ico"

# Open the PNG
img = Image.open(input_png).convert('RGBA')
print(f"Original size: {img.size}")

# Create multiple sizes
sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
img_dict = {}

for size in sizes:
    resized = img.resize(size, Image.Resampling.LANCZOS)
    img_dict[size] = resized
    print(f"Created {size}")

# Save as ICO using the correct method
# The first image's save() method with 'sizes' parameter
img_dict[(16, 16)].save(
    output_ico,
    format='ICO',
    sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
    append_images=[img_dict[(32, 32)], img_dict[(48, 48)], img_dict[(256, 256)]]
)

print(f"\nCreated: {output_ico}")

# Verify
verify_img = Image.open(output_ico)
print(f"Verification - Sizes in ICO: {verify_img.info.get('sizes', 'None')}")
