package com.wgc.arckeyhelper

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.util.Locale

class MainActivity : Activity(), TextToSpeech.OnInitListener {
    private var speaker: TextToSpeech? = null
    private var speechReady = false

    private val secretSettings =
        "https://github.com/ytpokerspace/Slush-vm/settings/secrets/actions"
    private val actionsPage =
        "https://github.com/ytpokerspace/Slush-vm/actions"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        speaker = TextToSpeech(this, this)

        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), dp(24), dp(22), dp(28))
        }

        val scroll = ScrollView(this).apply {
            isFillViewport = true
            addView(page)
        }

        page.addView(text(
            "ARC API KEY SETUP",
            28f,
            true
        ))
        page.addView(text(
            "This helper does not ask for, read, store, or transmit your API key. " +
                "It opens GitHub's own secure settings page in your browser.",
            20f
        ))
        page.addView(text(
            "WHAT TO DO",
            23f,
            true
        ))
        page.addView(text(
            "1. Open the GitHub secret settings below.\n\n" +
                "2. Under Repository secrets, choose New repository secret.\n\n" +
                "3. Enter this exact name: ARC_API_KEY\n\n" +
                "4. Enter your key directly on GitHub and save it. Never paste it into this app or ChatGPT.\n\n" +
                "5. Return here and open Actions to inspect the next run.",
            20f
        ))
        page.addView(text(
            "If GitHub asks you to sign in, complete that inside GitHub. " +
                "This app cannot see your password or API key.",
            18f
        ))

        page.addView(actionButton(
            "OPEN GITHUB SECRET SETTINGS",
            "Opens the repository's Actions secrets page"
        ) {
            openPage(secretSettings)
        })

        page.addView(actionButton(
            "OPEN GITHUB ACTIONS",
            "Opens the repository's workflow runs"
        ) {
            openPage(actionsPage)
        })

        page.addView(actionButton(
            "READ INSTRUCTIONS ALOUD",
            "Speaks the setup instructions"
        ) {
            speakInstructions()
        })

        page.addView(text(
            "SECURITY NOTE",
            22f,
            true
        ))
        page.addView(text(
            "A password-style field inside this helper would not make a key invisible to the app. " +
                "For that reason, credential entry stays entirely on github.com.",
            18f
        ))

        setContentView(scroll)
    }

    private fun text(value: String, size: Float, bold: Boolean = false): TextView =
        TextView(this).apply {
            text = value
            textSize = size
            setTextColor(0xFF172033.toInt())
            gravity = Gravity.START
            if (bold) setTypeface(typeface, android.graphics.Typeface.BOLD)
            setPadding(0, dp(10), 0, dp(14))
            contentDescription = value
        }

    private fun actionButton(
        label: String,
        description: String,
        action: () -> Unit
    ): Button = Button(this).apply {
        text = label
        textSize = 18f
        isAllCaps = false
        minHeight = dp(68)
        contentDescription = description
        setOnClickListener { action() }
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply {
            topMargin = dp(10)
            bottomMargin = dp(10)
        }
    }

    private fun openPage(url: String) {
        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    }

    private fun speakInstructions() {
        val message = "Open GitHub secret settings. Under Repository secrets, choose " +
            "New repository secret. Enter the name ARC underscore API underscore KEY. " +
            "Enter your key directly on GitHub and save it. Do not paste the key into " +
            "this app or ChatGPT. Then return here and open GitHub Actions."
        if (speechReady) {
            speaker?.speak(message, TextToSpeech.QUEUE_FLUSH, null, "setup-guide")
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            speechReady = speaker?.setLanguage(Locale.US) != TextToSpeech.LANG_MISSING_DATA
        }
    }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    override fun onDestroy() {
        speaker?.stop()
        speaker?.shutdown()
        speaker = null
        super.onDestroy()
    }
}
