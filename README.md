# sd-webui-grid-limit

Stable Diffusion WebUI (AUTOMATIC1111 / Forge) extension that limits the **batch grid** to the first **4, 9 or 16** images.
All individual images are still generated, saved and shown as usual — only the grid is limited.

[한국어](#한국어) · [English](#english)

---

## 한국어

### 기능
- 한 번 생성한 이미지 수(배치 수 × 배치 크기)가 설정한 한도보다 많으면, **그리드는 처음 N장만** 사용해서 만들어요. (4 → 2×2, 9 → 3×3, 16 → 4×4)
- 한도 이하이면 원래 동작 그대로예요.
- 개별 이미지 저장·표시는 전혀 바꾸지 않아요.
- A1111/Forge 원본 파일을 수정하지 않는 확장이에요. (함수 패치도 없음)
- X/Y/Z plot, Prompt matrix 같은 스크립트를 선택했을 때는 동작하지 않아서 그 스크립트의 그리드는 그대로예요.

### 설치 (원격 컴퓨터)
1. WebUI → **Extensions** → **Install from URL**
2. *URL for extension's git repository* 에 `https://github.com/blinker1104/sd-webui-grid-limit` 입력 → **Install**
3. **Installed** 탭 → **Apply and restart UI** (또는 WebUI 재시작)

업데이트: **Extensions → Installed → Check for updates → Apply and restart UI**

수동 설치: `cd extensions && git clone https://github.com/blinker1104/sd-webui-grid-limit`

### 사용법
txt2img / img2img 화면의 **Grid Limit** 접이식 패널에서 매번 바로 바꿀 수 있어요.
- **Limit grid images**: 켜기/끄기
- **Max images in grid**: 4 / 9 / 16

### 설정 (Settings → Saving images → Grid Limit)
| 설정 | 기본값 | 설명 |
|---|---|---|
| Enable grid limit by default | 켜짐 | 생성 화면 체크박스의 기본값 (Reload UI 후 반영) |
| Default max images in grid | 4 | 생성 화면 4/9/16 선택의 기본값 (Reload UI 후 반영) |
| Use a square layout | 켜짐 | 끄면 기본 "Grid row count" 규칙으로 배치 |
| Write 'Grid limit' to generation parameters | 켜짐 | 한도가 적용될 때 생성 정보에 `Grid limit: N` 기록 |

참고: 그리드 자체가 만들어지려면 기본 설정 **Settings → Saving images/grids → Always save all generated image grids** 또는 **Settings → Gallery → Show grid in gallery** 중 하나가 켜져 있어야 해요 (둘 다 기본값 켜짐).

### 호환성
- AUTOMATIC1111 v1.10.x (master/dev) — 확인한 소스 기준으로 작성
- Forge (lllyasviel/stable-diffusion-webui-forge, Gradio 4) — 같은 훅 구조 확인
- 다른 포크(reForge, Forge Neo 등)는 `processing.process_images_inner()`가 `images.image_grid()`를 직접 호출하는 구조라면 동작해요. 구조가 다르면 아무 것도 바꾸지 않아요(안전하게 무시).

---

## English

### What it does
- If a generation produces more images than the limit, the grid is built from **only the first N images** (4 → 2×2, 9 → 3×3, 16 → 4×4).
- At or below the limit nothing changes.
- Individual image saving/display is never touched.
- Pure extension: no core file is edited, nothing is monkey-patched.
- Does nothing while a script from the *Script* dropdown (X/Y/Z plot, Prompt matrix, …) is selected, so those grids are unaffected.

### Install
Extensions → Install from URL → `https://github.com/blinker1104/sd-webui-grid-limit` → Install → Installed → Apply and restart UI.
Update with **Check for updates**.

### Usage
Open the **Grid Limit** accordion in txt2img / img2img, toggle **Limit grid images** and choose **4 / 9 / 16** per generation.

### Settings (Settings → Saving images → Grid Limit)
Defaults for the UI controls (need *Reload UI*), square layout toggle, and whether `Grid limit: N` is written to the generation parameters.

API: `"alwayson_scripts": {"Grid Limit": {"args": [true, "9"]}}`

### How it works
1. `process()` of an AlwaysVisible script stores a small config on the processing object `p`.
2. The official `script_callbacks.on_image_grid` hook receives `ImageGridLoopParams` (imgs/cols/rows) from `modules/images.py::image_grid()`.
   The callback only acts when `image_grid()` was called directly by `modules/processing.py::process_images_inner()` for that same `p`,
   and then replaces `params.imgs` with a *new* list of the first N images and sets rows/cols.
3. `postprocess()` removes the config again.

### Compatibility
- AUTOMATIC1111 v1.10.x (master and dev)
- Forge (lllyasviel/stable-diffusion-webui-forge, Gradio 4)
- Other forks work if they keep the same `process_images_inner -> images.image_grid` call; otherwise the extension safely does nothing.

### Development
```
python3 -m unittest discover -s tests -v
```

License: MIT
