# 版式 JSON

坐标、尺寸、字号均为 CSS 像素（96 DPI），与输入图片使用同一坐标系。根对象：

```json
{
  "width": 1280,
  "height": 626,
  "fontFamily": "Noto Sans CJK SC",
  "slides": [{
    "background": "#FFF3DF",
    "notes": "来源：用户提供的参考图。",
    "elements": [
      {"type":"shape","name":"header","x":0,"y":0,"w":1280,"h":70,"fill":"#A90000"},
      {"type":"text","name":"title","x":60,"y":14,"w":1100,"h":46,"text":"标题","fontSize":36,"bold":true,"color":"#FFFFFF"}
    ]
  }]
}
```

所有元素必须有唯一 `name`、有限的 `x/y/w/h`，且在画布内。元素按数组顺序叠放。

## 文字 `type: text`

使用 `text` 字符串，或 `runs` 数组，例如 `[{"text":"结果："},{"text":"90分","color":"#E01512","bold":true,"fontSize":24}]`。可用 `fontSize`、`fontFamily`、`bold`、`color`、`align`（left/center/right）、`valign`（top/middle/bottom）、`insets`、`wrap`（square/none）。默认不缩小字号、不自动改变形状大小。需要显式换行时写 `\n`，或拆为独立元素。换行段落不设虚构的列表语义。

也可使用 `paragraphs`，每段为字符串或 `{"text":"..."}` / `{"runs":[...]}`。同一元素只能选择 `text`、`runs`、`paragraphs` 中一种，不能同时提供。每段支持以磅为单位的 `spaceBeforePt` / `spaceAfterPt`，默认0。`lineSpacing` 是行距倍数（如1.0），不是像素行高。

## 形状 `type: shape`

使用 `geometry`（默认 rect，可为 roundRect/ellipse/line）、`fill`、`stroke`、`strokeWidth` 和 `radius`。渐变可使用 Artifact Tool 的 `linear(...)` 字符串。形状仅用于参考图的容器、边框和基本几何，不用它代替需要图片素材的插图。

## 图片 `type: image`

使用 `path`（相对 spec 所在目录或绝对路径）、`alt` 和 `fit`（contain/cover）。支持 SVG、PNG、JPEG。图标应是独立元素，保留许可证。禁止把整页截图冒充可编辑重建。

## 统一矢量图标 `type: icon`

使用 `icon` 指定 `assets/icons/catalog.json` 中的键，提供 `name/x/y/w/h`，宽高必须相等。`color` 为可选 `#RRGGBB`；颜色回退到页/根 `iconColor` 和默认蓝。`group` 指定同页尺寸及颜色必须一致的业务组。不要提供 `path`、`svg`、`fill`、`stroke` 或 `strokeWidth`，避免绕过统一规范。

例如：`{"type":"icon","name":"speed","icon":"gauge","group":"benefits","x":240,"y":160,"w":40,"h":40}`。图标由随包 SVG 直接嵌入，保持比例；检查器区分 `vectorIcons` 与 `rasterScope`，并核对输出图片对象是否包含 SVG 引用。详见 [图标规范](icon-style.md)。

## 原生表格 `type: table`

使用 `values` 二维数组、`columnWidths` 和 `rowHeights`。列宽之和为 `w`，行高之和为 `h`。每格可以是字符串或 `{"runs":[...],"bold":true,"color":"#...","fontSize":14,"fill":"#..."}`。表格级别可以设置 `fontSize`、`color`、`fill`、`stroke`、`strokeWidth`、`align`。`rowFills` 可按行设置填色。每个单元格保留原生文本，可在 PowerPoint 中编辑。

表格的 `cellMargins` 可设置 `left/right/top/bottom`（像素），默认左右2px、上下0px。紧凑表格应明确内边距，防止应用默认内边距导致行高或换行改变。脚本为每个单元格四边设置边框，避免相邻单元格从默认表格样式继承不同颜色。

每个单元格可以使用 `paragraphs`，保留跨多段的红色/粗体文字。每格还可独立设置 `valign`、`wrap`、`lineSpacing` 和 `cellMargins`，不强制统一垂直居中。

脚本只验证结构和边界。最终仍须渲染检查文字的实际占用、字体替换和表格显示。不能把坐标边界检查当成文字不溢出的证明。

## 来源文字与截图范围

每页可增加 `sourceText` 和 `requiredTokens`，这些内容不出现在页面上，用于导出后核对：

```json
{
  "sourceText": [{"id":"summary","text":"已经对照原图确认的完整段落","confidence":"high"}],
  "requiredTokens": ["0.253%"],
  "elements": [{"type":"image","name":"evidence-01","sourceRole":"evidence-screenshot","x":60,"y":330,"w":350,"h":90,"path":"assets/evidence.png"}]
}
```

`sourceText` 必须先经过实际源图核对，不能只是用版式 spec 复制一份当作独立证据。检查器忽略空白差异，保留标点与数字差异。保留为图片的截图不会被宣称成原生文字。

## 对应关系和强调样式

页级 `nativeTextContracts` 可用对象 `name` 精确核对文字，或使用 `table`（从1起）、`row`/`column`（从0起）定位单元格。`text` 为全文匹配，`contains` 为包含匹配。

```json
{
  "nativeTextContracts": [{"name":"new-count","text":"171户"}],
  "formatContracts": [{"table":1,"row":2,"column":1,"text":"流量有150G","color":"#C52C36","bold":true}],
  "uncertainties": [{"location":"旧套餐版本名","text":"暂录文字","reason":"原图模糊","handling":"在备注列为待核"}]
}
```

样式检查支持原生文字中显式写出的 RGB 和粗体，可跨多个 run 检查同一短语。主题色尚未解析时不把未知样式当作通过。检查器列出 `uncertainties` 为来源待核提示，不把它们伪装成已核实内容。
