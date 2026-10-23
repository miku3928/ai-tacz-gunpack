# TaCZ 第一人称定位调参器

调 TaCZ 枪械在第一人称里的位置，改完写回枪包，游戏里 `/tacz reload` 立刻生效。
不用开 Blockbench，不用重启游戏。

![界面](screenshot.png)

> **不想装 Python？** 去 [Releases](https://github.com/miku3928/ai-tacz-gunpack/releases) 下
> `TaCZ第一人称定位调参器_v1.0_免安装.zip`，解压双击 exe 即可。

## 它解决的是什么

TaCZ 里第一人称枪的位置**不是**玩家可调的配置项。它由模型骨骼组
`idle_view`（腰射）和 `iron_view`（机瞄）的 pivot 决定，藏在枪包的
`geo_models/gun/*_geo.json` 里。以前想改只能开 Blockbench、装 cameras 插件、
把 FOV 设成 70、对着屏幕猜，改一次重启一次游戏。

这个工具把那条路砍成：选枪 → 拖 → 写回 → reload。

## 为什么预览里看到的就是游戏里看到的

不是拟合出来的。矩阵是从 TaCZ 1.20.1-1.1.8 的源码逐行推出来的，并且用
"照抄字节码"的写法反向核对过，六把官方枪的最大误差 **1.9e-16**。

游戏的渲染链（`GunItemRendererWrapper.renderFirstPerson`）是：

    translate(0, 1.5, 0)          // 渲染原点 (0,24,0) 移到模型原点
    rotate Z 180°                 // 基岩模型上下颠倒
    applyFirstPersonPositioningTransform:
        translate(0, 1.5, 0)
        mulPose(M)                // M = getPositioningNodeInverse(idle_view 链)
        translate(0, -1.5, 0)

把这四步乘开，两个 1.5 和 root 骨骼那个 `1.5 - y/16` 的特判会整体抵消，
最后就是一个干净式子：

    P = Rz(180°) · inv(W)

W 是定位组骨骼的世界矩阵（沿 root→leaf 累乘 `T(pos/16)·Rz·Ry·Rx`）。
改 pivot 只改 P，所以预览是精确的，不是近似的。

顺带纠正一个流传很广的说法：枪的第一人称渲染**不经过**原版
`ItemInHandRenderer` 的手持位移。TaCZ 自己的 `FirstPersonRenderEvent`
里 `@SubscribeEvent` 被注释掉了，真正干活的是内嵌库 simplebedrockmodel 的
`FirstPersonRenderHandler`，它直接接管 RenderHandEvent 并 cancel 掉原版渲染。
所以从"原版会拉远、往下、往右"去推偏移，方向从一开始就错了。

## poly_mesh（TML 模型）也支持

Blender 直接导出的 poly_mesh 枪包要装 **TML（Tacz Mesh Loader）** 才能进游戏，
基础 TaCZ 只认 `cubes`。本工具对这两种模型一视同仁。

差别只在"顶点相对骨骼枢轴怎么烘"这一步，下游管线完全一样。TML 的
`PolyMesh` 构造器里写死了（字节码逐行核对）：

    bakedX = ( pos.x - pivot.x) / 16
    bakedY = -(pos.y - pivot.y) / 16      <- y 取反
    bakedZ = ( pos.z - pivot.z) / 16

然后交给 `BedrockPart.translateAndRotateAndScale`，和 cube 走同一条路。

**不要**把 poly_mesh 当成"模型绝对坐标直接乘视矩阵"——那样枪会缩到 1/1.55，
不同骨骼的网格还会互相错位。按正确规则烘出来叠到真实截图上，和游戏里的画面
严丝合缝；按绝对坐标烘就对不上。

## 用法

**给别人用**：下 Release 里的免安装 zip，解压双击 exe。

**自己跑源码**：需要 Python 3.8+ 和 Pillow。

```bash
pip install pillow
python gui.py
```

Windows 上也可以双击 `启动.vbs`（不弹黑框）。

1. 上面填游戏版本目录下的 `tacz` 文件夹
2. 左边选枪包、选枪（"腰""机"表示有腰射 / 机瞄定位组，"网格"表示 poly_mesh）
3. 调：
   - **左键拖预览** 直接平移，鼠标走多少像素枪就走多少像素
   - **方向键** 微调 0.25 单位，**Shift+方向键** 走 1 单位，PgUp/PgDn 调前后
   - 右侧滑块和输入框给精确值；旋转是度
   - **腰射 / 机瞄 两个标签页是两套独立参数**，必须分别调
4. `Ctrl+S` 写回，游戏里 `/tacz reload`
5. 不满意就 `Ctrl+Z` 回到打开时的值

写回前会自动在原文件旁边留一份 `.bak`。写回只改被编辑的那几个数字，
不动整个文件的缩进换行（进 git 之后 diff 还能看）。

### 对齐真实观感

点"垫游戏截图"，选一张你自己在游戏里截的图，它会被压暗垫在预览下面，
渲染结果半透明叠上去。透明度用旁边的滑杆调。

这是唯一能把预览和你眼睛看到的画面钉在一起的办法——尤其是你改了 FOV
或者用了非 16:9 的分辨率时。**游戏设置里的 FOV 记得填到右下角那个框里**，
默认 70 是 MC 的默认值。

## 几个必须知道的点

**1 模型单位 = 1/16 方块。** 和 Blockbench 里看到的数字完全一样。

| 改动 | 屏幕效果 |
| --- | --- |
| `pivot.x` 变大 | 枪往**右** |
| `pivot.y` 变大 | 枪往**下** |
| `pivot.z` 变大 | 枪往**近**（更贴脸，也更大） |

官方枪的腰射位置有个共同规律：x 偏右 0.02~0.46 方块，y 在视线下方
0.7~1.0 方块。偏离这个范围太多通常不是你想要的。

**腰射和机瞄是两套独立的定位组。** `idle_view` 管不开镜，`iron_view` 管
开镜（装了瞄具时还会接上瞄具模型的 `scope_view`）。调好一个不会影响另一个。

**"把枪整体缩小"这件事，1.20.1 的枪包做不到。** 文档里提过的 `model_fov`
在 1.20.1 源码里不存在；`zoom_model_fov` 只在瞄准进度大于 0 时生效
（`Mth.lerp(aimingProgress, ...)`），而且大于 70 会被硬夹回 70。
想要小一号的枪，只能改几何体本身。

## 文件

| 文件 | 干什么 |
| --- | --- |
| `core.py` | 坐标转换、骨骼链、视矩阵、几何收集、投影。每条规则都能指到 Java 行号 |
| `render.py` | 软件光栅预览（PIL，无第三方渲染依赖） |
| `pack.py` | 读枪包（目录 / zip / 单文件）、找枪、写回 |
| `gui.py` | 界面 |
| `selftest.py` | 不开窗口跑一遍，核对矩阵等式、灵敏度、写回往返、poly_mesh 烘焙 |
| `build_exe.py` | 打包（默认目录版；`--onefile` 出单文件版） |

改完代码跑一下：

```bash
python selftest.py                      # 用默认目录
python selftest.py "E:/.../tacz"        # 指定枪包目录
```

全绿再动界面。

## 性能

poly_mesh 那种十几万面的模型做了针对性处理：三角面用 numpy 批量解析、
退化三角直接丢弃、亮度查表、按屏幕面积丢细碎三角形。
rifle3（96803 三角面）1288×724 一帧 46ms，拖拽时半分辨率 24ms。

## 已知限制

- **预览没有贴图、没有光影、没有手臂。** 它回答的是"枪在屏幕的哪个位置、
  朝哪个方向"，不是"好不好看"。
- **动画不参与预览。** 预览画的是 `static_idle` 那一刻的静止姿态。
- **第三人称 / 地面 / 展示框的位置不在这里。** 那些走 display json 的
  `transform.scale` 和 `thirdperson_hand` / `ground` / `fixed` 定位组。
