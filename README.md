# Holosophy-MCP · 全息玄学 MCP 服务

**将跨学科知识图谱转化为可计算的语义接口，为 AI Agent 赋予东方智慧。**

---

## 🌌 这是什么？

**Holosophy-MCP** 是 [HoloSophy](https://github.com/vfvincentwong2026/holosophy) 知识图谱的 **MCP（Model Context Protocol）服务端实现**。

它将 Obsidian 中沉淀的玄学 · 量子力学 · 天文学 · 历史地理四域知识，通过标准化的 API 对外提供服务，让任何 AI 应用都能以统一的语义协议调用这个知识库。

> 一句话：知识图谱 → 可计算接口 → AI 可调用

---

## 🔗 与 HoloSophy 的关系

| 项目 | 角色 | 说明 |
|------|------|------|
| [holosophy](https://github.com/vfvincentwong2026/holosophy) | 知识层 | Obsidian 知识图谱，人类可读的跨学科知识 |
| **holosophy-mcp** | **接口层** | 将知识转化为 API，机器可读、AI 可调用 |
| [EAHub](https://github.com/vfvincentwong2026/eahub) | 展示层 | 知识图谱的可视化前端界面 |

**三者构成完整闭环：知识沉淀 → API 服务 → 交互呈现**

---

## 🧠 核心能力

| 能力 | 说明 |
|------|------|
| **语义检索** | 基于自然语言的跨域知识搜索 |
| **关联查询** | 自动发现概念之间的隐性关联 |
| **Agent 就绪** | 标准 MCP 协议，可直接接入 Claude Desktop 等 Agent 工具 |
| **Cloudflare 原生** | 基于 Workers + D1，全球节点毫秒级响应 |

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/vfvincentwong2026/holosophy-mcp.git
cd holosophy-mcp
