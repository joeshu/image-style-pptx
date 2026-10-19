# 统一风格的矢量图标

## 默认选择

通用业务图标默认使用随包的 Lucide 线性 SVG，不再从低分辨率截图裁取。`assets/icons/catalog.json` 记录图标名称、中文语义、来源版本和 SHA-256；许可证为 `assets/LUCIDE-LICENSE.txt`。图标是语义对应的替代素材，不宣称与原图轮廓完全一致。

保留品牌、官方标识和用户明确要求原样保留的专有图标。用户要求逐像素复制时，按其要求保留原图并说明清晰度限制。照片、三维插图和证据截图不当作普通图标替换。

## 视觉规范

- 统一使用24×24的 SVG viewBox、2px描边、圆形线端、圆形连接、无填充的线性风格。
- 默认主题蓝 `#0B5BD3`。按参考图主题统一换色，允许蓝底白色或红底白色的反白图标。同一组使用同一颜色，不混搭彩色贴图、实心图标、emoji和不同线宽。
- 同一业务行使用同样的正方形槽位，建议32×32或40×40 CSS px，统一水平中心及垂直基线。栏目和正文可以使用不同尺寸组。
- 图标与标题留出至少8px，组合符号与相邻项目保持间距，避免“＋”贴到标题或卡片边缘。
- 颜色在 spec 中设置，不手工改动库文件；脚本保留轮廓和统一线宽。不拉伸为非正方形，不先转成 PNG 再插入。

## 常用语义映射

| 内容 | 图标键 |
| --- | --- |
| 营销成果 / 重点做法 / 经典案例 | `trophy` / `target` / `star` |
| 营销总结 | `clipboard-list` |
| 用户信息 / 用户痛点 / 核心话术 | `user-round` / `frown` / `message-circle-more` |
| 副卡 / 流量与通话 | `card-sim` / `phone-call` |
| 宽带提速 / 设备升级 | `gauge` / `router` |
| 安装费用 / 服务支持 | `receipt-text` / `headset` |

完整30枚图标见[图标预览](../assets/icons/preview.svg)及 `catalog.json`。没有匹配项时先找同一来源、同一线性风格的图标；不要为了“统一”把路由器、SIM卡、通话等业务含义换错。

## 用法

```json
{
  "iconColor": "#0B5BD3",
  "slides": [{"elements": [
    {"type":"icon","name":"benefit-sim","icon":"card-sim","group":"benefits","x":80,"y":160,"w":40,"h":40},
    {"type":"icon","name":"benefit-speed","icon":"gauge","group":"benefits","x":240,"y":160,"w":40,"h":40}
  ]}]
}
```

颜色按“元素 `color` → 页 `iconColor` → 根 `iconColor` → 默认蓝”取值，限 `#RRGGBB`。同页相同 `group` 的尺寸和颜色必须一致。脚本验证图标键、槽位、颜色和源文件哈希，再嵌入独立 SVG。

完整可运行画布示例为 `examples/unified-icons.json`，其尺寸、文字和页面结构可直接用于回归渲染。

## 可编辑性与检查

SVG 是可移动、缩放和替换的独立矢量图片；逐路径编辑取决于 PowerPoint/WPS 的版本及“转换为形状”能力。用户明确需要逐条修改线条时，应另走并验证原生形状转换，不能把嵌入 SVG 宣称为已经转成原生形状。

导出后检查：每个 `type: icon` 对应的 PPTX 图片对象必须带 SVG 引用，不能只剩 PNG；存在兼容预览 PNG 是正常情况。随后从最终 PPTX 渲染，查看描边、颜色、尺寸、对齐及文字间距。SVG引用检查不证明所有软件的显示或路径编辑能力。
