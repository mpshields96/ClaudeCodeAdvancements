#!/usr/bin/env python3
"""iOS project generator for Claude Code workflows (MT-13 Phase 2).

Generates a complete Xcode project with SwiftUI app target, test target,
CLAUDE.md, and CCA-convention files. The generated project compiles and
runs in the iOS Simulator via xcodebuild from the CLI.

Usage:
    python3 ios_project_gen.py MyAppName [--output /path] [--bundle-id com.x.y]

Architecture:
    - Generates valid .xcodeproj/project.pbxproj (Xcode 15+ format)
    - SwiftUI @main app entry point
    - ContentView with Preview macro
    - Swift Testing @Test target
    - CLAUDE.md with SwiftUI rules + CCA conventions
    - .gitignore for Xcode projects
"""

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ProjectConfig:
    """Configuration for iOS project generation."""
    name: str
    bundle_id: str = ""
    deployment_target: str = "18.0"
    swift_version: str = "6.0"
    include_tests: bool = True

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Project name cannot be empty")
        self.name = self.name.strip()
        if not self.bundle_id:
            self.bundle_id = f"com.cca.{self.module_name}"

    @property
    def module_name(self) -> str:
        """Sanitized name for use as Swift module identifier."""
        return re.sub(r"[^a-zA-Z0-9]", "", self.name)


# ---------------------------------------------------------------------------
# UUID generation (deterministic from name for reproducible builds)
# ---------------------------------------------------------------------------

def _make_uuid(seed: str) -> str:
    """Generate a 24-char hex UUID deterministically from seed.

    Xcode pbxproj uses 24-character uppercase hex strings as object IDs.
    We derive them from a seed so regeneration produces identical files.
    """
    h = hashlib.sha256(seed.encode()).hexdigest().upper()
    return h[:24]


# ---------------------------------------------------------------------------
# pbxproj generation
# ---------------------------------------------------------------------------

