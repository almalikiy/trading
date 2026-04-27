package com.example.alertapp

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface {
                    var isServiceRunning by remember { mutableStateOf(false) }
                    
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "Trade Alert Controller",
                            style = MaterialTheme.typography.headlineMedium,
                            modifier = Modifier.padding(bottom = 16.dp)
                        )
                        
                        Button(onClick = {
                            if (checkOverlayPermission()) {
                                startFloatingService()
                                isServiceRunning = true
                            } else {
                                requestOverlayPermission()
                            }
                        }) {
                            Text(if (isServiceRunning) "Service Running" else "Start Floating Alert")
                        }
                        
                        if (!checkOverlayPermission()) {
                            Text(
                                text = "Please grant 'Display over other apps' permission to use this feature.",
                                color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.padding(top = 8.dp)
                            )
                        }
                    }
                }
            }
        }
    }

    private fun checkOverlayPermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(this)
        } else {
            true
        }
    }

    private fun requestOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivityForResult(intent, 1234)
        }
    }

    private fun startFloatingService() {
        val intent = Intent(this, FloatingAlertService::class.java)
        ContextCompat.startForegroundService(this, intent)
    }
}
