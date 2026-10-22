#!/usr/bin/env python3
"""把 apps.hoik.de 的线上页面改造成可离线内嵌的 App 页面。

改动：
1. 注入 <base target="_blank"> 之外的方案：直接捕获 click，交给 Android 端处理
2. 移除「刷新」按钮及相关逻辑（依赖服务端 /refresh，file:// 下必然失败）
3. 补 safe-area / 状态栏内边距，适配全面屏
4. 加一个遮罩，离线时给出明确提示
"""
import re
import sys

SRC = "/var/minis/workspace/apps_page.html"
DST = "/var/minis/workspace/appstore-app/app/src/main/assets/index.html"

html = open(SRC, encoding="utf-8").read()
orig_len = len(html)

# ---------- 1. 移除刷新按钮 ----------
removed = []

# 顶栏里的刷新按钮（<button id="refbtn"> ... </button>）
m = re.search(r'<button[^>]*id="refbtn"[^>]*>.*?</button>', html, re.S)
if m:
    removed.append("refbtn button")
    html = html[:m.start()] + html[m.end():]
else:
    print("WARN: refbtn button not found")

# 刷新相关 JS：函数 doRefresh 以及它的事件绑定
m = re.search(r'\n\s*function doRefresh\(pw\)\{.*?\n\s*\}\n', html, re.S)
if m:
    removed.append("doRefresh()")
    html = html[:m.start()] + "\n" + html[m.end():]

m = re.search(r'\n[^\n]*refbtn\.addEventListener\([^\n]*\n', html)
if m:
    removed.append("refbtn listener")
    html = html[:m.start()] + "\n" + html[m.end():]

# 残留的 refbtn 引用（如 const refbtn = ...）置空以防 ReferenceError
html = re.sub(r'\b(const|let|var)\s+refbtn\s*=\s*[^;]+;',
              r'\1 refbtn = null;', html)

# ---------- 2. 外链交给系统处理 ----------
INJECT_CLICK = """
<script>
/* 由 App 注入：把所有 http(s) 链接交给 Android 系统浏览器打开，
   避免 WebView 内把整个页面导航走。 */
(function(){
  document.addEventListener("click", function(e){
    var a = e.target;
    while (a && a.tagName !== "A") a = a.parentElement;
    if (!a) return;
    var href = a.getAttribute("href");
    if (!href) return;
    if (href.indexOf("http://") === 0 || href.indexOf("https://") === 0) {
      e.preventDefault();
      e.stopPropagation();
      if (window.AndroidBridge && window.AndroidBridge.openExternal) {
        window.AndroidBridge.openExternal(href);
      } else {
        window.open(href, "_blank");
      }
    }
  }, true);
})();
</script>
"""
html = html.replace("</body>", INJECT_CLICK + "</body>")

# ---------- 3. 状态栏 / 安全区适配 ----------
APP_CSS = """
<style id="app-shell-css">
/* 顶部留出状态栏高度（Android 端通过 CSS 变量注入），底部留出手势条 */
body{padding-top:calc(22px + var(--sat, 0px))!important}
html{padding-bottom:env(safe-area-inset-bottom)}
/* 离线遮罩 */
#app-offline{position:fixed;inset:0;z-index:9999;display:none;
  background:rgba(8,9,10,.94);color:#F7F8F8;align-items:center;justify-content:center;
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;text-align:center;padding:24px}
#app-offline.on{display:flex}
#app-offline b{display:block;margin-bottom:8px;font-size:16px}
#app-offline span{color:#9CA3AF;font-size:13px}
</style>
"""
html = html.replace("</head>", APP_CSS + "</head>")

OFFLINE_DIV = ('<div id="app-offline"><div><b>网络不可用</b>'
               '<span>列表内容已内嵌，但图标与下载需要联网</span></div></div>')
html = html.replace("<body", "<body", 1)
m = re.search(r"<body[^>]*>", html)
if m:
    html = html[:m.end()] + OFFLINE_DIV + html[m.end():]

open(DST, "w", encoding="utf-8").write(html)

print("原页面: %d bytes -> 内嵌: %d bytes" % (orig_len, len(html)))
print("移除项: %s" % (", ".join(removed) if removed else "无"))
leftover = html.count("refbtn") + html.count("doRefresh")
print("残留 refbtn/doRefresh 引用: %d (const refbtn=null 计数正常)" % leftover)