def generate_pbxproj(cfg: ProjectConfig) -> str:
    """Generate a valid project.pbxproj file content."""
    name = cfg.module_name
    bundle_id = cfg.bundle_id

    # Deterministic UUIDs for all pbxproj objects
    root_id = _make_uuid(f"{name}_root")
    main_group_id = _make_uuid(f"{name}_maingroup")
    sources_group_id = _make_uuid(f"{name}_sourcesgroup")
    app_target_id = _make_uuid(f"{name}_apptarget")
    app_config_list_id = _make_uuid(f"{name}_appconfigs")
    proj_config_list_id = _make_uuid(f"{name}_projconfigs")
    debug_config_id = _make_uuid(f"{name}_debug")
    release_config_id = _make_uuid(f"{name}_release")
    app_debug_id = _make_uuid(f"{name}_appdebug")
    app_release_id = _make_uuid(f"{name}_apprelease")
    sources_phase_id = _make_uuid(f"{name}_sourcesphase")
    frameworks_phase_id = _make_uuid(f"{name}_frameworksphase")
    resources_phase_id = _make_uuid(f"{name}_resourcesphase")
    app_file_id = _make_uuid(f"{name}_appfile")
    app_ref_id = _make_uuid(f"{name}_appref")
    cv_file_id = _make_uuid(f"{name}_cvfile")
    cv_ref_id = _make_uuid(f"{name}_cvref")
    assets_ref_id = _make_uuid(f"{name}_assetsref")
    assets_build_id = _make_uuid(f"{name}_assetsbuild")
    products_group_id = _make_uuid(f"{name}_productsgroup")
    product_ref_id = _make_uuid(f"{name}_productref")

    # Test target objects
    test_target_id = _make_uuid(f"{name}_testtarget")
    test_config_list_id = _make_uuid(f"{name}_testconfigs")
    test_debug_id = _make_uuid(f"{name}_testdebug")
    test_release_id = _make_uuid(f"{name}_testrelease")
    test_sources_phase_id = _make_uuid(f"{name}_testsourcesphase")
    test_file_id = _make_uuid(f"{name}_testfile")
    test_ref_id = _make_uuid(f"{name}_testref")
    test_group_id = _make_uuid(f"{name}_testgroup")
    test_product_ref_id = _make_uuid(f"{name}_testproductref")
    test_dep_id = _make_uuid(f"{name}_testdep")
    test_proxy_id = _make_uuid(f"{name}_testproxy")

    # Start building the pbxproj
    sections = []
    sections.append(f"""// !$*UTF8*$!
{{
	archiveVersion = 1;
	classes = {{
	}};
	objectVersion = 56;
	objects = {{
""")

    # PBXBuildFile
    sections.append(f"""/* Begin PBXBuildFile section */
		{app_file_id} /* {name}App.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {app_ref_id}; }};
		{cv_file_id} /* ContentView.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {cv_ref_id}; }};
		{assets_build_id} /* Assets.xcassets in Resources */ = {{isa = PBXBuildFile; fileRef = {assets_ref_id}; }};
""")
    if cfg.include_tests:
        sections.append(f"""		{test_file_id} /* {name}Tests.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {test_ref_id}; }};
""")
    sections.append("""/* End PBXBuildFile section */

""")

    # PBXContainerItemProxy (for test dependency)
    if cfg.include_tests:
        sections.append(f"""/* Begin PBXContainerItemProxy section */
		{test_proxy_id} = {{
			isa = PBXContainerItemProxy;
			containerPortal = {root_id};
			proxyType = 1;
			remoteGlobalIDString = {app_target_id};
			remoteInfo = {name};
		}};
/* End PBXContainerItemProxy section */

""")

    # PBXFileReference
    sections.append(f"""/* Begin PBXFileReference section */
		{app_ref_id} /* {name}App.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = "{name}App.swift"; sourceTree = "<group>"; }};
		{cv_ref_id} /* ContentView.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = "ContentView.swift"; sourceTree = "<group>"; }};
		{assets_ref_id} /* Assets.xcassets */ = {{isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; path = "Assets.xcassets"; sourceTree = "<group>"; }};
		{product_ref_id} /* {name}.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = "{name}.app"; sourceTree = BUILT_PRODUCTS_DIR; }};
""")
    if cfg.include_tests:
        sections.append(f"""		{test_ref_id} /* {name}Tests.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = "{name}Tests.swift"; sourceTree = "<group>"; }};
		{test_product_ref_id} /* {name}Tests.xctest */ = {{isa = PBXFileReference; explicitFileType = wrapper.cfbundle; includeInIndex = 0; path = "{name}Tests.xctest"; sourceTree = BUILT_PRODUCTS_DIR; }};
""")
    sections.append("""/* End PBXFileReference section */

""")

    # PBXFrameworksBuildPhase
    sections.append(f"""/* Begin PBXFrameworksBuildPhase section */
		{frameworks_phase_id} = {{
			isa = PBXFrameworksBuildPhase;
			buildActionMask = 2147483647;
			files = (
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXFrameworksBuildPhase section */

""")

    # PBXGroup
    products_children = f"{product_ref_id}"
    if cfg.include_tests:
        products_children += f",\n\t\t\t\t{test_product_ref_id}"

    main_children = f"{sources_group_id},\n\t\t\t\t{products_group_id}"
    if cfg.include_tests:
        main_children += f",\n\t\t\t\t{test_group_id}"

    sections.append(f"""/* Begin PBXGroup section */
		{main_group_id} = {{
			isa = PBXGroup;
			children = (
				{main_children},
			);
			sourceTree = "<group>";
		}};
		{sources_group_id} /* {name} */ = {{
			isa = PBXGroup;
			children = (
				{app_ref_id},
				{cv_ref_id},
				{assets_ref_id},
			);
			path = "{name}";
			sourceTree = "<group>";
		}};
		{products_group_id} /* Products */ = {{
			isa = PBXGroup;
			children = (
				{products_children},
			);
			name = Products;
			sourceTree = "<group>";
		}};
""")
    if cfg.include_tests:
        sections.append(f"""		{test_group_id} /* {name}Tests */ = {{
			isa = PBXGroup;
			children = (
				{test_ref_id},
			);
			path = "{name}Tests";
			sourceTree = "<group>";
		}};
""")
    sections.append("""/* End PBXGroup section */

""")

    # PBXNativeTarget
    deps = ""
    if cfg.include_tests:
        deps = ""  # App target has no deps

    targets_list = f"{app_target_id}"
    if cfg.include_tests:
        targets_list += f",\n\t\t\t\t{test_target_id}"

    sections.append(f"""/* Begin PBXNativeTarget section */
		{app_target_id} /* {name} */ = {{
			isa = PBXNativeTarget;
			buildConfigurationList = {app_config_list_id};
			buildPhases = (
				{sources_phase_id},
				{frameworks_phase_id},
				{resources_phase_id},
			);
			buildRules = (
			);
			dependencies = (
			);
			name = {name};
			productName = {name};
			productReference = {product_ref_id};
			productType = "com.apple.product-type.application";
		}};
""")
    if cfg.include_tests:
        sections.append(f"""		{test_target_id} /* {name}Tests */ = {{
			isa = PBXNativeTarget;
			buildConfigurationList = {test_config_list_id};
			buildPhases = (
				{test_sources_phase_id},
			);
			buildRules = (
			);
			dependencies = (
				{test_dep_id},
			);
			name = {name}Tests;
			productName = {name}Tests;
			productReference = {test_product_ref_id};
			productType = "com.apple.product-type.bundle.unit-test";
		}};
""")
    sections.append("""/* End PBXNativeTarget section */

""")

    # PBXProject
    sections.append(f"""/* Begin PBXProject section */
		{root_id} = {{
			isa = PBXProject;
			attributes = {{
				BuildIndependentTargetsInParallel = 1;
				LastSwiftUpdateCheck = 1600;
				LastUpgradeCheck = 1600;
			}};
			buildConfigurationList = {proj_config_list_id};
			compatibilityVersion = "Xcode 14.0";
			developmentRegion = en;
			hasScannedForEncodings = 0;
			knownRegions = (
				en,
				Base,
			);
			mainGroup = {main_group_id};
			productRefGroup = {products_group_id};
			projectDirPath = "";
			projectRoot = "";
			targets = (
				{targets_list},
			);
		}};
/* End PBXProject section */

""")

    # PBXResourcesBuildPhase
    sections.append(f"""/* Begin PBXResourcesBuildPhase section */
		{resources_phase_id} = {{
			isa = PBXResourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
				{assets_build_id},
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXResourcesBuildPhase section */

""")

    # PBXSourcesBuildPhase
    sections.append(f"""/* Begin PBXSourcesBuildPhase section */
		{sources_phase_id} /* Sources */ = {{
			isa = PBXSourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
				{app_file_id},
				{cv_file_id},
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
""")
    if cfg.include_tests:
        sections.append(f"""		{test_sources_phase_id} /* Sources */ = {{
			isa = PBXSourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
				{test_file_id},
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
""")
    sections.append("""/* End PBXSourcesBuildPhase section */

""")

    # PBXTargetDependency
    if cfg.include_tests:
        sections.append(f"""/* Begin PBXTargetDependency section */
		{test_dep_id} = {{
			isa = PBXTargetDependency;
			target = {app_target_id};
			targetProxy = {test_proxy_id};
		}};
/* End PBXTargetDependency section */

""")

    # XCBuildConfiguration
    common_debug = f"""
				ALWAYS_SEARCH_USER_PATHS = NO;
				ASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS = YES;
				CLANG_ANALYZER_NONNULL = YES;
				CLANG_CXX_LANGUAGE_STANDARD = "gnu++20";
				CLANG_ENABLE_MODULES = YES;
				CLANG_ENABLE_OBJC_ARC = YES;
				COPY_PHASE_STRIP = NO;
				DEBUG_INFORMATION_FORMAT = dwarf;
				ENABLE_STRICT_OBJC_MSGSEND = YES;
				ENABLE_TESTABILITY = YES;
				GCC_DYNAMIC_NO_PIC = NO;
				GCC_OPTIMIZATION_LEVEL = 0;
				GCC_PREPROCESSOR_DEFINITIONS = (
					"DEBUG=1",
					"$(inherited)",
				);
				GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
				GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
				IPHONEOS_DEPLOYMENT_TARGET = {cfg.deployment_target};
				MTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;
				ONLY_ACTIVE_ARCH = YES;
				SDKROOT = iphoneos;
				SWIFT_ACTIVE_COMPILATION_CONDITIONS = "$(inherited) DEBUG";
				SWIFT_OPTIMIZATION_LEVEL = "-Onone";
				SWIFT_VERSION = {cfg.swift_version};"""

    common_release = f"""
				ALWAYS_SEARCH_USER_PATHS = NO;
				ASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS = YES;
				CLANG_ANALYZER_NONNULL = YES;
				CLANG_CXX_LANGUAGE_STANDARD = "gnu++20";
				CLANG_ENABLE_MODULES = YES;
				CLANG_ENABLE_OBJC_ARC = YES;
				COPY_PHASE_STRIP = NO;
				DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";
				ENABLE_NS_ASSERTIONS = NO;
				ENABLE_STRICT_OBJC_MSGSEND = YES;
				GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
				GCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
				IPHONEOS_DEPLOYMENT_TARGET = {cfg.deployment_target};
				MTL_ENABLE_DEBUG_INFO = NO;
				SDKROOT = iphoneos;
				SWIFT_COMPILATION_MODE = wholemodule;
				SWIFT_VERSION = {cfg.swift_version};
				VALIDATE_PRODUCT = YES;"""

    sections.append(f"""/* Begin XCBuildConfiguration section */
		{debug_config_id} /* Debug */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{{common_debug}
			}};
			name = Debug;
		}};
		{release_config_id} /* Release */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{{common_release}
			}};
			name = Release;
		}};
		{app_debug_id} /* Debug */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
				ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME = AccentColor;
				CODE_SIGN_STYLE = Automatic;
				CURRENT_PROJECT_VERSION = 1;
				GENERATE_INFOPLIST_FILE = YES;
				INFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES;
				INFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents = YES;
				INFOPLIST_KEY_UILaunchScreen_Generation = YES;
				INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad = "UIInterfaceOrientationPortrait UIInterfaceOrientationPortraitUpsideDown UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";
				INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone = "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";
				MARKETING_VERSION = 1.0;
				PRODUCT_BUNDLE_IDENTIFIER = "{bundle_id}";
				PRODUCT_NAME = "$(TARGET_NAME)";
				SWIFT_EMIT_LOC_STRINGS = YES;
				SWIFT_VERSION = {cfg.swift_version};
				TARGETED_DEVICE_FAMILY = "1,2";
			}};
			name = Debug;
		}};
		{app_release_id} /* Release */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
				ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME = AccentColor;
				CODE_SIGN_STYLE = Automatic;
				CURRENT_PROJECT_VERSION = 1;
				GENERATE_INFOPLIST_FILE = YES;
				INFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES;
				INFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents = YES;
				INFOPLIST_KEY_UILaunchScreen_Generation = YES;
				INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad = "UIInterfaceOrientationPortrait UIInterfaceOrientationPortraitUpsideDown UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";
				INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone = "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";
				MARKETING_VERSION = 1.0;
				PRODUCT_BUNDLE_IDENTIFIER = "{bundle_id}";
				PRODUCT_NAME = "$(TARGET_NAME)";
				SWIFT_EMIT_LOC_STRINGS = YES;
				SWIFT_VERSION = {cfg.swift_version};
				TARGETED_DEVICE_FAMILY = "1,2";
			}};
			name = Release;
		}};
""")

    if cfg.include_tests:
        sections.append(f"""		{test_debug_id} /* Debug */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				BUNDLE_LOADER = "$(TEST_HOST)";
				CODE_SIGN_STYLE = Automatic;
				CURRENT_PROJECT_VERSION = 1;
				GENERATE_INFOPLIST_FILE = YES;
				MARKETING_VERSION = 1.0;
				PRODUCT_BUNDLE_IDENTIFIER = "{bundle_id}.tests";
				PRODUCT_NAME = "$(TARGET_NAME)";
				SWIFT_EMIT_LOC_STRINGS = NO;
				SWIFT_VERSION = {cfg.swift_version};
				TARGETED_DEVICE_FAMILY = "1,2";
				TEST_HOST = "$(BUILT_PRODUCTS_DIR)/{name}.app/$(BUNDLE_EXECUTABLE_FOLDER_PATH)/{name}";
			}};
			name = Debug;
		}};
		{test_release_id} /* Release */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				BUNDLE_LOADER = "$(TEST_HOST)";
				CODE_SIGN_STYLE = Automatic;
				CURRENT_PROJECT_VERSION = 1;
				GENERATE_INFOPLIST_FILE = YES;
				MARKETING_VERSION = 1.0;
				PRODUCT_BUNDLE_IDENTIFIER = "{bundle_id}.tests";
				PRODUCT_NAME = "$(TARGET_NAME)";
				SWIFT_EMIT_LOC_STRINGS = NO;
				SWIFT_VERSION = {cfg.swift_version};
				TARGETED_DEVICE_FAMILY = "1,2";
				TEST_HOST = "$(BUILT_PRODUCTS_DIR)/{name}.app/$(BUNDLE_EXECUTABLE_FOLDER_PATH)/{name}";
			}};
			name = Release;
		}};
""")

    sections.append("""/* End XCBuildConfiguration section */

""")

    # XCConfigurationList
    sections.append(f"""/* Begin XCConfigurationList section */
		{proj_config_list_id} = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{debug_config_id},
				{release_config_id},
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
		{app_config_list_id} = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{app_debug_id},
				{app_release_id},
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
""")
    if cfg.include_tests:
        sections.append(f"""		{test_config_list_id} = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{test_debug_id},
				{test_release_id},
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
""")
    sections.append("""/* End XCConfigurationList section */

""")

    # Close root
    sections.append(f"""	}};
	rootObject = {root_id};
}}
""")

    return "".join(sections)


