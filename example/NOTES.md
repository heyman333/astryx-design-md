# design.md / llms.txt 검증 결과

루트의 `design.md`와 `llms.txt`**만** 참고해 실제 Astryx 페이지("프로젝트 설정")를
작성하고, 빌드·렌더링까지 확인한 기록입니다. 결과물은 `screenshot.png` 참고.
오버레이 컴포넌트(Dialog, HoverCard)는 `screenshot-dialog.png` /
`screenshot-hovercard.png` 참고 — `?demo=dialog`, `?demo=hovercard` 쿼리로
열린 상태를 재현할 수 있습니다.

## 실행

```bash
cd example
npm install
npm run build     # tsc --noEmit && vite build
npm run dev       # http://localhost:5173
```

## 시도 1 — 두 문서만으로 작성

**성공한 것 (문서 정보가 정확했던 부분):**

- 설치 명령(`npm install @astryxdesign/core @astryxdesign/theme-neutral @stylexjs/stylex`)이 그대로 동작
- design.md 컴포넌트 인벤토리의 이름 13개(Banner, Avatar, Badge, Heading, Text, Card,
  TextInput, TextArea, Switch, Divider, Button, Stack, Theme)가 **전부 `@astryxdesign/core`에서
  임포트 성공** — 인벤토리가 실제 export와 일치
- CSS 경로 추측(`@astryxdesign/core/astryx.css`, `@astryxdesign/theme-neutral/theme.css`)이
  실제 export와 일치 ("pre-built CSS `astryx.css`" 서술 덕분)
- 컴포넌트 선택 가이드가 유효 (예: "설정에는 Switch, 폼 제출에는 checkbox",
  "Card는 기본 레이아웃 도구가 아님")

**실패한 것 (tsc 오류 17건 — 문서에 props가 없어서):**

| 추측 | 실제 |
| --- | --- |
| `Banner variant="info"` | `status="info"` |
| `Stack gap="lg"` | `gap={6}` — 숫자 스케일 `0~10`, 문자열 아님 |
| `Section title="..."` | Section에 title prop 없음 (Heading 별도 사용) |
| `TextInput defaultValue` | uncontrolled 미지원 — `value` + `onChange` 필수 (controlled only) |
| `Switch defaultChecked` | `value: boolean` 필수 (controlled only) |
| `Text type="caption"` | `type="supporting"` |
| `<Theme>` 만 감싸기 | `theme={neutralTheme}` prop 필수 (`@astryxdesign/theme-neutral/built`) |
| `style={{...}}` | style prop 없음 — `width`/`maxWidth`/`padding` prop 또는 `xstyle` |

## 시도 2 — llms.txt가 안내한 CLI로 props 확인 후 수정

llms.txt의 "CLI bootstrap for agents" 항목대로
`astryx component <Name> --dense`, `astryx docs theme --dense`를 실행해 실제 props를
확인하고 수정 → **tsc 0 오류, vite build 성공, 렌더링 정상**.

## 추가 검증 — Dialog & HoverCard

같은 흐름(CLI로 props 확인 → 구현)으로 오버레이 컴포넌트 2종을 추가:

- **Dialog** — 저장 확인 모달. `isOpen`/`onOpenChange` controlled, 내부에 `DialogHeader`
  (title이 aria-labelledby + 포커스 대상) + 본문 + 액션 버튼. `purpose`로 dismiss 정책
  제어(info/form/required). 이번엔 CLI 문서만으로 **tsc·빌드 첫 시도 통과**.
- **HoverCard** — 작성자 `@yuna` 텍스트에 호버하면 프로필 카드. `content` prop에 카드
  내용, children이 트리거(ref 전달 필요). `placement`/`alignment`는 RTL 대응 논리값
  (above/below/start/end). 트리거에 dashed underline 힌트가 자동 적용됨.

## 추가 검증 — DateInput

- **DateInput** — "출시 예정일" 필드. `value`가 `ISODateString`(`YYYY-MM-DD` 템플릿
  리터럴 타입)이라 일반 `string` state는 tsc에서 거부됨 — 타입은
  `@astryxdesign/core/Calendar`에서 import (`import type {ISODateString}`).
  `min`으로 과거 날짜 차단, 선택적 필드라 `isOptional` + `hasClear` 적용
  (CLI Best Practices 권고 그대로). 표시 포맷은 기본 `date_long`이 브라우저
  로케일을 따라 "2026년 9월 1일"로 렌더링됨.

## 결론

- **design.md/llms.txt는 "무엇을 쓸지"(컴포넌트 선택·설치·구조 이해)에는 충분하고 정확함.**
- **"어떻게 쓸지"(props)는 의도적으로 문서 밖** — llms.txt에 명시된 CLI 조회 흐름으로
  해결되며, 이 흐름 자체가 실제로 동작함을 확인.
- 개선 아이디어: llms.txt Key facts에 다음 두 줄을 추가하면 시도 1의 오류 대부분이 예방됨.
  - "All inputs are controlled: `value` + `onChange` (no `defaultValue`/`defaultChecked`)."
  - "Layout spacing uses a numeric scale: `gap={4}`, not `gap=\"md\"`; no `style` prop — use `xstyle` or size props."
