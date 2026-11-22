#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <map>
#include <string>
#include <system_error>

#include <imgui.h>
#include <rex/app/title_app.h>
#include <rex/filesystem/file_system.h>
#include <rex/kernel/title_paths.h>
#include <rex/kernel/title_runtime.h>
#include <rex/path_settings.h>
#include <rex/settings_registry.h>
#include <rex/ui/ui_system.h>

#include "generated/default/fm2_init.h"

namespace {

std::filesystem::path PcSettingsPath() {
  return REX_PATHS().config_file.Get().parent_path() / "fm2-pc-settings.txt";
}

class PcSettingsDialog final : public rex::ui::DialogBase {
 public:
  explicit PcSettingsDialog(rex::ui::IUISystem& ui) : ui_(ui) {}

  bool WantsExclusiveInput() const override { return true; }

  bool Draw(ImGuiIO&) override {
    bool open = !ImGui::IsKeyPressed(ImGuiKey_Escape, false);
    ImGui::SetNextWindowSize(ImVec2(420, 0), ImGuiCond_FirstUseEver);
    if (ImGui::Begin("FM2 PC Settings", &open,
                     ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings)) {
      ImGui::TextUnformatted("Display");
      ImGui::Separator();
      bool fullscreen = ui_.GetSettings().fullscreen.Get();
      if (ImGui::Checkbox("Fullscreen", &fullscreen)) {
        SetFullscreen(fullscreen);
      } else if (ImGui::IsKeyPressed(ImGuiKey_F, false)) {
        SetFullscreen(!fullscreen);
      }
      ImGui::TextUnformatted("F: Toggle Fullscreen  |  Esc: Close");
      ImGui::TextUnformatted("Frame Rate: Original");
      ImGui::TextWrapped("Higher frame rates are not available yet.");
      if (ImGui::Button("Reset to Defaults")) {
        SetFullscreen(false);
      }
      ImGui::SameLine();
      if (ImGui::Button("Close")) {
        open = false;
      }
      if (!status_.empty()) {
        ImGui::TextWrapped("%s", status_.c_str());
      }
    }
    ImGui::End();
    return open;
  }

 private:
  void SetFullscreen(bool fullscreen) {
    auto changed = REX_SETTINGS().SetText("ui.fullscreen", fullscreen ? "true" : "false");
    if (!changed) {
      status_ = changed.error().message;
      return;
    }
    const auto path = PcSettingsPath();
    auto pending = path;
    pending += ".tmp";
    {
      std::ofstream stream(pending, std::ios::trunc);
      stream << (fullscreen ? "fullscreen=true\n" : "fullscreen=false\n");
      stream.close();
      if (!stream) {
        status_ = "Fullscreen changed but the preference could not be saved.";
        return;
      }
    }
    std::error_code error;
    std::filesystem::rename(pending, path, error);
    status_ = error ? "Fullscreen changed but the preference could not be saved."
                    : "Settings saved.";
  }

  rex::ui::IUISystem& ui_;
  std::string status_;
};

}  // namespace

class Fm2App : public rex::app::TitleApp {
 public:
  Fm2App() : TitleApp("fm2", kPPCImageConfig) {}

 protected:
  rex::Result<void> OnConfigure(rex::SettingsRegistry& settings) override {
    REX_TRY_VOID(TitleApp::OnConfigure(settings));
    return settings.SetText(rex::SettingLayer::kTitle, "ui.fullscreen", "false");
  }

  rex::Result<void> OnInit() override {
    REX_TRY_VOID(TitleApp::OnInit());
    auto& fullscreen = GetUI().GetSettings().fullscreen;
    if (fullscreen.GetLayer() <= rex::SettingLayer::kTitle) {
      std::ifstream stream(PcSettingsPath());
      std::string preference;
      if (std::getline(stream, preference) &&
          (preference == "fullscreen=true" || preference == "fullscreen=false")) {
        REX_TRY_VOID(fullscreen.SetText(rex::SettingLayer::kTitle,
                                       preference == "fullscreen=true" ? "true" : "false"));
      }
    }
    static constexpr std::array overlays{
        rex::ui::OverlayConfig{
            "fm2_pc_settings",
            {rex::VirtualKey::kF10},
            [](rex::ui::IUISystem& ui) -> std::unique_ptr<rex::ui::IDialog> {
              return std::make_unique<PcSettingsDialog>(ui);
            }},
    };
    return GetUI().AddOverlays(overlays);
  }

  rex::Result<void> OnTitleLaunch(rex::kernel::TitleRuntime& title) override {
    auto& fs = title.GetFileSystem();
    const auto root = title.GetTitlePaths().game_root.Get();
    std::map<std::string, std::string> aliases;
    for (const auto& entry :
         std::filesystem::recursive_directory_iterator(root / "Media" / "Audio")) {
      if (!entry.is_regular_file() || entry.path().extension() != ".fsb") {
        continue;
      }
      auto name = entry.path().filename().string();
      std::ranges::transform(name, name.begin(), [](char c) {
        return c >= 'A' && c <= 'Z' ? static_cast<char>(c + 'a' - 'A') : c;
      });
      auto path = entry.path().lexically_relative(root).generic_string();
      std::ranges::replace(path, '/', '\\');
      auto [existing, inserted] = aliases.try_emplace(name, "game:\\" + path);
      if (!inserted) {
        // The engine banks have LOD-specific files with matching basenames.
        // Leave ambiguous names alone; FM2 can still open them by full path.
        existing->second.clear();
      }
    }
    for (const auto& [name, target] : aliases) {
      if (target.empty()) {
        continue;
      }
      if (auto linked = fs.Link(name, target); !linked) {
        return linked;
      }
    }

    // FM2 creates the cache: alias itself. Give its target a writable host
    // directory without permitting changes to the mounted disc.
    const auto cache = REX_PATHS().user_root.Get() / "fm2-cache";
    std::error_code error;
    std::filesystem::create_directories(cache, error);
    if (error) {
      return rex::Err(rex::Error(rex::ErrorCategory::kRuntime,
                                 "Cannot create the FM2 cache: " + error.message()));
    }
    return fs.Mount({
        .path = R"(\Device\cache0)",
        .source = cache,
        .flags = rex::filesystem::MountFlags::kWritable,
    });
  }
};

REX_TITLE_APP(Fm2App)