# ---------------------------------------------------------------------------
# Swift file generators
# ---------------------------------------------------------------------------

def generate_swiftui_app(name: str) -> str:
    """Generate the @main App entry point."""
    module = re.sub(r"[^a-zA-Z0-9]", "", name)
    return f"""import SwiftUI

@main
struct {module}App: App {{
    var body: some Scene {{
        WindowGroup {{
            ContentView()
        }}
    }}
}}
"""


def generate_content_view(name: str) -> str:
    """Generate the initial ContentView."""
    return f"""import SwiftUI

struct ContentView: View {{
    var body: some View {{
        VStack(spacing: 16) {{
            Image(systemName: "swift")
                .imageScale(.large)
                .foregroundStyle(.tint)
            Text("{name}")
                .font(.title)
        }}
        .padding()
    }}
}}

#Preview {{
    ContentView()
}}
"""


def generate_tests(name: str) -> str:
    """Generate the test file using Swift Testing framework."""
    module = re.sub(r"[^a-zA-Z0-9]", "", name)
    return f"""import Testing
@testable import {module}

struct {module}Tests {{
    @Test func appLaunches() async throws {{
        // Basic smoke test — app module imports successfully
        #expect(true)
    }}
}}
"""


# ---------------------------------------------------------------------------
# Supporting file generators
# ---------------------------------------------------------------------------

