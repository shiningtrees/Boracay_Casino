# 📚 Boracay Casino Documentation

> 프로젝트 문서 체계 가이드

---

## 폴더 구조

```
docs/
├── planning/           # 기획 및 스펙 문서
├── deploy/            # 배포 관련 문서
└── changelog/         # 작업 일지 (날짜별)
```

---

## 1. planning/ - 기획 및 스펙 문서

**용도**: 구현 예정/진행 중인 작업, 프로젝트 기획서

### 파일명 규칙
- **todo 문서**: `toto_NNN_feature_YYMMDD.md`
  - 예: `toto_001_max_profit_260213.md`
- **기획서**: `프로젝트명.md`
  - 예: `Boracay Casino 프로젝트 마스터플랜.md`

### 작성 시점
- 새 기능 구현 전 스펙 정의
- 실험/검증 계획 수립 시

### 완료 처리
- 완료 표시: 문서 상단에 `> **Status**: ✅ 구현 완료 (YYYY-MM-DD)` 추가
- 파일 유지: planning/ 폴더에 그대로 보관 (히스토리 보존)

---

## 2. deploy/ - 배포 관련 문서

**용도**: 서버 배포 가이드, CI/CD, 운영 워크플로우

### 주요 문서
- `SERVER_DEPLOY.md`: 서버 배포 절차
- `ORIGINAL_ONLY_WORKFLOW.md`: 배포 워크플로우

### 작성 시점
- 새 환경 구축 시
- 배포 절차 변경 시
- 운영 이슈 대응 가이드 필요 시

---

## 3. changelog/ - 작업 일지

**용도**: 날짜별 상세 작업 내역 기록

### 파일명 규칙
- `YYYY-MM-DD.md` (예: `2026-02-14.md`)

### 작성 내용
- 구현한 기능 상세 설명
- 코드 변경 사항 (파일별 주요 변경점)
- 테스트 결과 및 이슈
- 다음 작업 계획

### 작성 시점
- 주요 기능 구현 완료 후
- 중요한 버그 수정 후
- 마일스톤 달성 시

---

## 문서 작성 가이드

### 신규 문서 생성
1. **기능 스펙**: `docs/planning/toto_NNN_feature_YYMMDD.md`
2. **작업 일지**: `docs/changelog/YYYY-MM-DD.md`
3. **배포 가이드**: `docs/deploy/GUIDE_NAME.md`

### 기존 문서 업데이트
- **DEV_NOTES.md** (루트): 프로젝트 전반 업데이트 시
- **planning/*.md**: 스펙 변경/완료 표시
- **changelog/*.md**: 해당 날짜 일지에 추가

### 문서 작성 원칙
- **간결함**: 과잉 문서화 금지
- **실용성**: 실제로 참고할 내용만
- **최신성**: 오래된 정보는 상단에 표시

---

## Quick Reference

### 어떤 문서를 먼저 읽어야 할까?
1. **루트 `DEV_NOTES.md`**: 프로젝트 전체 구조 파악
2. **`planning/toto_*.md`**: 현재 작업 중인 기능 확인
3. **`changelog/latest`**: 최근 작업 내역 확인
4. **`deploy/`**: 배포 필요 시

### 다른 에이전트가 작업 이어받을 때
1. `DEV_NOTES.md` 읽고 전체 구조 파악
2. `docs/planning/` 폴더에서 진행 중인 todo 확인
3. `docs/changelog/` 최신 일지로 최근 작업 컨텍스트 확인
4. 작업 완료 후 changelog 작성

---

**Last Updated**: 2026-02-14
