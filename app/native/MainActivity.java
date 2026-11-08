package io.github.u2pii.signal;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(AppLaunchPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
