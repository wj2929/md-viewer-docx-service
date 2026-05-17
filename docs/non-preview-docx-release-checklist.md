# 非 Preview DOCX 发布验收清单

适用范围：`standard`、`official`、`internal`、`report` 四种非 `preview` DOCX 样式。

## 自动化门禁

发布前至少执行：

```bash
PYTHONPATH=. pytest tests/test_non_preview_style_contracts.py -q
PYTHONPATH=. pytest -q
```

重点确认：

- `tests/fixtures/non_preview_styles/` 中所有样例均能生成 DOCX。
- `official/internal/report` 默认不出现“由 MD Viewer 生成”。
- 表格首行包含 `w:tblHeader`，支持跨页重复表头。
- H5/H6、基础嵌套列表、表格内图片占位符和字体 warning 有回归测试。
- 如果本机安装 LibreOffice 与 `pdfinfo`，`official-document.md` 应能转换为 A4 PDF。

## 人工抽检

每次 release 至少抽检：

- Word：打开 `official-document.md`、`wide-table.md`、`report-with-charts.md` 导出的 DOCX。
- WPS：打开同一组文件，核对字体替换、分页、表格跨页和图片尺寸。
- LibreOffice：确认文件可打开并可另存为 PDF。

## 不可接受结果

- DOCX 无法打开或 Word/WPS 提示文件损坏。
- 正式样式默认出现“由 MD Viewer 生成”。
- H5 在 `official` 中退化为普通正文。
- 嵌套有序列表子级不从 1 开始，或父级编号不能恢复。
- 表格表头跨页不重复。
- 字体缺失但导出结果没有 warning。

## 发布说明约束

发布说明中只能称为“DOCX 正文样式预设”，不能称为完整公文模板、完整内部文件模板或完整报告模板。字体受系统与授权影响，正式提交前仍需在 Word/WPS 中人工核对。
