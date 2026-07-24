# Wiki Schema（知识库配置）

> 此文件告诉 LLM 知识库的结构和操作约定。

## 目录结构

- `raw/`：原始来源，只读，永不修改
- `wiki/`：LLM 编译产物，由 LLM 完全拥有
- `wiki/index.md`：全局内容目录，每页一行摘要
- `wiki/log.md`：操作日志，append-only

## 摄取约定（Ingest）

1. 读取新来源，提取关键概念和实体
2. 在 `wiki/concepts/` 或 `wiki/entities/` 创建或更新对应 .md 文件
3. 使用 `[[wiki-links]]` 格式添加交叉引用
4. 更新 `wiki/index.md` 目录
5. 在每个 wiki 页面的 frontmatter 中记录来源文件

## Wiki 页面 Frontmatter 格式

```yaml
---
title: "页面标题"
confidence: 0.9
last_ingested: YYYY-MM-DD
sources:
  - raw/articles/example.md
stale: false
---
```

## 查询约定（Query）

1. 先读取 `wiki/index.md` 定位相关页面
2. 读取相关页面内容并综合答案
3. 优质答案归档回 wiki 作为新页面

## 整理约定（Lint）

- 检查页面间矛盾，在 frontmatter 标注 `stale: true`
- 补全孤立页面的入站链接
- 发现缺少独立页面的重要概念
