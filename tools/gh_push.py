#!/usr/bin/env python3
"""通过 GitHub REST API 提交整个目录（绕开沙箱里坏掉的 git 二进制）。

用法：
    python3 tools/gh_push.py <owner/repo> [--branch main] [--message MSG]

行为：
- 首次提交用 contents API 逐个文件创建；文件多了会撞 API 速率限制，
  因此改用 Git Data API（blob -> tree -> commit -> ref），一次提交完成。
- 已存在的仓库则基于现有 HEAD 追加提交。
"""
import base64
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {".git", ".gradle", "build", ".idea", "tools/__pycache__"}
SKIP_EXT = {".pyc"}


def api(method, path, data=None):
    cmd = ["gh", "api", "-X", method, path]
    if data is not None:
        payload = json.dumps(data)
        proc = subprocess.run(
            ["gh", "api", "-X", method, path, "--input", "-"],
            input=payload, text=True, capture_output=True,
        )
    else:
        proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError("%s %s -> %s\n%s" % (method, path, proc.returncode, proc.stderr[:800]))
    out = proc.stdout.strip()
    return json.loads(out) if out else {}


def collect_files():
    files = []
    for base, dirs, names in os.walk(ROOT):
        rel_base = os.path.relpath(base, ROOT).replace(os.sep, "/")
        if rel_base == ".":
            rel_base = ""
        dirs[:] = [d for d in dirs if os.path.join(rel_base, d).lstrip("/") not in SKIP_DIRS
                   and os.path.join(rel_base, d).strip("/") not in SKIP_DIRS]
        for n in names:
            rel = (rel_base + "/" + n).lstrip("/")
            if os.path.splitext(n)[1] in SKIP_EXT:
                continue
            if rel.startswith(".git/"):
                continue
            files.append(rel)
    return sorted(files)


def main():
    repo = sys.argv[1]
    branch = "main"
    message = "通过 API 提交"
    args = sys.argv[2:]
    for i, a in enumerate(args):
        if a == "--branch":
            branch = args[i + 1]
        if a == "--message":
            message = args[i + 1]

    files = collect_files()
    print("待提交文件 %d 个" % len(files))

    # 1. 取当前分支 HEAD（仓库可能还是空的）
    parent = None
    base_tree = None
    try:
        ref = api("GET", "/repos/%s/git/ref/heads/%s" % (repo, branch))
        parent = ref["object"]["sha"]
        commit = api("GET", "/repos/%s/git/commits/%s" % (repo, parent))
        base_tree = commit["tree"]["sha"]
        print("现有 HEAD: %s" % parent[:8])
    except RuntimeError as e:
        if any(s in str(e) for s in ("404", "Not Found", "409", "empty")):
            print("分支不存在，将作为首次提交")
        else:
            raise

    # 2. 逐个上传 blob
    entries = []
    for rel in files:
        path = os.path.join(ROOT, rel)
        with open(path, "rb") as f:
            raw = f.read()
        blob = api("POST", "/repos/%s/git/blobs" % repo, {
            "content": base64.b64encode(raw).decode(),
            "encoding": "base64",
        })
        entries.append({
            "path": rel,
            "mode": "100755" if rel == "gradlew" else "100644",
            "type": "blob",
            "sha": blob["sha"],
        })
        print("  + %-58s %7d B" % (rel, len(raw)))

    # 3. 建 tree
    tree_payload = {"tree": entries}
    if base_tree:
        tree_payload["base_tree"] = base_tree
    tree = api("POST", "/repos/%s/git/trees" % repo, tree_payload)

    # 4. 建 commit
    commit_payload = {"message": message, "tree": tree["sha"]}
    if parent:
        commit_payload["parents"] = [parent]
    new_commit = api("POST", "/repos/%s/git/commits" % repo, commit_payload)
    print("新 commit: %s" % new_commit["sha"][:8])

    # 5. 更新 / 创建 ref
    if parent:
        api("PATCH", "/repos/%s/git/refs/heads/%s" % (repo, branch),
            {"sha": new_commit["sha"], "force": False})
    else:
        api("POST", "/repos/%s/git/refs" % repo,
            {"ref": "refs/heads/%s" % branch, "sha": new_commit["sha"]})
    print("已推送 -> %s@%s" % (repo, branch))


if __name__ == "__main__":
    main()
