import io
import logging
import struct
from typing import List, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def write_psd(layers_data: List[Tuple[str, np.ndarray]], width: int, height: int, output_path: str):
    """
    手动写入 PSD 文件，避免 pytoshop 的 packbits 问题

    Args:
        layers_data: [(layer_name, rgba_array), ...]
        width: 画布宽度
        height: 画布高度
        output_path: 输出文件路径
    """
    with open(output_path, "wb") as f:
        _write_psd_to_file(f, layers_data, width, height)
    logger.info(f"PSD 生成成功: {output_path}, {len(layers_data)} 个图层")


def build_psd_to_bytes(layer_images: List[Tuple[str, bytes]], max_width: int, max_height: int) -> bytes:
    """
    将分层 PNG 合成为 PSD，返回字节流

    Args:
        layer_images: [(name, png_bytes), ...]
        max_width: 画布宽度
        max_height: 画布高度

    Returns:
        PSD 文件字节流
    """
    layers_data = []
    for name, png_bytes in layer_images:
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        arr = np.array(img)
        layers_data.append((name, arr))

    buffer = io.BytesIO()
    _write_psd_to_file(buffer, layers_data, max_width, max_height)
    buffer.seek(0)
    logger.info(f"PSD 合成完成: {len(layers_data)} 个图层, {max_width}x{max_height}")
    return buffer.read()


def _write_psd_to_file(f, layers_data, width, height):
    """内部实现：写入 PSD 二进制格式"""
    # === File Header ===
    f.write(b"8BPS")  # signature
    f.write(struct.pack(">H", 1))  # version
    f.write(b"\x00" * 6)  # reserved
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
        ch_map = [(-1, arr[:, :, 3]), (0, arr[:, :, 0]), (1, arr[:, :, 1]), (2, arr[:, :, 2])]
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
        f.write(struct.pack(">B", 0))  # clipping
        f.write(struct.pack(">B", 0x08))  # flags: transparency protected=no
        f.write(struct.pack(">B", 0))  # filler

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
    # 写入合并后的 RGBA 数据（用最上层）
    merged = np.zeros((height, width, 4), dtype=np.uint8)
    if layers_data:
        _, first = layers_data[-1]  # 最上层
        h, w = first.shape[:2]
        merged[:h, :w] = first
    for ch in range(4):
        f.write(merged[:, :, ch].tobytes())
