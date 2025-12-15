import os
from pathlib import Path
from paddleocr import PaddleOCRVL


pipeline = PaddleOCRVL()

input_dir = Path("posters").resolve()      
output_base = Path("output").resolve()    


output_base.mkdir(exist_ok=True)


image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

image_files = [
    p for p in input_dir.iterdir()
    if p.suffix.lower() in image_extensions
]

for img_path in image_files:
    print(f"\nProcessing: {img_path.name}")
    

    poster_output_dir = output_base / img_path.stem
    poster_output_dir.mkdir(exist_ok=True)

    original_cwd = os.getcwd()
    try:

        os.chdir(poster_output_dir)

 
        output = pipeline.predict(str(img_path)) 
        for res in output:
            res.save_to_json(save_path="result.json")
            res.save_to_markdown(save_path="result.md")


        print(f"✅ Done: {img_path.name}")

    except Exception as e:
        print(f"❌ Error processing {img_path.name}: {e}")

    finally:
        os.chdir(original_cwd)
