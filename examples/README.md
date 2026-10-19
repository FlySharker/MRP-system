# 合成演示数据 / Synthetic demo data

[sample_mrp.xlsx](sample_mrp.xlsx) 可直接通过概览页「导入数据」选择，再点击「分析」上传。文件包含 195 条记录、3 个物料、1 个虚构工厂和 32 周历史；所有数值与标识均由脚本生成，不来自真实企业。

| 物料 | 场景 |
| --- | --- |
| `DEMO-STABLE` | 充足初始库存，每周供给与需求匹配 |
| `DEMO-SHORTAGE` | 每周供给不足，库存逐步下降 |
| `DEMO-SPIKE` | 第 13、14 周需求突增，第 19 周追加供给 |

在项目根目录重建工作簿：

```powershell
python examples/generate_sample.py
```

只依赖 `openpyxl`，已列入根目录 `requirements.txt`。脚本会覆盖同目录的演示文件。MRP 数据位于第一个工作表，每个物料从 `Stock` 事件开始，`Order` 为负数需求，`PurRqs` 为正数供给。

建议先关闭单例分析的 LLM 开关。演示数据用于功能展示及流程验证，不是预测精度基准，不应据此推断实际业务收益或准确率。

The workbook contains only synthetic data: 195 records, three fictional materials, one fictional plant, and 32 weeks of history. Regenerate it with the command above. Import the first worksheet through the dashboard and disable LLM analysis for a credential-free walkthrough. These scenarios demonstrate application behavior; they are not a forecasting benchmark.
