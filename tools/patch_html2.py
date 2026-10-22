#!/usr/bin/env python3
"""第二轮清理：彻底移除依赖服务端 /refresh 的密码弹窗整段逻辑。"""
import re

P = "/var/minis/workspace/appstore-app/app/src/main/assets/index.html"
s = open(P, encoding="utf-8").read()

# 定位从 "var refbtn = null;" 到密码相关事件绑定结束的整段
start = s.find("var refbtn = null;")
if start < 0:
    raise SystemExit("找不到 refbtn 锚点")

end_anchor = 'if(pwin) pwin.addEventListener("keydown", function(e){'
end = s.find(end_anchor)
if end < 0:
    raise SystemExit("找不到密码 keydown 锚点")
# 找到该绑定块的结尾 "});"
tail = s.find("});", s.find("if(e.key === \"Escape\") closePw();", end))
if tail < 0:
    raise SystemExit("找不到密码块结尾")
tail += 3
removed_block = s[start:tail]

# 替换为：只保留 tl（状态文案）引用，其余置空
replacement = (
    "  // [App 版] 刷新与密码弹窗已移除（依赖服务端 /refresh）\n"
    "  var tl = document.querySelector(\".tl-text\");\n"
    "  var pwbd = null, pwbox = null, pwin = null, pwerr = null;\n"
    "  function closePw(){}\n"
)
s = s[:start] + replacement + s[tail:]

print("移除密码/刷新逻辑 %d 字节" % len(removed_block))

# 清理 aria-hidden 选择器里的 #refbtn
s = s.replace('".wrap, #refbtn, #pwbd, #pwbox"', '".wrap, #pwbd, #pwbox"')
s = s.replace('".wrap, #refbtn, #bd, #sheet"', '".wrap, #bd, #sheet"')

# 删除 .refbtn 的 CSS 规则
before = len(s)
s = re.sub(r'\n\.refbtn[^{]*\{[^}]*\}', '', s)
print("清理 .refbtn CSS %d 字节" % (before - len(s)))

# 删除页面上残留的密码弹窗 DOM（#pwbd / #pwbox 容器）
for pat in [
    r'<div[^>]*id="pwbd"[^>]*>\s*</div>',
    r'<div[^>]*id="pwbox".*?</div>\s*</div>',
]:
    m = re.search(pat, s, re.S)
    if m:
        print("移除 DOM: %s" % m.group()[:60].replace("\n", " "))
        s = s[:m.start()] + s[m.end():]

open(P, "w", encoding="utf-8").write(s)

# 校验
leftover = [w for w in ["refbtn", "doRefresh", "openPw", "pwb"] if w in s]
print("残留关键字:", leftover if leftover else "无")
