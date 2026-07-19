-- 概念表
CREATE TABLE IF NOT EXISTS concepts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE,
  chinese_name TEXT,
  category TEXT,
  summary TEXT,
  content TEXT,
  tags TEXT,
  links TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 关系表（双链）
CREATE TABLE IF NOT EXISTS relationships (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT,
  target TEXT,
  relation_type TEXT DEFAULT '关联',
  FOREIGN KEY (source) REFERENCES concepts(name),
  FOREIGN KEY (target) REFERENCES concepts(name)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_concepts_name ON concepts(name);
CREATE INDEX IF NOT EXISTS idx_concepts_category ON concepts(category);
CREATE INDEX IF NOT EXISTS idx_concepts_tags ON concepts(tags);