# 7x46 完整素材

架空 7×46mm 中间威力步枪弹，按 tacz_default_gun 的规范做全套素材。

## 成品

- `dist/7x46_GunPack_1.0.0.zip` —— 直接丢进 `.minecraft/tacz/`（16 个文件）
- `dist/7x46_gunpack/` —— 解包后的同一棵树
- `7x46_pack_preview.png` —— 图标 + 模型 + 抛壳一览

## 重新生成

```
python gen4.py        # 物品图标 -> 7x46*.png
python atlas.py       # UV 图集 -> pack/7x46_uv.png
python maps.py        # _n / _s -> pack/
python build_geo.py   # 弹箱模型 -> pack/geo_models/ammo/
python build_shell.py # 抛壳模型+贴图 -> pack/
python assemble.py    # 拼 dist 树 + 打 zip
python verify_pack.py # 资源路径 / json / lang / recipe 校验
python verify_zip.py  # 解压回读校验
```

## 设计说明

见 `7x46_设计说明.md`。
