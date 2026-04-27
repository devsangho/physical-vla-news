# 📄 VLA / Physical AI Daily Digest

매일 아침 10시(KST)에 VLA 모델 및 Physical AI 관련 논문·뉴스를 자동 수집하고,
Claude API로 요약하여 GitHub Issue로 발행하는 파이프라인입니다.

## 소스

| 소스 | 방식 | 비용 |
|------|------|------|
| arXiv | 공식 API | 무료 |
| Semantic Scholar | 공식 API | 무료 |
| Google Scholar | scholarly 라이브러리 | 무료 (rate limit 주의) |
| Google News | RSS 피드 | 무료 |

> Twitter/X는 API 비용 문제로 Semantic Scholar로 대체했습니다.

## 설정 방법

### 1. 레포 생성

이 디렉토리 전체를 새 GitHub 레포로 push합니다:

```bash
git init
git add .
git commit -m "init: VLA paper digest pipeline"
gh repo create vla-paper-digest --public --push
```

### 2. Anthropic API Key 등록

GitHub 레포 → Settings → Secrets and variables → Actions → New repository secret:

- Name: `ANTHROPIC_API_KEY`
- Value: 본인의 Anthropic API key

> `GITHUB_TOKEN`은 GitHub Actions에서 자동 제공되므로 별도 등록 불필요합니다.

### 3. Issues 활성화 확인

레포 Settings → Features → Issues가 체크되어 있는지 확인합니다.

### 4. 테스트 실행

GitHub 레포 → Actions → "VLA/Physical AI Daily Digest" → "Run workflow" 버튼으로 수동 실행합니다.

## 커스터마이징

### 검색 키워드 수정

`scripts/daily_digest.py`의 `SEARCH_QUERIES` 리스트를 수정하세요:

```python
SEARCH_QUERIES = [
    "vision language action model",
    "VLA robot",
    "physical AI robotics",
    # 여기에 키워드 추가
]
```

### 실행 시간 변경

`.github/workflows/daily-digest.yml`의 cron 표현식을 수정하세요:

```yaml
schedule:
  - cron: "0 1 * * *"  # UTC 01:00 = KST 10:00
```

### 라벨 커스터마이징

`create_github_issue()` 함수의 `labels`를 수정하세요.

## 구조

```
.
├── .github/workflows/
│   └── daily-digest.yml      # GitHub Actions 워크플로우
├── scripts/
│   └── daily_digest.py        # 메인 스크립트
├── requirements.txt           # Python 의존성
└── README.md
```

## 비용

- GitHub Actions: 무료 (public repo) / 월 2,000분 (private repo)
- Anthropic API: 요약 1회당 약 $0.01~0.03 (Sonnet 기준)
- 월 예상 비용: **~$1 미만**

## 💰 Bounty Contribution

- **Task:** 📄 VLA/Physical AI Daily Digest — 2026-04-27
- **Reward:** $6
- **Source:** GitHub-Paid
- **Date:** 2026-04-27

