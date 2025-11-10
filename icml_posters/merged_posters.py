import json
from pathlib import Path

def merge_poster_jsons(icml_json="posters.json", iclr_json="iclr_posters.json", poster_folder="posters", output_json="merged_posters.json"):
    posters = []

    # 定义输入文件与对应会议名称
    files = [
        ("ICML2025", icml_json),
        ("ICLR2025", iclr_json),
    ]

    for conf_name, json_file in files:
        json_path = Path(json_file)
        if not json_path.exists():
            print(f"⚠️ 文件不存在：{json_path}")
            continue

        print(f"📖 正在读取 {conf_name} 文件：{json_path}")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ 无法解析 JSON 文件 {json_file}: {e}")
            continue

        # 标准化每条记录
        for item in data:
            poster_file = item.get("poster_file")
            if not poster_file:
                print(f"⚠️ 跳过无 poster_file 的记录：{item.get('title', '无标题')}")
                continue

            poster_id = f"{conf_name.split('20')[0]}_{Path(poster_file).stem}"

            posters.append({
                "poster_id": poster_id,
                "conference": conf_name,
                "title": item.get("title"),
                "authors": item.get("authors"),
                "source_url": item.get("poster_url"),
                "page_url": item.get("page_url"),
                "local_png_path": str(Path(poster_folder) / poster_file),
            })

    # 输出结果
    print(f"\n✅ 成功合并 {len(posters)} 条记录。")

    output_path = Path(output_json)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(posters, f, indent=2, ensure_ascii=False)

    print(f"💾 已保存合并文件：{output_path.resolve()}")
    return posters


if __name__ == "__main__":
    merged = merge_poster_jsons()
    if merged:
        print("\n示例数据：")
        print(json.dumps(merged[0], indent=2, ensure_ascii=False))
