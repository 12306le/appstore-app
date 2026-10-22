package com.hoik.appstore;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.InputStream;
import java.io.OutputStream;
import java.io.File;
import java.io.FileOutputStream;

/**
 * 软件下载站的原生外壳。
 * 页面本体内嵌在 assets 里，断网也能打开；所有外链交给系统浏览器/下载器。
 */
public class MainActivity extends Activity {

    private static final String ASSET_URL = "file:///android_asset/index.html";

    private WebView webView;
    private ConnectivityManager.NetworkCallback netCallback;
    private ConnectivityManager cm;

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 全屏沉浸：内容延伸到状态栏下方，由 CSS 变量补偿高度
        getWindow().setStatusBarColor(Color.parseColor("#08090A"));
        getWindow().setNavigationBarColor(Color.parseColor("#08090A"));
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor("#08090A"));
        webView.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(webView);

        configureWebView();

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return handleUri(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return handleUri(Uri.parse(url));
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                injectStatusBarInset();
                updateOfflineBanner();
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                // 只有主文档失败才提示，子资源（图标等）失败静默
                if (request.isForMainFrame()) {
                    Toast.makeText(MainActivity.this,
                            "页面加载失败", Toast.LENGTH_SHORT).show();
                }
            }
        });

        webView.loadUrl(ASSET_URL);
        watchNetwork();
    }

    private void configureWebView() {
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        // 让内嵌页面能加载 GitHub 上的图标等远程资源
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);

        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setTextZoom(100); // 不受系统字体缩放影响导致布局撑破

        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);

        webView.addJavascriptInterface(new Bridge(), "AndroidBridge");
    }

    /** 所有 http(s) 一律交给系统处理：浏览器打开 / 下载管理器接管 */
    private boolean handleUri(Uri uri) {
        if (uri == null) return true;
        String scheme = uri.getScheme();
        if (scheme == null) return true;

        if (scheme.equals("file") || scheme.equals("about") || scheme.equals("javascript")) {
            return false; // 内部导航放行
        }
        if (scheme.equals("http") || scheme.equals("https")) {
            return openExternal(uri);
        }
        // tel: mailto: market: 等
        return openExternal(uri);
    }

    private boolean openExternal(Uri uri) {
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, uri);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
            return true;
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "没有可处理该链接的应用", Toast.LENGTH_SHORT).show();
            return true;
        }
    }

    /** 把状态栏高度以 CSS 变量注入，页面据此留白 */
    private void injectStatusBarInset() {
        int insetPx = 0;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            android.view.WindowInsets insets =
                    getWindow().getDecorView().getRootWindowInsets();
            if (insets != null) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    android.graphics.Insets bars = insets.getInsets(
                            android.view.WindowInsets.Type.statusBars());
                    insetPx = bars.top;
                } else {
                    insetPx = insets.getSystemWindowInsetTop();
                }
            }
        }
        float density = getResources().getDisplayMetrics().density;
        int dp = Math.round(insetPx / density);

        String js = "(function(){document.documentElement.style.setProperty('--sat','"
                + dp + "px');})()";
        webView.evaluateJavascript(js, null);
    }

    /** 监听网络变化，切换离线提示遮罩 */
    private void watchNetwork() {
        cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        if (cm == null) return;

        netCallback = new ConnectivityManager.NetworkCallback() {
            @Override
            public void onAvailable(Network network) {
                runOnUiThread(MainActivity.this::updateOfflineBanner);
            }

            @Override
            public void onLost(Network network) {
                runOnUiThread(MainActivity.this::updateOfflineBanner);
            }
        };
        try {
            NetworkRequest req = new NetworkRequest.Builder()
                    .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                    .build();
            cm.registerNetworkCallback(req, netCallback);
        } catch (Exception ignored) {
        }
    }

    private boolean isOnline() {
        if (cm == null) return true;
        Network n = cm.getActiveNetwork();
        if (n == null) return false;
        NetworkCapabilities c = cm.getNetworkCapabilities(n);
        return c != null && c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
    }

    private void updateOfflineBanner() {
        if (webView == null) return;
        String js = "(function(){var el=document.getElementById('app-offline');"
                + "if(el)el.classList.toggle('on'," + (!isOnline()) + ");})()";
        webView.evaluateJavascript(js, null);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (cm != null && netCallback != null) {
            try {
                cm.unregisterNetworkCallback(netCallback);
            } catch (Exception ignored) {
            }
        }
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }

    /** 暴露给页面的原生能力 */
    public class Bridge {
        @JavascriptInterface
        public void openExternal(String url) {
            final Uri uri = Uri.parse(url);
            runOnUiThread(() -> openExternal(uri));
        }

        @JavascriptInterface
        public boolean isOnline() {
            return MainActivity.this.isOnline();
        }

        @JavascriptInterface
        public String appVersion() {
            try {
                return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
            } catch (Exception e) {
                return "?";
            }
        }
    }
}
