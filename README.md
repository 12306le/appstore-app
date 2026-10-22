# 软件下载 · App

把 [apps.hoik.de](https://apps.hoik.de/) 打包成 Android 原生 App。纯 WebView 外壳，但页面内嵌在 APK 里。

## 特性

- **离线可用**：HTML/JS/CSS 全部打进 assets，没网也能打开看列表
- **外链外跳**：所有下载链接交给系统浏览器 / 下载器，不在 WebView 里下载
- **状态栏适配**：JS 注入 CSS 变量 `--sat`，页面顶部按真实状态栏高度留白，不遮挡
- **断网提示**：监听网络变化，掉线时浮出遮罩说明
- **暗色主题**：与网页一致的 `#08090A` 背景

## 与网页版的差异

网页版的「刷新」按钮依赖服务端 `/refresh` 接口重新抓取数据，App 里没有这个服务端，
因此已移除该按钮和配套的密码弹窗。数据新鲜度由 Cloudflare Worker 的每日 Cron 保证。

## 构建

推送到 `main` 即自动构建，产出在 Actions 和 Releases 里：

```
./gradlew assembleDebug assembleRelease
```

## 结构

```
app/src/main/assets/index.html        # 内嵌页面（由 tools/patch_html*.py 从线上页面生成）
app/src/main/java/com/hoik/appstore/  # MainActivity + JS Bridge
```

重新生成内嵌页面：

```bash
curl -s https://apps.hoik.de/ -o apps_page.html
python3 tools/patch_html.py && python3 tools/patch_html2.py
```