def generate_claude_md(name: str) -> str:
    """Generate CLAUDE.md with SwiftUI rules and CCA conventions."""
    return f"""# {name} — CLAUDE.md

## Architecture
- **SwiftUI + MVVM** — one file per View, one file per ViewModel
- **One file = one job** — no god-objects, no massive view files
- **Swift 6 @Observable** macro for state management (not ObservableObject)
- **NavigationStack** with type-safe routing (not NavigationView)
- **Swift Testing** framework with @Test macros (not XCTest)

## Rules
- Test every ViewModel method before writing View code
- Never force-unwrap optionals — use guard/if-let
- Use async/await for all network calls (no completion handlers)
- Keep Views under 100 lines — extract subviews aggressively
- Use SwiftUI previews for every View (#Preview macro)

## Build & Test
```bash
# Build for simulator
xcodebuild build -project {name}.xcodeproj -scheme {name} -destination "generic/platform=iOS Simulator" -quiet

# Run tests
xcodebuild test -project {name}.xcodeproj -scheme {name} -destination "platform=iOS Simulator,name=iPhone 17 Pro" -quiet
```

## File Structure
```
{name}/
├── {name}App.swift          # @main entry point
├── ContentView.swift         # Root view
├── Views/                    # One file per view
├── ViewModels/               # One file per view model
├── Models/                   # Data models
├── Services/                 # API clients, persistence
└── Assets.xcassets/          # Images, colors, app icon
{name}Tests/
└── {name}Tests.swift         # Swift Testing tests
```
"""


