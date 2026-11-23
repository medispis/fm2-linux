# Graphics optimization findings

This audit covers FM2's pinned ReXGlue v0.11.0 revision
`a3e1d82678ca20d68d4837a8e9ee4652ff073745`. It uses source inspection and
existing local captures. No renderer changes, new benchmarks, or race
tests were made.

## What the existing capture shows

In the capture labeled 60 Hz, the screenshots bracketing the timing
window both show the 3D Arcade tab. The trace contains 17 sampled Vulkan
submissions, with a median GPU submission span of **11.24 ms**. Dynamic
rendering spans with draws in a 1280×512 render area account for **100.53 ms
of 191.98 ms** of summed submission spans (**52.4%**). The spans with one
color attachment account for 68.30 ms; those with zero color attachments
account for 32.23 ms. Zero color attachments does not rule out depth or
stencil work. These are render-area dimensions and submission timings,
not displayed resolution or whole-frame times.

The two archived runs used Vulkan presentation mode 0. The capture labeled
120 Hz ends on the title screen, not the Arcade tab, so it is not a valid
comparison. Keep the raw traces and screenshots local.

## Specific optimization candidates

### 1. Identify the expensive 1280×512 draws

In `src/gpu/xenos/vulkan/command_processor.cpp`, group the sampled
`VulkanCommandProcessor::IssueDraw` work by guest shader pair, render target,
depth/stencil state, and sample count. The existing data says where time
went, but does not identify an expensive shader or prove redundant draws.
If one translated shader dominates, inspect its texture fetches and
generated SPIR-V. If many small draws dominate, check for avoidable
rendering-scope breaks and attachment transitions before changing shaders.
Compare the same scene at the same quality and check depth and stencil
output, not just the final car image.

### 2. Remove a resolve preflight, then test a real direct resolve

In `src/gpu/xenos/vulkan/render_target_cache.cpp`, `Resolve` tries
`TryDirectResolve` by default on the host-render-target path.
`TryDirectResolve` computes dispatches and looks up pipelines, but on
success it still calls `DumpRenderTargets`. `GetDirectResolvePipeline`
reuses the ordinary copy pipeline; there is no dedicated source-image
shader. The later resolve dispatch still reads the intermediate EDRAM
buffer and writes the destination. A “direct resolve success” therefore
does not mean a copy was avoided.

The lowest-effort test is an A/B run with `--gpu.xenos.direct_host_resolve=false`.
Confirm the host-render-target path is active and time CPU resolve setup
separately from GPU work. This tests whether the preflight costs anything
on FM2; it does not remove the GPU copy. If the dump and copy are expensive
and one format dominates, consider a shader that writes the guest-tiled
destination directly for that specific format. Keep the fallback for
untested cases and compare destination bytes, including tile placement,
format conversion, MSAA, and depth/stencil where applicable. Resolve
clears and texture-cache notifications must still happen.

### 3. Reduce pipeline creation stutter without dropping draws

`tools/run-fm2.sh` disables async shader compilation. In `IssueDraw`, the
async placeholder branch returns before drawing, so enabling it is not a
quality-neutral optimization. The Vulkan pipeline cache already persists
shader and pipeline-description data, but the graphics creation call in
`pipeline_cache.cpp` passes `VK_NULL_HANDLE` as the `VkPipelineCache`.

Measure cold and warm `vkCreateGraphicsPipelines` time and menu frame-time
spikes first. If driver compilation remains significant, test a
device-compatible persistent Vulkan pipeline cache. Reject incompatible
cache blobs, keep the cache local, and measure whether the change reduces
stutter or merely moves the work to startup. This is a stutter candidate,
not evidence of higher steady-state FPS.

## Lower priority

- **GPU-to-CPU readback:** Resolve readback defaults to `none`; don't assume
  it causes the observed bottleneck. Shader memexport readback is separate
  and can wait for the GPU. Count those waits before investigating further;
  don't disable readback without proving that guest memory remains coherent.
- **Lower internal resolution:** A prior 640×480 guest mode request left the
  1280×720 swap source unchanged. ReXGlue's existing draw scale settings are
  integer multipliers with a minimum of 1, not a way to render below native
  size. Treat sub-native 3D rendering as a separate quality option, not a
  quick fix to the present window size.

## Suggested first benchmark

Use a normal 60 Hz launch, the same Arcade tab and window size, and a
warmed cache. Repeat the runs and record median and 95th-percentile frame
times, GPU draw and resolve spans, and CPU resolve setup time. Start with
draw attribution and the direct-resolve A/B test before changing renderer
behavior. Check output before keeping any optimization. A menu
result is not a race result; verify races separately only with approval.
