# 页面内容全部由 JS 在 WebView 里驱动，不做混淆裁剪以防止误伤
-keepclassmembers class com.hoik.appstore.MainActivity$Bridge {
    public *;
}
-keepattributes JavascriptInterface
