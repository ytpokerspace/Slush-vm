# Platform Registries

This is a semantic map, not a statement that every platform integration is implemented.

## Windows Registry

Canonical hives: windows.registry.hklm (HKEY_LOCAL_MACHINE), windows.registry.hkcu (HKEY_CURRENT_USER), windows.registry.hkcr (merged class-registration view), windows.registry.hku (HKEY_USERS), and windows.registry.hkcc (HKEY_CURRENT_CONFIG hardware-profile view).

Concepts include HKLM SYSTEM/SOFTWARE/SECURITY/SAM/HARDWARE; HKCU Software/Environment/Explorer and Run entries; HKCR file extensions and handlers; and per-user settings. Exact paths vary by setting/version. HKLM SECURITY and SAM are sensitive and OS-protected. Run entries affect startup. ACLs, elevation, registry views, and redirection matter.

Suggested operations: windows.registry.key.enumerate, windows.registry.value.read/write/delete, windows.registry.association.inspect, windows.registry.startup.inspect. Separate read/write/delete permissions and preserve native types such as REG_SZ, REG_DWORD, REG_QWORD, REG_BINARY, and REG_MULTI_SZ.

## Windows graphics, UI, audio, media

- DWM is a compositor, not DirectX itself.
- DirectX is an ecosystem; Direct3D and Direct2D are distinct APIs.
- DirectWrite handles text layout/rendering; DXGI is graphics infrastructure.
- WDDM is a driver model, not a rendering API.
- Vulkan and OpenGL are cross-platform APIs, but availability depends on drivers/backends.
- WPF and WinUI are UI frameworks; Windows Composition is a composition API family.
- WASAPI and DirectSound are audio APIs; Media Foundation is a media platform.
- A codec defines encoding/decoding; DXVA concerns hardware video acceleration; Windows Media Player is an application/integration.

Capability families include graphics.device.enumerate, graphics.surface.create, graphics.render.frame, graphics.present, graphics.text.layout, audio.device.enumerate, audio.stream.play/capture, media.decode/encode, and media.hardware_acceleration.inspect.

## Filesystem, storage, process, and network

Separate portable file operations from platform-specific mounts, block devices, partitions, repair, boot configuration, and image servicing. Resolve paths with symlink/junction, traversal, TOCTOU, and allowed-root concerns. Destructive storage operations require explicit targets, confirmation, elevated permission, and audit.

Distinguish VM tasks, shell jobs, OS processes, and threads. Unix fork is not equivalent to a VM task. Timeout and process-tree termination semantics must be explicit. Split network inspection from configuration and connect from listen. SSH, SMB, remote administration, route changes, and cloud operations need scoped permissions.

## Packages, builds, containers, cloud

Separate OS package managers from language package managers. Install scripts/build scripts execute code. Rust's rustc compiler is distinct from Cargo. Docker mounts, privileged mode, daemon access, and network policy must be explicit. Kubernetes operations require context/namespace and separate read/write permissions. Azure operations require tenant/subscription/resource scope.

## Android

An APK includes manifest, DEX, resources, optional native libraries, and signing metadata. OAT is an ART compilation artifact, not a mandatory APK component. A signature's presence alone does not prove trust; verify signer, scheme, platform expectations, and package integrity. Separate inspection from installation and system-level operations.
