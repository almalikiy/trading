package com.example.alertapp

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                var isServiceRunning by remember { mutableStateOf(false) }
                Button(onClick = {
                    val intent = Intent(this, FloatingAlertService::class.java)
                    ContextCompat.startForegroundService(this, intent)
                    isServiceRunning = true
                }) {
                    Text(if (isServiceRunning) "Service Running" else "Start Floating Alert")
                }
            }
        }
    }
}
