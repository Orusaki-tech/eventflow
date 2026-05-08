const { withMainActivity } = require("@expo/config-plugins");

const HANDOFF_HELPER = `
  private fun maybePersistShareIntent(intent: Intent?) {
    if (intent == null) return
    val action = intent.action ?: return
    if (action != Intent.ACTION_SEND && action != Intent.ACTION_SEND_MULTIPLE) return
    val mime = intent.type ?: ""

    fun writeJson(obj: JSONObject) {
      try {
        File(filesDir, "eventflow-share-handoff.json").writeText(obj.toString())
      } catch (_: Exception) {}
    }

    fun copyUriToFile(uri: android.net.Uri, i: Int): JSONObject? {
      try {
        val cr = applicationContext.contentResolver
        val type = cr.getType(uri) ?: mime
        val ext = when {
          type.contains("png") -> "png"
          type.contains("webp") -> "webp"
          type.contains("gif") -> "gif"
          type.contains("mp4") -> "mp4"
          type.contains("quicktime") -> "mov"
          type.contains("jpeg") || type.contains("jpg") -> "jpg"
          else -> "bin"
        }
        val dir = File(filesDir, "eventflow-share").apply { mkdirs() }
        val outFile = File(dir, "shared_\${System.currentTimeMillis()}_\${i}.\${ext}")
        cr.openInputStream(uri).use { input ->
          if (input == null) return null
          outFile.outputStream().use { output -> input.copyTo(output) }
        }
        val item = JSONObject()
        item.put("uri", outFile.absolutePath)
        item.put("mimeType", type)
        item.put("filename", outFile.name)
        return item
      } catch (_: Exception) {
        return null
      }
    }

    // If there are shared streams, persist as media payload.
    try {
      val items = org.json.JSONArray()
      if (action == Intent.ACTION_SEND) {
        val u = intent.getParcelableExtra<android.net.Uri>(Intent.EXTRA_STREAM)
        if (u != null) {
          val item = copyUriToFile(u, 0)
          if (item != null) items.put(item)
        }
      } else {
        val list = intent.getParcelableArrayListExtra<android.net.Uri>(Intent.EXTRA_STREAM)
        if (list != null) {
          for ((idx, u) in list.withIndex()) {
            val item = copyUriToFile(u, idx)
            if (item != null) items.put(item)
          }
        }
      }
      if (items.length() > 0) {
        val o = JSONObject()
        o.put("kind", "media")
        o.put("capturedAt", System.currentTimeMillis())
        o.put("items", items)
        // Optional text (caption/url)
        val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: intent.getStringExtra(Intent.EXTRA_SUBJECT)
        if (text != null && text.isNotBlank()) o.put("text", text)
        writeJson(o)
        return
      }
    } catch (_: Exception) {}

    // Fall back to text payload.
    val text = intent.getStringExtra(Intent.EXTRA_TEXT)
      ?: intent.getStringExtra(Intent.EXTRA_SUBJECT)
      ?: return
    val o = JSONObject()
    o.put("kind", "text")
    o.put("text", text)
    o.put("capturedAt", System.currentTimeMillis())
    writeJson(o)
  }
`;

function injectMainActivity(contents) {
  if (contents.includes("maybePersistShareIntent")) {
    return contents;
  }
  const imports = `import android.content.Intent
import android.net.Uri
import org.json.JSONObject
import org.json.JSONArray
import java.io.File
`;

  let next = contents;
  if (!next.includes("import org.json.JSONObject")) {
    next = next.replace(
      "import expo.modules.ReactActivityDelegateWrapper",
      `import expo.modules.ReactActivityDelegateWrapper
${imports}`
    );
  }

  next = next.replace(
    "super.onCreate(null)",
    `super.onCreate(null)
    maybePersistShareIntent(intent)`
  );

  const closingClass = "  override fun invokeDefaultOnBackPressed() {";
  if (!next.includes("override fun onNewIntent")) {
    next = next.replace(
      closingClass,
      `  override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    setIntent(intent)
    maybePersistShareIntent(intent)
  }

${closingClass}`
    );
  }

  const insertAt = next.lastIndexOf("\n}");
  if (insertAt !== -1) {
    next =
      next.slice(0, insertAt) + HANDOFF_HELPER.trimEnd() + "\n" + next.slice(insertAt);
  }

  return next;
}

/** @type {import("@expo/config-plugins").ConfigPlugin} */
module.exports = function withAndroidShareHandoff(config) {
  return withMainActivity(config, (modConfig) => {
    if (modConfig.modResults.language !== "kt") {
      return modConfig;
    }
    modConfig.modResults.contents = injectMainActivity(modConfig.modResults.contents);
    return modConfig;
  });
};
