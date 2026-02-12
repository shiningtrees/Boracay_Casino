# Boracay Casino Original-Only Workflow

혼자 개발할 때는 워크트리를 쓰지 않고, 항상 원본 폴더만 사용한다.

## 원칙
- 작업 폴더는 항상 `~/GitHub/Boracay_Casino` 하나만 사용한다.
- 실행/수정/테스트/커밋을 모두 원본 폴더에서만 수행한다.
- `~/.cursor/worktrees/...` 경로에서는 작업하지 않는다.

## 작업 시작 체크 (매번)
1. Cursor에서 `File > Open Folder...`로 `~/GitHub/Boracay_Casino`를 연다.
2. 터미널에서 `pwd`가 `~/GitHub/Boracay_Casino`인지 확인한다.
3. `git status`로 현재 브랜치/변경사항을 확인한다.

## 작업 중 체크
- 실행 명령은 항상 원본 경로에서만:
  - `source venv/bin/activate`
  - `python main.py`
- 경로에 `worktrees`가 보이면 즉시 중단하고 원본 폴더로 다시 연다.

## 작업 종료 체크
- 변경 확인: `git status`
- 필요 시 diff 확인: `git diff`
- 커밋/배포 전 마지막으로 현재 경로 확인: `pwd`

## 권장 운영 팁
- Cursor를 여러 창으로 쓸 때, 창 제목/경로 표시를 보고 원본 폴더인지 먼저 확인한다.
- 실수 방지용으로 터미널 프롬프트에 현재 경로가 보이도록 유지한다.

## 한 줄 규칙
**"Boracay Casino는 항상 `~/GitHub/Boracay_Casino`에서만 작업한다."**