def generate_info_plist(name: str) -> str:
    """Generate Info.plist (minimal — most settings auto-generated by Xcode)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleDisplayName</key>
	<string>{name}</string>
</dict>
</plist>
"""


def generate_gitignore() -> str:
    """Generate .gitignore for Xcode projects."""
    return """# Xcode
*.xcodeproj/project.xcworkspace/
*.xcodeproj/xcuserdata/
*.xcworkspace/
xcuserdata/
DerivedData/
build/
*.ipa
*.dSYM.zip
*.dSYM

# Swift Package Manager
.build/
Packages/

# CocoaPods (not used but just in case)
Pods/

# macOS
.DS_Store
"""


def generate_assets_catalog(name: str) -> dict:
    """Generate Assets.xcassets structure. Returns dict of path -> content."""
    return {
        "Contents.json": '{\n  "info" : {\n    "author" : "xcode",\n    "version" : 1\n  }\n}\n',
        "AccentColor.colorset/Contents.json": '{\n  "colors" : [\n    {\n      "idiom" : "universal"\n    }\n  ],\n  "info" : {\n    "author" : "xcode",\n    "version" : 1\n  }\n}\n',
        "AppIcon.appiconset/Contents.json": '{\n  "images" : [\n    {\n      "idiom" : "universal",\n      "platform" : "ios",\n      "size" : "1024x1024"\n    }\n  ],\n  "info" : {\n    "author" : "xcode",\n    "version" : 1\n  }\n}\n',
    }


