#include <algorithm>
#include <array>
#include <atomic>
#include <cstring>
#include <filesystem>
#include <format>
#include <fstream>
#include <map>
#include <string>
#include <string_view>
#include <system_error>

#include <imgui.h>
#include <rex/app/title_app.h>
#include <rex/filesystem/file_system.h>
#include <rex/gpu/graphics_system.h>
#include <rex/kernel/title_paths.h>
#include <rex/kernel/title_runtime.h>
#include <rex/logging/log_category.h>
#include <rex/path_settings.h>
#include <rex/ppc/hook.h>
#include <rex/ppc/stack.h>
#include <rex/settings_registry.h>
#include <rex/title.h>
#include <rex/ui/ui_system.h>

#include "generated/default/fm2_init.h"
#include "generated/default/fm2_pch.h"

namespace {

struct DisplayMenuFlow {
  std::string stock;
  std::string updated;
};

DisplayMenuFlow display_menu_flow;
rex::ui::IUISystem* display_menu_ui = nullptr;
rex::gpu::IGraphicsSystem* display_menu_graphics = nullptr;
double active_guest_refresh_hz = 60.0;
int launch_render_scale_x = 1;
int launch_render_scale_y = 1;
bool launch_lower_resolution = false;
std::atomic_bool lower_resolution_applied{false};
constexpr std::string_view kPerformanceHud = "fm2_performance_hud";
constexpr std::size_t kStockOptionsSize = 33679;

DisplayMenuFlow ReadDisplayMenuFlow(const std::filesystem::path& game_root) {
  const auto read = [](const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    std::string data(kStockOptionsSize + 1, '\0');
    input.read(data.data(), data.size());
    const auto size = input.gcount();
    if (!input.eof() || input.bad() || size == 0) {
      return std::string{};
    }
    data.resize(static_cast<std::size_t>(size));
    return data;
  };
  const auto folder = game_root.parent_path() / "display-menu";
  auto stock = read(folder / "stock.xml");
  auto updated = read(folder / "options.xml");
  if (stock.size() != kStockOptionsSize || updated.empty() || updated.size() > stock.size() ||
      updated.find('\0') != std::string::npos) {
    return {};
  }
  return {std::move(stock), std::move(updated)};
}

std::filesystem::path PcSettingsPath() {
  return REX_PATHS().config_file.Get().parent_path() / "fm2-pc-settings.txt";
}

enum class RenderResolution { kNative, kLower, k1080p, kDouble };

constexpr std::array kRenderResolutionNames{
    "1280x720 (Native)", "960x540 (Experimental)", "1920x1080 (Experimental)",
    "2560x1440 (Experimental 2x)",
};

struct PcPreferences {
  bool fullscreen = false;
  bool experimental_120hz = false;
  bool stretch = false;
  bool performance_hud = false;
  RenderResolution render_resolution = RenderResolution::kNative;
};

PcPreferences ReadPcPreferences() {
  PcPreferences preferences;
  std::ifstream stream(PcSettingsPath());
  for (std::string line; std::getline(stream, line);) {
    if (line == "fullscreen=true" || line == "fullscreen=false") {
      preferences.fullscreen = line == "fullscreen=true";
    } else if (line == "refresh_hz=120" || line == "refresh_hz=60") {
      preferences.experimental_120hz = line == "refresh_hz=120";
    } else if (line == "aspect=original" || line == "aspect=stretch") {
      preferences.stretch = line == "aspect=stretch";
    } else if (line == "performance_hud=true" || line == "performance_hud=false") {
      preferences.performance_hud = line == "performance_hud=true";
    } else if (line == "render_resolution=720" || line == "render_scale=1") {
      preferences.render_resolution = RenderResolution::kNative;
    } else if (line == "render_resolution=540") {
      preferences.render_resolution = RenderResolution::kLower;
    } else if (line == "render_resolution=1080") {
      preferences.render_resolution = RenderResolution::k1080p;
    } else if (line == "render_resolution=1440" || line == "render_scale=2") {
      preferences.render_resolution = RenderResolution::kDouble;
    }
  }
  return preferences;
}

bool WritePcPreferences(const PcPreferences& preferences) {
  const auto path = PcSettingsPath();
  auto pending = path;
  pending += ".tmp";
  std::ofstream stream(pending, std::ios::trunc);
  constexpr std::array kRenderHeights{720, 540, 1080, 1440};
  stream << (preferences.fullscreen ? "fullscreen=true\n" : "fullscreen=false\n")
         << (preferences.experimental_120hz ? "refresh_hz=120\n" : "refresh_hz=60\n")
         << (preferences.stretch ? "aspect=stretch\n" : "aspect=original\n")
         << (preferences.performance_hud ? "performance_hud=true\n" : "performance_hud=false\n")
         << "render_resolution="
         << kRenderHeights[static_cast<std::size_t>(preferences.render_resolution)] << '\n';
  stream.close();
  if (!stream) {
    return false;
  }
  std::error_code error;
  std::filesystem::rename(pending, path, error);
  return !error;
}

std::string RefreshStatus(const PcPreferences& preferences) {
  return std::format("Active guest rate: {:g} Hz\nSaved for next normal launch: {} Hz",
                     active_guest_refresh_hz, preferences.experimental_120hz ? 120 : 60);
}

std::string RenderResolutionStatus(const PcPreferences& preferences) {
  const auto saved = kRenderResolutionNames[static_cast<std::size_t>(preferences.render_resolution)];
  if (lower_resolution_applied.load()) {
    return std::format("Launch preset: {}x{}\nSaved: {}", 960 * launch_render_scale_x,
                       540 * launch_render_scale_y, saved);
  }
  return std::format("Launch render scale: {}x by {}x\nSaved: {}", launch_render_scale_x,
                     launch_render_scale_y, saved);
}

constexpr std::array<std::pair<std::string_view, std::string_view>, 3> kExperimentalTiming{{
    {"ui.video_mode_refresh_rate", "120"},
    {"gpu.vsync", "true"},
    {"gpu.vulkan.unsynced_present", "true"},
}};

constexpr std::string_view kLetterbox = "gpu.xenos.present_letterbox";

rex::Result<void> ApplyDisplayPreferences(rex::ui::IUISystem& ui,
                                          const PcPreferences& before,
                                          const PcPreferences& after, bool reset = false) {
  auto& settings = REX_SETTINGS();
  if ((reset || before.fullscreen != after.fullscreen) &&
      ui.GetSettings().fullscreen.Get() != after.fullscreen) {
    REX_TRY_VOID(settings.SetText("ui.fullscreen", after.fullscreen ? "true" : "false"));
  }
  if (reset || before.stretch != after.stretch) {
    REX_TRY_VOID(settings.SetText(kLetterbox, after.stretch ? "false" : "true"));
  }
  if (reset || before.performance_hud != after.performance_hud) {
    ui.ShowOverlay(kPerformanceHud, after.performance_hud);
  }
  if (!WritePcPreferences(after)) {
    return rex::Err(rex::ErrorCategory::kRuntime, "Could not save PC settings.");
  }
  return rex::Ok();
}

class PerformanceHud final : public rex::ui::DialogBase {
 public:
  bool Draw(ImGuiIO&) override {
    if (!display_menu_graphics) {
      return true;
    }
    const auto stats = display_menu_graphics->GetFrameStats();
    ImGui::SetNextWindowPos(ImVec2(12, 12));
    ImGui::SetNextWindowBgAlpha(0.75f);
    if (ImGui::Begin("##FM2Performance", nullptr,
                     ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                         ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoSavedSettings |
                         ImGuiWindowFlags_NoFocusOnAppearing)) {
      ImGui::Text("Guest: %.1f FPS | %.2f ms", stats.fps, stats.frame_time_ms);
    }
    ImGui::End();
    return true;
  }
};

class PcSettingsDialog final : public rex::ui::DialogBase {
 public:
  explicit PcSettingsDialog(rex::ui::IUISystem& ui)
      : ui_(ui), preferences_(ReadPcPreferences()) {}

