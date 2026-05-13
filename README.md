# 超材料分析工具

这个仓库用于托管静态网页工具，可以直接部署到 GitHub Pages。

## 页面

- `index.html`：工具首页。
- `curve_inspector_raw_diff_fixed_click.html`：曲线检查器。网页读取 `X/Y CSV` 和预先生成的 `curve_features.json`。
- `hole_geometry_stats.html`：孔几何统计。网页读取 `hole_data_abaqus_geom.csv` 后在浏览器内计算统计图表。

## 新增页面

1. 把新的 HTML 放到仓库根目录。
2. 在 `site-nav.js` 的 `SITE_PAGES` 数组里新增一项：

```js
{ href: "new_page.html", label: "新页面名称" }
```

3. 在新页面 `<head>` 引入：

```html
<link rel="stylesheet" href="site-nav.css">
```

4. 在 `</body>` 前引入：

```html
<script src="site-nav.js" data-current="new_page.html"></script>
```

## 曲线特征 JSON

GitHub Pages 不能执行 Python。曲线检查器使用的 `curve_features.json` 需要本地生成：

```bash
python3 curve_inspector_core.py success_case_results_merged.csv -o curve_features.json
```

然后在网页中上传该 JSON。
