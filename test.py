import argparse
import struct
import numpy as np
from PIL import Image
from pathlib import Path


def write_psd(layers_data, width, height, output_path):
    """手动写入PSD文件，避免pytoshop的packbits问题"""
    f = open(output_path, "wb")

    # === File Header ===
    f.write(b"8BPS")           # signature
    f.write(struct.pack(">H", 1))  # version
    f.write(b"\x00" * 6)      # reserved
    f.write(struct.pack(">H", 4))  # channels (RGBA)
    f.write(struct.pack(">I", height))
    f.write(struct.pack(">I", width))
    f.write(struct.pack(">H", 8))  # depth 8bit
    f.write(struct.pack(">H", 3))  # color mode: RGB

    # === Color Mode Data ===
    f.write(struct.pack(">I", 0))

    # === Image Resources ===
    f.write(struct.pack(">I", 0))

    # === Layer and Mask Info ===
    layer_mask_start = f.tell()
    f.write(struct.pack(">I", 0))  # placeholder

    # -- Layer Info --
    layer_info_start = f.tell()
    f.write(struct.pack(">I", 0))  # placeholder

    num_layers = len(layers_data)
    f.write(struct.pack(">h", num_layers))

    # 每个图层的 channel data 先缓存
    channel_buffers = []

    for name, arr in layers_data:
        h, w = arr.shape[:2]
        top, left, bottom, right = 0, 0, h, w

        f.write(struct.pack(">i", top))
        f.write(struct.pack(">i", left))
        f.write(struct.pack(">i", bottom))
        f.write(struct.pack(">i", right))

        num_ch = 4  # R G B A
        f.write(struct.pack(">H", num_ch))

        # channel info: id + data length
        ch_map = [(-1, arr[:, :, 3]), (0, arr[:, :, 0]),
                  (1, arr[:, :, 1]), (2, arr[:, :, 2])]
        layer_ch_data = []
        for ch_id, ch_arr in ch_map:
            raw = ch_arr.tobytes()
            data_len = 2 + len(raw)  # 2 bytes compression + raw data
            f.write(struct.pack(">h", ch_id))
            f.write(struct.pack(">I", data_len))
            layer_ch_data.append(raw)
        channel_buffers.append(layer_ch_data)

        # blend mode signature
        f.write(b"8BIM")
        f.write(b"norm")  # blend mode
        f.write(struct.pack(">B", 255))  # opacity
        f.write(struct.pack(">B", 0))    # clipping
        f.write(struct.pack(">B", 0x08)) # flags: transparency protected=no
        f.write(struct.pack(">B", 0))    # filler

        # extra data
        extra_start = f.tell()
        f.write(struct.pack(">I", 0))  # placeholder

        # layer mask data
        f.write(struct.pack(">I", 0))
        # blending ranges
        f.write(struct.pack(">I", 0))

        # layer name (Pascal string, padded to 4 bytes)
        name_bytes = name.encode("utf-8")[:255]
        name_len = len(name_bytes)
        f.write(struct.pack(">B", name_len))
        f.write(name_bytes)
        # pad to multiple of 4
        total = 1 + name_len
        pad = (4 - total % 4) % 4
        f.write(b"\x00" * pad)

        extra_end = f.tell()
        extra_size = extra_end - extra_start - 4
        f.seek(extra_start)
        f.write(struct.pack(">I", extra_size))
        f.seek(extra_end)

    # Channel image data for each layer
    for layer_ch_data in channel_buffers:
        for raw in layer_ch_data:
            f.write(struct.pack(">H", 0))  # compression = raw
            f.write(raw)

    layer_info_end = f.tell()
    layer_info_size = layer_info_end - layer_info_start - 4
    # pad to even
    if layer_info_size % 2 != 0:
        f.write(b"\x00")
        layer_info_end += 1
        layer_info_size += 1
    f.seek(layer_info_start)
    f.write(struct.pack(">I", layer_info_size))
    f.seek(layer_info_end)

    layer_mask_end = f.tell()
    layer_mask_size = layer_mask_end - layer_mask_start - 4
    f.seek(layer_mask_start)
    f.write(struct.pack(">I", layer_mask_size))
    f.seek(layer_mask_end)

    # === Merged Image Data (required) ===
    f.write(struct.pack(">H", 0))  # compression = raw
    # 写入合并后的 RGBA 数据（用第一张图或空白）
    merged = np.zeros((height, width, 4), dtype=np.uint8)
    if layers_data:
        _, first = layers_data[-1]  # 最上层
        h, w = first.shape[:2]
        merged[:h, :w] = first
    for ch in range(4):
        f.write(merged[:, :, ch].tobytes())

    f.close()


def main():
    parser = argparse.ArgumentParser(description="多张PNG合成PSD")
    parser.add_argument("images", nargs="+", help="PNG图片路径")
    parser.add_argument("-o", "--output", default="output.psd", help="输出路径")
    args = parser.parse_args()

    layers_data = []
    max_w, max_h = 0, 0

    for img_path in args.images:
        name = Path(img_path).stem
        print(f"添加图层: {name}")
        img = Image.open(img_path).convert("RGBA")
        arr = np.array(img)
        layers_data.append((name, arr))
        max_w = max(max_w, img.width)
        max_h = max(max_h, img.height)

    write_psd(layers_data, max_w, max_h, args.output)
    print(f"完成! {args.output} ({len(layers_data)} 个图层, {max_w}x{max_h})")


if __name__ == "__main__":
    main()