  bool WantsExclusiveInput() const override { return true; }

  void OnShow() override {
    preferences_ = ReadPcPreferences();
    status_.clear();
  }

  bool Draw(ImGuiIO&) override {
    bool open = !ImGui::IsKeyPressed(ImGuiKey_Escape, false);
    ImGui::SetNextWindowSize(ImVec2(420, 0), ImGuiCond_FirstUseEver);
    if (ImGui::Begin("FM2 PC Settings", &open,
                     ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings)) {
      ImGui::TextUnformatted("Display");
      ImGui::Separator();
      bool fullscreen = ui_.GetSettings().fullscreen.Get();
      if (ImGui::Checkbox("Fullscreen", &fullscreen)) {
        Change(&PcPreferences::fullscreen, fullscreen);
      } else if (ImGui::IsKeyPressed(ImGuiKey_F, false)) {
        Change(&PcPreferences::fullscreen, !fullscreen);
      }
      bool stretch = preferences_.stretch;
      if (ImGui::Checkbox("Stretch to fill window", &stretch)) {
        Change(&PcPreferences::stretch, stretch);
      }
      bool hud = preferences_.performance_hud;
      if (ImGui::Checkbox("Performance HUD", &hud)) {
        Change(&PcPreferences::performance_hud, hud);
      }
      int timing = preferences_.experimental_120hz ? 1 : 0;
      if (ImGui::Combo("Frame Rate (next launch)", &timing,
                       "Original (60 Hz)\0Experimental (120 Hz)\0")) {
        Change(&PcPreferences::experimental_120hz, timing == 1);
      } else if (ImGui::IsKeyPressed(ImGuiKey_R, false)) {
        Change(&PcPreferences::experimental_120hz, !preferences_.experimental_120hz);
      }
      ImGui::TextUnformatted(RefreshStatus(preferences_).c_str());
      ImGui::TextUnformatted("F: Fullscreen  |  R: Frame Rate  |  Esc: Close");
      ImGui::TextWrapped("Restart to apply. 120 Hz may tear; actual FPS and gameplay timing "
                         "are not verified. Launch overrides take precedence.");
      int render_resolution = static_cast<int>(preferences_.render_resolution);
      if (ImGui::Combo("Render Resolution (next launch)", &render_resolution,
                       kRenderResolutionNames.data(), kRenderResolutionNames.size())) {
        auto preferences = preferences_;
        preferences.render_resolution = static_cast<RenderResolution>(render_resolution);
        Save(preferences);
      }
      ImGui::TextUnformatted(RenderResolutionStatus(preferences_).c_str());
      if (ImGui::Button("Reset to Defaults")) {
        ImGui::OpenPopup("Restore Display Defaults?");
      }
      if (ImGui::BeginPopupModal("Restore Display Defaults?", nullptr,
                                 ImGuiWindowFlags_AlwaysAutoResize)) {
        if (ImGui::Button("Restore")) {
          Save({}, true);
          ImGui::CloseCurrentPopup();
        }
        ImGui::SameLine();
        if (ImGui::Button("Cancel")) {
          ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
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
  void Change(bool PcPreferences::*field, bool value) {
    auto preferences = preferences_;
    preferences.*field = value;
    Save(preferences, false, field == &PcPreferences::fullscreen);
  }

  void Save(PcPreferences preferences, bool reset = false, bool fullscreen_changed = false) {
    auto before = preferences_;
    if (fullscreen_changed) {
      before.fullscreen = ui_.GetSettings().fullscreen.Get();
    }
    auto changed = ApplyDisplayPreferences(ui_, before, preferences, reset);
    if (!changed) {
      status_ = changed.error().message;
      return;
    }
    const bool timing_changed = preferences_.experimental_120hz != preferences.experimental_120hz;
    const bool render_changed = preferences_.render_resolution != preferences.render_resolution;
    preferences_ = preferences;
    status_ = timing_changed || render_changed ? "Settings saved. Restart to apply."
                                               : "Settings saved.";
  }

  rex::ui::IUISystem& ui_;
  PcPreferences preferences_;
  std::string status_;
};

}  // namespace

extern "C" REX_FUNC(__imp__sub_824CF490);
extern "C" REX_FUNC(__imp__sub_824B6DB8);
extern "C" REX_FUNC(__imp__sub_825F4EE8);
extern "C" REX_FUNC(__imp__sub_825AE450);

REX_HOOK_RAW(sub_825AE450) {
  if (launch_lower_resolution && !lower_resolution_applied.load() &&
      ctx.lr == 0x825b3808 && ctx.r7.u32 == 0) {
    // Profile 0 describes the European title's render dimensions and its
    // three horizontal EDRAM strips. Both must change together.
    constexpr u32 kProfile = 0x829a2ba0;
    constexpr std::array<u32, 4> kNativeEdges{0, 256, 512, 720};
    constexpr std::array<u32, 4> kLowerEdges{0, 192, 384, 540};
    bool matches = REX_LOAD_U32(kProfile + 4) == 1280 &&
                   REX_LOAD_U32(kProfile + 8) == 720 &&
                   REX_LOAD_U32(kProfile + 12) == 2 && REX_LOAD_U32(kProfile + 16) == 3;
    for (u32 i = 0; matches && i < 3; ++i) {
      const u32 box = kProfile + 32 + i * 16;
      matches = REX_LOAD_U32(box) == 0 && REX_LOAD_U32(box + 4) == kNativeEdges[i] &&
                REX_LOAD_U32(box + 8) == 1280 && REX_LOAD_U32(box + 12) == kNativeEdges[i + 1];
    }
    if (matches) {
      REX_STORE_U32(kProfile + 4, 960);
      REX_STORE_U32(kProfile + 8, 540);
      for (u32 i = 0; i < 3; ++i) {
        const u32 box = kProfile + 32 + i * 16;
        REX_STORE_U32(box + 4, kLowerEdges[i]);
        REX_STORE_U32(box + 8, 960);
        REX_STORE_U32(box + 12, kLowerEdges[i + 1]);
      }
      lower_resolution_applied.store(true);
      REXLOG_INFO("FM2: applied 960x540 render profile (4x MSAA, three strips)");
    } else {
      REXLOG_WARN("FM2: unexpected 3D render profile layout; keeping stock guest profile");
    }
  }
  __imp__sub_825AE450(ctx, base);
}

// European FM2's Lua type, string argument and push-string functions.
REX_IMPORT(sub_824B69F8, GuestLuaType, i32(u32, i32));
REX_IMPORT(sub_824B6DB8, GuestLuaString, u32(u32, i32, u32));
REX_IMPORT(sub_824B70F8, GuestLuaPushString, void(u32, u32));

REX_HOOK_RAW(sub_825F4EE8) {
  // These read-only queries return text without advancing the native flow.
  constexpr i32 kLuaString = 4;
  const u32 lua = ctx.r3.u32;
  if (display_menu_ui && lua && GuestLuaType(ctx, base, lua, 2) == kLuaString) {
    const u32 address = GuestLuaString(ctx, base, lua, 2, 0);
    if (address) {
      const auto* event = reinterpret_cast<const char*>(base + address);
      constexpr char kRefreshStatus[] = "FM2ReadRefreshStatus";
      constexpr char kWindowStatus[] = "FM2ReadWindowStatus";
      constexpr char kRenderStatus[] = "FM2ReadRenderResolution";
      std::string status;
      if (std::strncmp(event, kRefreshStatus, sizeof(kRefreshStatus)) == 0) {
        status = RefreshStatus(ReadPcPreferences());
      } else if (std::strncmp(event, kWindowStatus, sizeof(kWindowStatus)) == 0) {
        status = display_menu_ui->GetSettings().fullscreen.Get()
                     ? "Current window mode: Fullscreen"
                     : "Current window mode: Windowed";
      } else if (std::strncmp(event, kRenderStatus, sizeof(kRenderStatus)) == 0) {
        status = RenderResolutionStatus(ReadPcPreferences());
      }
      if (!status.empty()) {
        rex::ppc::StackFrame frame(ctx, base);
        GuestLuaPushString(ctx, base, lua, frame.PushString(status).GetGuestAddress());
        ctx.r3.u64 = 1;
        return;
      }
    }
  }
  __imp__sub_825F4EE8(ctx, base);
}

REX_HOOK_RAW(sub_824CF490) {
  const auto& flow = display_menu_flow;
  // The European title's flow loader passes an owned, terminated XML buffer here.
  if (ctx.lr == 0x825e1158 && ctx.r4.u32 && !flow.stock.empty()) {
    auto* text = reinterpret_cast<char*>(base + ctx.r4.u32);
    if (std::strncmp(text, flow.stock.c_str(), flow.stock.size() + 1) == 0) {
      std::memcpy(text, flow.updated.c_str(), flow.updated.size() + 1);
      REXLOG_INFO("Installed native FM2 Display & Performance flow");
    }
  }
  __imp__sub_824CF490(ctx, base);
}

REX_HOOK_RAW(sub_824B6DB8) {
  // The native UI event handler converts the Lua event name to a string at this call site.
  const bool from_menu_event = ctx.lr == 0x825f24d8;
  __imp__sub_824B6DB8(ctx, base);
  if (!from_menu_event || !display_menu_ui || !ctx.r3.u32) {
    return;
  }
  const auto* text = reinterpret_cast<const char*>(base + ctx.r3.u32);
  enum class Action { kFullscreen, kAspect, kHud, kRefresh, kRenderResolution, kRestore };
  constexpr std::array actions{
      std::pair{"FM2ToggleFullscreen", Action::kFullscreen},
      std::pair{"FM2ToggleAspect", Action::kAspect},
      std::pair{"FM2ToggleHud", Action::kHud},
      std::pair{"FM2ToggleRefresh", Action::kRefresh},
      std::pair{"FM2ToggleRenderResolution", Action::kRenderResolution},
      std::pair{"FM2RestoreDisplay", Action::kRestore},
  };
  auto action = std::ranges::find_if(actions, [text](const auto& entry) {
    return std::strncmp(text, entry.first, std::strlen(entry.first) + 1) == 0;
  });
  if (action == actions.end()) {
    return;
  }
  auto* ui = display_menu_ui;
  ui->PostTask([ui, action = action->second] {
    auto before = ReadPcPreferences();
    auto preferences = before;
    switch (action) {
      case Action::kFullscreen:
        before.fullscreen = ui->GetSettings().fullscreen.Get();
        preferences.fullscreen = !before.fullscreen;
        break;
      case Action::kAspect: preferences.stretch = !before.stretch; break;
      case Action::kHud: preferences.performance_hud = !before.performance_hud; break;
      case Action::kRefresh: preferences.experimental_120hz = !before.experimental_120hz; break;
      case Action::kRenderResolution:
        preferences.render_resolution = static_cast<RenderResolution>(
            (static_cast<std::size_t>(before.render_resolution) + 1) % kRenderResolutionNames.size());
        break;
      case Action::kRestore: preferences = {}; break;
    }
    auto changed = ApplyDisplayPreferences(*ui, before, preferences, action == Action::kRestore);
    if (!changed) {
      REXLOG_WARN("Native Display & Performance: {}", changed.error().message);
    } else {
      REXLOG_INFO("Native Display & Performance: saved fullscreen={}, stretch={}, HUD={}, "
                  "refresh={}, render resolution={}",
                  preferences.fullscreen, preferences.stretch, preferences.performance_hud,
                  preferences.experimental_120hz ? 120 : 60,
                  kRenderResolutionNames[static_cast<std::size_t>(preferences.render_resolution)]);
    }
  });
}

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
    const auto preferences = ReadPcPreferences();
    auto& fullscreen = GetUI().GetSettings().fullscreen;
    if (preferences.fullscreen && fullscreen.GetLayer() <= rex::SettingLayer::kTitle) {
      REX_TRY_VOID(fullscreen.SetText(rex::SettingLayer::kTitle, "true"));
    }
    if (preferences.stretch && REX_SETTINGS().Find(kLetterbox)) {
      REX_TRY_VOID(REX_SETTINGS().SetText(rex::SettingLayer::kTitle, kLetterbox, "false"));
    }
    if (preferences.experimental_120hz) {
      // Treat the three settings as one profile. Do not mix it with explicit overrides.
      auto& settings = REX_SETTINGS();
      const bool use_profile = std::ranges::all_of(kExperimentalTiming, [&](const auto& entry) {
        auto setting = settings.Find(entry.first);
        return setting && (*setting)->GetLayer() <= rex::SettingLayer::kTitle;
      });
      if (use_profile) {
        for (const auto& [name, value] : kExperimentalTiming) {
          REX_TRY_VOID(settings.SetText(rex::SettingLayer::kTitle, name, value));
        }
      }
    }
    auto& graphics_settings = GetGraphics().GetSettings();
    auto& scale_x = graphics_settings.resolution_scale_x;
    auto& scale_y = graphics_settings.resolution_scale_y;
    if (scale_x.GetLayer() <= rex::SettingLayer::kTitle &&
        scale_y.GetLayer() <= rex::SettingLayer::kTitle) {
      launch_lower_resolution = preferences.render_resolution == RenderResolution::kLower ||
                                preferences.render_resolution == RenderResolution::k1080p;
      if (preferences.render_resolution == RenderResolution::kDouble ||
          preferences.render_resolution == RenderResolution::k1080p) {
        REX_TRY_VOID(scale_x.SetText(rex::SettingLayer::kTitle, "2"));
        REX_TRY_VOID(scale_y.SetText(rex::SettingLayer::kTitle, "2"));
      }
    }
    launch_render_scale_x = scale_x.Get();
    launch_render_scale_y = scale_y.Get();
    lower_resolution_applied.store(false);
    static constexpr std::array overlays{
        rex::ui::OverlayConfig{
            "fm2_pc_settings",
            {rex::VirtualKey::kF10},
            [](rex::ui::IUISystem& ui) -> std::unique_ptr<rex::ui::IDialog> {
              return std::make_unique<PcSettingsDialog>(ui);
            }},
        rex::ui::OverlayConfig{
            kPerformanceHud, {}, [](rex::ui::IUISystem&) -> std::unique_ptr<rex::ui::IDialog> {
              return std::make_unique<PerformanceHud>();
            }},
    };
    display_menu_graphics = &GetGraphics();
    REX_TRY_VOID(GetUI().AddOverlays(overlays));
    if (preferences.performance_hud) {
      GetUI().ShowOverlay(kPerformanceHud, true);
    }
    return rex::Ok();
  }

  void OnShutdown() override {
    TitleApp::OnShutdown();
    display_menu_ui = nullptr;
    display_menu_graphics = nullptr;
  }

  rex::Result<void> OnTitleLaunch(rex::kernel::TitleRuntime& title) override {
    auto& fs = title.GetFileSystem();
    const auto root = title.GetTitlePaths().game_root.Get();
    display_menu_flow = ReadDisplayMenuFlow(root);
    display_menu_ui = &GetUI();
    active_guest_refresh_hz = GetUI().GetVideoMode().refresh_rate;
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
