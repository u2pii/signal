package io.github.u2pii.signal;

import android.content.Intent;
import android.content.pm.PackageManager;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * 按包名直接拉起交易所 App 的桌面入口。
 * 不走深链，所以不依赖对方注册什么 scheme / App Link。
 */
@CapacitorPlugin(name = "AppLaunch")
public class AppLaunchPlugin extends Plugin {

    @PluginMethod
    public void openApp(PluginCall call) {
        JSObject ret = new JSObject();
        String hit = "";

        JSArray pkgs = call.getArray("pkgs");
        if (pkgs != null) {
            PackageManager pm = getContext().getPackageManager();
            for (int i = 0; i < pkgs.length(); i++) {
                String pkg = pkgs.optString(i, "");
                if (pkg == null || pkg.isEmpty()) continue;
                try {
                    Intent it = pm.getLaunchIntentForPackage(pkg);
                    if (it == null) continue;
                    it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    getContext().startActivity(it);
                    hit = pkg;
                    break;
                } catch (Exception e) {
                    // 下一个
                }
            }
        }

        ret.put("ok", !hit.isEmpty());
        ret.put("pkg", hit);
        call.resolve(ret);
    }
}