# ---------------------------------------------------------------------------
# Project generator (orchestrator)
# ---------------------------------------------------------------------------

def generate_project(cfg: ProjectConfig, output_dir: str) -> str:
    """Generate a complete Xcode project.

    Args:
        cfg: Project configuration.
        output_dir: Parent directory to create project in.

    Returns:
        Path to the generated project directory.

    Raises:
        FileExistsError: If the project directory already exists.
    """
    project_dir = os.path.join(output_dir, cfg.name)
    if os.path.exists(project_dir):
        raise FileExistsError(f"Directory already exists: {project_dir}")

    name = cfg.module_name

    # Create directory structure
    os.makedirs(os.path.join(project_dir, f"{cfg.name}.xcodeproj"))
    os.makedirs(os.path.join(project_dir, cfg.name))
    if cfg.include_tests:
        os.makedirs(os.path.join(project_dir, f"{cfg.name}Tests"))

    # Write pbxproj
    pbxproj_path = os.path.join(project_dir, f"{cfg.name}.xcodeproj", "project.pbxproj")
    with open(pbxproj_path, "w") as f:
        f.write(generate_pbxproj(cfg))

    # Write Swift files
    with open(os.path.join(project_dir, cfg.name, f"{name}App.swift"), "w") as f:
        f.write(generate_swiftui_app(cfg.name))

    with open(os.path.join(project_dir, cfg.name, "ContentView.swift"), "w") as f:
        f.write(generate_content_view(cfg.name))

    if cfg.include_tests:
        with open(os.path.join(project_dir, f"{cfg.name}Tests", f"{name}Tests.swift"), "w") as f:
            f.write(generate_tests(cfg.name))

    # Write Assets.xcassets
    assets_dir = os.path.join(project_dir, cfg.name, "Assets.xcassets")
    for rel_path, content in generate_assets_catalog(cfg.name).items():
        full_path = os.path.join(assets_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)

    # Write CLAUDE.md
    with open(os.path.join(project_dir, "CLAUDE.md"), "w") as f:
        f.write(generate_claude_md(cfg.name))

    # Write .gitignore
    with open(os.path.join(project_dir, ".gitignore"), "w") as f:
        f.write(generate_gitignore())

    return project_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate an iOS SwiftUI project for Claude Code workflows."
    )
    parser.add_argument("name", help="Project name (e.g., KalshiDashboard)")
    parser.add_argument("--output", "-o", default=".", help="Output directory (default: current)")
    parser.add_argument("--bundle-id", help="Bundle identifier (default: com.cca.<name>)")
    parser.add_argument("--deployment-target", default="18.0", help="iOS deployment target")
    parser.add_argument("--swift-version", default="6.0", help="Swift version")
    parser.add_argument("--no-tests", action="store_true", help="Skip test target")

    args = parser.parse_args()

    cfg = ProjectConfig(
        name=args.name,
        bundle_id=args.bundle_id or "",
        deployment_target=args.deployment_target,
        swift_version=args.swift_version,
        include_tests=not args.no_tests,
    )

    path = generate_project(cfg, args.output)
    print(f"Generated project: {path}")
    print(f"  xcodeproj: {path}/{args.name}.xcodeproj")
    print(f"  bundle ID: {cfg.bundle_id}")
    print(f"  Swift {cfg.swift_version}, iOS {cfg.deployment_target}")
    if cfg.include_tests:
        print(f"  tests: {path}/{args.name}Tests/")
    print(f"\nBuild: xcodebuild build -project {path}/{args.name}.xcodeproj -scheme {args.name} -destination 'generic/platform=iOS Simulator' -quiet")


if __name__ == "__main__":
    main()
