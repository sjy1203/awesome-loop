# Contributing

English · [简体中文](#参与贡献)

Suggestions and corrections are welcome through issues and pull requests.

- **Suggest a paper**: open an issue with the arXiv link and one sentence on how it uses looping.
- **Fix an error**: open an issue or a pull request that points to the table, figure or section in the paper.
- **Add an entry**: edit or add a YAML file under `papers/`, `models/` or `claims/`, run
  `python3 scripts/build.py` (needs `pip install pyyaml jsonschema`), and commit the YAML together with the
  regenerated files. CI checks that they match.

The full rules are in [AGENTS.md](AGENTS.md). The most important ones:

- Only public sources. Numbers are copied exactly as printed, each with a table, figure or section reference;
  nothing is computed or converted.
- Caveats describe limitations visible in the paper, not opinions.
- Deep cards are for language models; other domains are welcome as radar entries.
- Each card has English and Chinese text with the same content.

## 参与贡献

欢迎通过 issue 和 pull request 提建议或纠错。

- **推荐论文**：开 issue，附 arXiv 链接，用一句话说明它怎么用循环。
- **纠错**：开 issue 或 PR，指出原文的表格、图或章节。
- **新增条目**：在 `papers/`、`models/` 或 `claims/` 下新增或修改 YAML，运行 `python3 scripts/build.py`
  （需要 `pip install pyyaml jsonschema`），把 YAML 和重新生成的文件一起提交。CI 会检查两者是否一致。

完整规则见 [AGENTS.md](AGENTS.md)。最重要的几条：

- 只用公开来源。数字按原文照抄，注明表格、图或章节，不做任何计算或换算。
- 保留意见只写原文里看得到的局限，不写个人观点。
- 精读卡只收语言模型，其他领域欢迎作为 radar 条目收录。
- 每张卡都有内容一致的中英文。
