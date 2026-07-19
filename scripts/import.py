#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HoloSophy → Cloudflare D1 一键同步脚本

用法：
    python scripts/import.py              # 全量同步到线上 D1（覆盖式：清库重灌，幂等）
    python scripts/import.py --dry-run    # 只解析+统计+生成 SQL，不写库
    python scripts/import.py --vault "D:/path/to/vault"   # 指定知识库路径

知识库路径优先级：--vault 参数 > 环境变量 HOLOSOPHY_VAULT > 下方 DEFAULT_VAULT
分类规则：vault 根目录下凡含 .md 的子目录 = 一个分类（EXCLUDE_DIRS 除外），
新增目录即新增分类，无需改脚本。
依赖：仅 Python 3.8+ 标准库；需要可用的 wrangler（PATH / npx / 本仓库 node_modules）。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---- 可按环境修改的默认值 -------------------------------------------------
DEFAULT_VAULT = r"D:\桌面工作\AI project\玄学聚合\HoloSophy — 全息玄学知识图谱"
EXCLUDE_DIRS = {"copilot", ".obsidian", ".git", ".trash", ".github"}
BATCH_SIZE = 500  # 每个 SQL 文件的最大语句数（库变大后自动分批）
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_frontmatter(text):
    """解析 YAML frontmatter（仅支持 key: value 与 key: 列表），返回 (meta, body)。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}, text
    fm, body = {}, text[m.end():]
    cur_key = None
    for line in m.group(1).split("\n"):
        km = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if km:
            cur_key = km.group(1)
            val = km.group(2).strip()
            fm[cur_key] = val if val else []
        elif re.match(r"^\s+-\s+", line) and cur_key:
            if not isinstance(fm.get(cur_key), list):
                fm[cur_key] = [fm[cur_key]] if fm.get(cur_key) else []
            fm[cur_key].append(re.sub(r"^\s+-\s+", "", line).strip())
    return fm, body


def strip_md(s):
    """去掉 markdown 符号，生成纯文本摘要。"""
    s = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", s)  # [[链接|别名]] → 链接
    s = re.sub(r"[#>*`$\[\]]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def sqlq(s):
    return "'" + (s or "").replace("'", "''") + "'"


def collect_concepts(vault: Path):
    """扫描 vault，返回 (concepts, relationships, stats)。"""
    categories = sorted(
        d for d in vault.iterdir()
        if d.is_dir() and d.name not in EXCLUDE_DIRS and list(d.glob("*.md"))
    )
    if not categories:
        sys.exit(f"[X] 在 {vault} 下没有找到任何含 .md 的分类目录")

    concepts, skipped = [], []
    seen = set()
    per_cat = {}
    for cat_dir in categories:
        cat = cat_dir.name
        for f in sorted(cat_dir.glob("*.md")):
            raw = f.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(raw)
            title = str(fm.get("title") or re.sub(r"\.md$", "", f.stem)).strip()
            if not title:
                skipped.append(f"{cat}/{f.name} (无标题)")
                continue
            if title in seen:
                skipped.append(f"{cat}/{f.name} (重名: {title})")
                continue
            seen.add(title)
            tags = fm.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", body)
            sm = re.search(r">\s*\*\*摘要\*\*[：:]\s*(.+)", raw)
            if sm:
                summary = strip_md(sm.group(1))[:500]
            else:
                paras = [p for p in body.split("\n\n")
                         if p.strip() and not p.strip().startswith(("#", ">", "---"))]
                summary = strip_md(paras[0])[:500] if paras else ""
            concepts.append({
                "name": title, "chinese_name": title, "category": cat,
                "summary": summary, "content": raw.strip(),
                "tags": ",".join(tags), "links": ",".join(sorted(set(links))),
            })
            per_cat[cat] = per_cat.get(cat, 0) + 1

    names = {c["name"] for c in concepts}
    rels = set()
    for c in concepts:
        for lk in (c["links"].split(",") if c["links"] else []):
            lk = lk.strip()
            if lk and lk in names and lk != c["name"]:
                rels.add((c["name"], lk))
    return concepts, sorted(rels), {"per_cat": per_cat, "skipped": skipped}


def build_statements(concepts, rels):
    stmts = ["DELETE FROM relationships;", "DELETE FROM concepts;"]
    for c in concepts:
        stmts.append(
            "INSERT INTO concepts (name, chinese_name, category, summary, content, tags, links,"
            " created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,datetime('now'),datetime('now'));"
            % (sqlq(c["name"]), sqlq(c["chinese_name"]), sqlq(c["category"]),
               sqlq(c["summary"]), sqlq(c["content"]), sqlq(c["tags"]), sqlq(c["links"])))
    for s, t in rels:
        stmts.append("INSERT INTO relationships (source, target, relation_type)"
                     " VALUES (%s,%s,'关联');" % (sqlq(s), sqlq(t)))
    return stmts


def get_database_id():
    """从仓库 wrangler.jsonc 读取 D1 database_id。"""
    cfg = (REPO_ROOT / "wrangler.jsonc").read_text(encoding="utf-8")
    m = re.search(r'"database_id"\s*:\s*"([^"]+)"', cfg)
    if not m:
        sys.exit("[X] wrangler.jsonc 中找不到 database_id")
    return m.group(1)


def find_wrangler_cmd():
    """定位 wrangler。返回 (cmd_prefix, needs_shell)。
    优先用仓库 node_modules 里的 wrangler.js + node.exe（最确定）；
    其次 PATH 上的 wrangler / npx（Windows 上 .cmd 需走 shell）。"""
    local = REPO_ROOT / "node_modules" / "wrangler" / "bin" / "wrangler.js"
    if local.exists():
        candidates = [shutil.which("node"), os.environ.get("NODE_EXE"),
                      r"C:\Users\夏夜\AppData\Local\Programs\kimi-desktop\resources\resources\runtime\node.exe"]
        node = next((n for n in candidates
                     if n and n.lower().endswith(".exe") and Path(n).exists()), None)
        if node:
            return [node, str(local)], False
    if shutil.which("wrangler"):
        return ["wrangler"], True
    if shutil.which("npx"):
        return ["npx", "--yes", "wrangler"], True
    sys.exit("[X] 找不到 wrangler（仓库 node_modules / PATH / npx 均无；请先 npm install）")


def run_wrangler(cmd_prefix, needs_shell, args, label):
    env = dict(os.environ, CI="true")
    print(f"  → {label} ...")
    p = subprocess.run(cmd_prefix + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=600,
                       shell=(needs_shell and os.name == "nt"))
    if p.returncode != 0:
        print(p.stdout[-2000:])
        print(p.stderr[-2000:])
        sys.exit(f"[X] {label} 失败 (exit={p.returncode})")
    return p.stdout


def main():
    for stream in (sys.stdout, sys.stderr):  # Windows 控制台 UTF-8
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="HoloSophy → D1 一键同步")
    ap.add_argument("--vault", default=os.environ.get("HOLOSOPHY_VAULT", DEFAULT_VAULT))
    ap.add_argument("--dry-run", action="store_true", help="只解析统计，不写库")
    ap.add_argument("--keep-sql", action="store_true", help="保留生成的 SQL 文件")
    args = ap.parse_args()

    vault = Path(args.vault)
    if not vault.is_dir():
        sys.exit(f"[X] 知识库路径不存在: {vault}")

    print(f"[1/4] 解析知识库: {vault}")
    concepts, rels, stats = collect_concepts(vault)
    for cat, n in stats["per_cat"].items():
        print(f"      {cat}: {n}")
    print(f"      合计 {len(concepts)} 概念 / {len(rels)} 关系")
    for s in stats["skipped"]:
        print(f"      跳过: {s}")

    stmts = build_statements(concepts, rels)
    db_id = get_database_id()
    print(f"[2/4] 生成 SQL: {len(stmts)} 条语句 → 目标库 {db_id}")

    if args.dry_run:
        out = REPO_ROOT / "scripts" / "import_preview.sql"
        out.write_text("\n".join(stmts), encoding="utf-8")
        print(f"[dry-run] 未写库。SQL 预览: {out}")
        return

    cmd, needs_shell = find_wrangler_cmd()
    batches = [stmts[i:i + BATCH_SIZE] for i in range(0, len(stmts), BATCH_SIZE)]
    tmp_files = []
    try:
        print(f"[3/4] 写入 D1（{len(batches)} 批）...")
        for i, batch in enumerate(batches, 1):
            fd, path = tempfile.mkstemp(suffix=".sql", prefix=f"holosophy_import_{i}_")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write("\n".join(batch))
            tmp_files.append(path)
            out = run_wrangler(cmd, needs_shell, ["d1", "execute", db_id, "--remote", f"--file={path}"],
                               f"批次 {i}/{len(batches)} ({len(batch)} 条)")
            m = re.search(r"Executed (\d+) queries", out)
            print(f"      批次 {i} 完成: {m.group(1) + ' queries' if m else 'ok'}")
    finally:
        for p in tmp_files:
            if not args.keep_sql:
                Path(p).unlink(missing_ok=True)
            else:
                print(f"      SQL 保留: {p}")

    print("[4/4] 复核 ...")
    out = run_wrangler(cmd, needs_shell, ["d1", "execute", db_id, "--remote", "--command",
                             "SELECT (SELECT COUNT(*) FROM concepts) AS concepts,"
                             " (SELECT COUNT(*) FROM relationships) AS rels"], "计数复核")
    m = re.search(r'"concepts":\s*(\d+).*?"rels":\s*(\d+)', out, re.S)
    if m:
        ok = int(m.group(1)) == len(concepts) and int(m.group(2)) == len(rels)
        print(f"      线上: concepts={m.group(1)} rels={m.group(2)} "
              f"{'✓ 与本地一致' if ok else '✗ 不一致，请检查'}")
    print(f"[√] 同步完成 → https://mcp.eastastar.com/api/knowledge/search")


if __name__ == "__main__":
    main()
