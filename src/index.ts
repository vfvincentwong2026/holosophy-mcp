import { Hono } from 'hono';
import { cors } from 'hono/cors';

type Bindings = {
  DB: D1Database;
};

const app = new Hono<{ Bindings: Bindings }>();

app.use('/*', cors());

// 健康检查
app.get('/health', async (c) => {
  return c.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// 添加知识条目（使用 concepts 表）
app.post('/api/knowledge/add', async (c) => {
  try {
    const body = await c.req.json();
    const { name, chinese_name, category, summary, content, tags, links } = body;

    if (!content && !summary) {
      return c.json({ success: false, error: '内容或摘要不能为空' }, 400);
    }

    const db = c.env.DB;
    if (!db) {
      return c.json({ success: false, error: '数据库未连接' }, 500);
    }

    // 使用 concepts 表，包含所有字段
    await db.prepare(
      `INSERT INTO concepts (name, chinese_name, category, summary, content, tags, links, created_at, updated_at) 
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
    ).bind(
      name || content?.substring(0, 20) || '未命名',
      chinese_name || '',
      category || '未分类',
      summary || content?.substring(0, 100) || '',
      content || '',
      tags || '',
      links || '',
      new Date().toISOString(),
      new Date().toISOString()
    ).run();

    return c.json({ success: true, message: '知识条目添加成功' });
  } catch (error) {
    return c.json({
      success: false,
      error: error instanceof Error ? error.message : '添加失败'
    }, 500);
  }
});

// 搜索知识库（使用 concepts 表）
app.get('/api/knowledge/search', async (c) => {
  try {
    const query = c.req.query('q') || '';
    const limit = parseInt(c.req.query('limit') || '10');

    const db = c.env.DB;
    if (!db) {
      return c.json({ success: false, error: '数据库未连接' }, 500);
    }

    // 搜索 name, chinese_name, content, summary, tags
    const result = await db.prepare(
      `SELECT * FROM concepts 
       WHERE name LIKE ? OR chinese_name LIKE ? OR content LIKE ? OR summary LIKE ? OR tags LIKE ?
       ORDER BY created_at DESC LIMIT ?`
    ).bind(`%${query}%`, `%${query}%`, `%${query}%`, `%${query}%`, `%${query}%`, limit).all();

    return c.json({
      success: true,
      data: result.results || [],
      total: result.results?.length || 0
    });
  } catch (error) {
    return c.json({
      success: false,
      error: error instanceof Error ? error.message : '查询失败'
    }, 500);
  }
});

// MCP 端点（使用 concepts 表）
app.post('/mcp', async (c) => {
  try {
    const body = await c.req.json();
    const { messages, stream = false } = body;

    const db = c.env.DB;
    if (!db) {
      return c.json({ success: false, error: '数据库未连接' }, 500);
    }

    const query = messages?.[messages.length - 1]?.content || '';
    let dbResult: any[] = [];

    if (query) {
      const result = await db.prepare(
        `SELECT * FROM concepts 
         WHERE name LIKE ? OR chinese_name LIKE ? OR content LIKE ? OR summary LIKE ? OR tags LIKE ?
         ORDER BY created_at DESC LIMIT 10`
      ).bind(`%${query}%`, `%${query}%`, `%${query}%`, `%${query}%`, `%${query}%`).all();
      dbResult = result.results || [];
    }

    return c.json({
      success: true,
      data: {
        response: `处理了 ${messages?.length || 0} 条消息，查询到 ${dbResult.length} 条相关记录`,
        dbResults: dbResult,
        timestamp: new Date().toISOString()
      }
    });
  } catch (error) {
    return c.json({
      success: false,
      error: error instanceof Error ? error.message : 'MCP 处理失败'
    }, 500);
  }
});

export default app;