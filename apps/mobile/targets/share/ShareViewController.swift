import UIKit
import UniformTypeIdentifiers

/// Thin share target: collect text/URLs and media files, persist to App Group, open host app.
class ShareViewController: UIViewController {
  private let suiteName = "group.com.eventflow.mobile"
  private let storageKey = "eventflow_share_handoff_payload"

  override func viewDidAppear(_ animated: Bool) {
    super.viewDidAppear(animated)
    collectPayload { [weak self] combined in
      guard let self else { return }
      if let ud = UserDefaults(suiteName: self.suiteName), let payload = combined, !payload.isEmpty {
        ud.set(payload, forKey: self.storageKey)
        ud.synchronize()
      }
      self.openHostAndFinish()
    }
  }

  private func collectPayload(done: @escaping (String?) -> Void) {
    guard let item = extensionContext?.inputItems.first as? NSExtensionItem else {
      done(nil)
      return
    }
    var chunks: [String] = []
    var files: [[String: String]] = []
    let group = DispatchGroup()
    let providers = item.attachments ?? []

    for provider in providers {
      if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
        group.enter()
        provider.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { data, _ in
          defer { group.leave() }
          if let url = data as? URL {
            chunks.append(url.absoluteString)
          }
        }
      }
      if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
        group.enter()
        provider.loadItem(forTypeIdentifier: UTType.plainText.identifier, options: nil) { data, _ in
          defer { group.leave() }
          if let s = data as? String {
            chunks.append(s)
          }
        }
      }

      // Images
      if provider.hasItemConformingToTypeIdentifier(UTType.image.identifier) {
        group.enter()
        provider.loadItem(forTypeIdentifier: UTType.image.identifier, options: nil) { data, _ in
          defer { group.leave() }
          guard let srcUrl = data as? URL else { return }
          guard let container = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: self.suiteName) else { return }
          let dir = container.appendingPathComponent("eventflow-share", isDirectory: true)
          try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
          let name = "shared_\(Int(Date().timeIntervalSince1970 * 1000))_\(UUID().uuidString).\(srcUrl.pathExtension.isEmpty ? "jpg" : srcUrl.pathExtension)"
          let dst = dir.appendingPathComponent(name)
          do {
            if FileManager.default.fileExists(atPath: dst.path) {
              try FileManager.default.removeItem(at: dst)
            }
            try FileManager.default.copyItem(at: srcUrl, to: dst)
            files.append([
              "uri": dst.path,
              "mimeType": "image/\(srcUrl.pathExtension.isEmpty ? "jpeg" : srcUrl.pathExtension)",
              "filename": name
            ])
          } catch {
            return
          }
        }
      }

      // Videos
      if provider.hasItemConformingToTypeIdentifier(UTType.movie.identifier) {
        group.enter()
        provider.loadItem(forTypeIdentifier: UTType.movie.identifier, options: nil) { data, _ in
          defer { group.leave() }
          guard let srcUrl = data as? URL else { return }
          guard let container = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: self.suiteName) else { return }
          let dir = container.appendingPathComponent("eventflow-share", isDirectory: true)
          try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
          let name = "shared_\(Int(Date().timeIntervalSince1970 * 1000))_\(UUID().uuidString).\(srcUrl.pathExtension.isEmpty ? "mp4" : srcUrl.pathExtension)"
          let dst = dir.appendingPathComponent(name)
          do {
            if FileManager.default.fileExists(atPath: dst.path) {
              try FileManager.default.removeItem(at: dst)
            }
            try FileManager.default.copyItem(at: srcUrl, to: dst)
            files.append([
              "uri": dst.path,
              "mimeType": "video/\(srcUrl.pathExtension.isEmpty ? "mp4" : srcUrl.pathExtension)",
              "filename": name
            ])
          } catch {
            return
          }
        }
      }
    }

    group.notify(queue: .main) {
      let text = chunks.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
      var obj: [String: Any] = [
        "capturedAt": Int(Date().timeIntervalSince1970 * 1000),
      ]
      if !files.isEmpty {
        obj["kind"] = "media"
        obj["items"] = files
        if !text.isEmpty { obj["text"] = text }
      } else if !text.isEmpty {
        obj["kind"] = "text"
        obj["text"] = text
      } else {
        done(nil)
        return
      }
      if let data = try? JSONSerialization.data(withJSONObject: obj),
         let json = String(data: data, encoding: .utf8) {
        done(json)
      } else {
        done(nil)
      }
    }
  }

  private func openHostAndFinish() {
    guard let url = URL(string: "eventflow://share-handoff") else {
      extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
      return
    }
    if #available(iOS 14.0, *) {
      extensionContext?.open(url, completionHandler: { [weak self] _ in
        self?.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
      })
    } else {
      extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
    }
  }
}
